#!/usr/bin/env python3
"""Configura hosts finales (servidores, impresoras, PCs) editando el XML del .pkt guardado por PT."""
import sys, re, html, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pkt

SRC, DST = sys.argv[1], sys.argv[2]
raw = open(SRC, "rb").read()
doc = (pkt.decode(raw) if not raw.startswith(b"<") else raw).decode("utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))

DOMAIN = "sslmjp.net"
WEB6, DNS6, TRK6 = "2001:1200:EC15:1::10", "2001:1200:EC15:1::53", "2001:1200:EC15:1::30"

def block(name):
    """Devuelve (inicio, fin) del <ENGINE> del dispositivo."""
    i = doc.index(f'<NAME translate="true">{name}</NAME>')
    s = doc.rindex("<ENGINE>", 0, i)
    e = doc.index("</ENGINE>", i)
    return s, e

def edit(name, fn):
    global doc
    s, e = block(name)
    doc = doc[:s] + fn(doc[s:e]) + doc[e:]

def set_tag(b, tag, val, count=1):
    pat = re.compile(rf"<{tag}>[^<]*</{tag}>|<{tag}\s*/>")
    n = [0]
    def rep(m):
        n[0] += 1
        if n[0] > count:
            return m.group(0)
        return f"<{tag}>{val}</{tag}>" if val != "" else f"<{tag}/>"
    out = pat.sub(rep, b)
    if n[0] == 0:
        raise KeyError(tag)
    return out

def first_eth_port(b):
    """(ini, fin) del primer <PORT> que contiene IPV6_ENABLED (FastEthernet0)."""
    i = b.index("<IPV6_ENABLED>")
    s = b.rindex("<PORT>", 0, i)
    e = b.index("</PORT>", i) + len("</PORT>")
    return s, e

def v6list(addrs):
    x = "<IPV6_ADDRESSES>"
    for a, p in addrs:
        x += f"<IPV6_ADDRESS><ADDRESS>{a}</ADDRESS><PREFIX>{p}</PREFIX><TYPE>0</TYPE></IPV6_ADDRESS>"
    return x + "</IPV6_ADDRESSES>"

def static_host(name, ip4=None, mask4=None, gw4=None, ip6=None, gw6=None, dns6=None):
    def fn(b):
        s, e = first_eth_port(b)
        p = b[s:e]
        p = set_tag(p, "IP", ip4 or "")
        p = set_tag(p, "SUBNET", mask4 or "")
        p = set_tag(p, "PORT_DHCP_ENABLE", "false")
        p = set_tag(p, "IPV6_ENABLED", "true" if ip6 else "false")
        p = set_tag(p, "IPV6_ADDRESS_AUTOCONFIG", "false")
        p = set_tag(p, "IPV6_PORT_DHCP_ENABLED", "false")
        if gw6:
            p = set_tag(p, "IPV6_PORT_GATEWAY", gw6)
        if dns6:
            p = set_tag(p, "IPV6_PORT_DNS", dns6)
        p = re.sub(r"<IPV6_ADDRESSES>.*?</IPV6_ADDRESSES>|<IPV6_ADDRESSES\s*/>",
                   v6list([(ip6, 64)] if ip6 else []), p, count=1, flags=re.S)
        b = b[:s] + p + b[e:]
        b = set_tag(b, "GATEWAY", gw4 or "")
        b = set_tag(b, "GATEWAYV6", gw6 or "")
        if dns6:
            b = re.sub(r"<DNS_CLIENT>.*?</DNS_CLIENT>",
                       f"<DNS_CLIENT><SERVER_IP/><SERVER_IPV6>{dns6}</SERVER_IPV6></DNS_CLIENT>", b, count=1, flags=re.S)
        return b
    edit(name, fn)

def services(name, http=None, https=None, dns=None):
    def fn(b):
        if http is not None:
            b = re.sub(r"(<HTTP_SERVER>\s*<ENABLED>)\d(</ENABLED>)", rf"\g<1>{1 if http else 0}\2", b, count=1)
        if https is not None:
            b = re.sub(r"<HTTPSENABLED>\d</HTTPSENABLED>", f"<HTTPSENABLED>{1 if https else 0}</HTTPSENABLED>", b, count=1)
        if dns is not None:
            recs = "".join(f"<RESOURCE-RECORD><TYPE>AAAA-REC</TYPE><NAME>{n}</NAME><TTL>86400</TTL>"
                           f"<IPV6ADDRESS>{a}</IPV6ADDRESS></RESOURCE-RECORD>" for n, a in dns)
            b = re.sub(r"<DNS_SERVER>\s*<ENABLED>\d</ENABLED>\s*(<NAMESERVER-DATABASE\s*/>|<NAMESERVER-DATABASE>.*?</NAMESERVER-DATABASE>)",
                       f"<DNS_SERVER><ENABLED>{1 if dns else 0}</ENABLED><NAMESERVER-DATABASE>{recs}</NAMESERVER-DATABASE>",
                       b, count=1, flags=re.S)
        return b
    edit(name, fn)

def http_index(name, page_html):
    def fn(b):
        i = b.index("<NAME>http:</NAME>")
        j = b.index("<NAME>index.html</NAME>", i)
        s = b.index("<TEXT>", j) + len("<TEXT>")
        e = b.index("</TEXT>", s)
        return b[:s] + html.escape(page_html, quote=False) + b[e:]
    edit(name, fn)

def dhcp_pools(name, pools):
    def pool(p):
        return ("<POOL>" + f"<NAME>{p['name']}</NAME><NETWORK>{p['net']}</NETWORK><MASK>{p['mask']}</MASK>"
                f"<DEFAULT_ROUTER>{p['gw']}</DEFAULT_ROUTER><TFTP_ADDRESS>0.0.0.0</TFTP_ADDRESS>"
                f"<START_IP>{p['start']}</START_IP><END_IP>{p['end']}</END_IP><DNS_SERVER>172.16.5.130</DNS_SERVER>"
                f"<MAX_USERS>{p['max']}</MAX_USERS><DOMAIN_NAME>{DOMAIN}</DOMAIN_NAME><DHCP_POOL_LEASES/>"
                "<LEASE_TIME>86400000</LEASE_TIME><WLC_ADDRESS>0.0.0.0</WLC_ADDRESS></POOL>")
    def fn(b):
        s = b.index("<DHCP_SERVERS>"); e = b.index("</DHCP_SERVERS>", s)
        d = b[s:e]
        d = re.sub(r"(<DHCP_SERVER>\s*<ENABLED>)\d(</ENABLED>)", r"\g<1>1\2", d, count=1)
        d = re.sub(r"<POOLS>.*?</POOLS>", "<POOLS>" + "".join(pool(p) for p in pools) + "</POOLS>", d, count=1, flags=re.S)
        return b[:s] + d + b[e:]
    edit(name, fn)

def dhcp_client(name, gw6):
    """PC: IPv4 por DHCP y IPv6 por DHCPv6 (stateful)."""
    def fn(b):
        s, e = first_eth_port(b)
        p = b[s:e]
        p = set_tag(p, "IP", ""); p = set_tag(p, "SUBNET", "")
        p = set_tag(p, "PORT_DHCP_ENABLE", "true")
        p = set_tag(p, "IPV6_ENABLED", "true")
        p = set_tag(p, "IPV6_ADDRESS_AUTOCONFIG", "false")
        p = set_tag(p, "IPV6_PORT_DHCP_ENABLED", "true")
        p = set_tag(p, "IPV6_PORT_GATEWAY", gw6)
        b = b[:s] + p + b[e:]
        b = set_tag(b, "GATEWAYV6", gw6)
        entry = ("<PORT><PORT_NAME>FastEthernet0</PORT_NAME><DHCPV6_CLIENT><IAID>1</IAID><STATE>0</STATE>"
                 "<DHCPV6_CLIENT_PORT_DATA><ENABLED>1</ENABLED><RAPID_COMMIT>0</RAPID_COMMIT><HINT>0</HINT>"
                 "<PREFIX_NAME></PREFIX_NAME><INITIAL_SOLICIT_TIME></INITIAL_SOLICIT_TIME><LAST_SOLICIT_TIME></LAST_SOLICIT_TIME>"
                 "<PRERX_SOLICIT_TIME>0</PRERX_SOLICIT_TIME><SOLICIT_MSG_COUNT>0</SOLICIT_MSG_COUNT>"
                 "<INITIAL_REQUEST_TIME></INITIAL_REQUEST_TIME><LAST_REQUEST_TIME></LAST_REQUEST_TIME>"
                 "<REQUEST_MSG_COUNT>0</REQUEST_MSG_COUNT></DHCPV6_CLIENT_PORT_DATA></DHCPV6_CLIENT></PORT>")
        b = re.sub(r"<ENABLED_PORTS\s*/>|<ENABLED_PORTS>.*?</ENABLED_PORTS>", "<ENABLED_PORTS>" + entry + "</ENABLED_PORTS>",
                   b, count=1, flags=re.S)
        return b
    edit(name, fn)

# ---------------- DMZ (solo IPv6) ----------------
static_host("Web_Server", ip6=WEB6, gw6="FE80::1", dns6=DNS6)
static_host("DNS_Server", ip6=DNS6, gw6="FE80::1", dns6=DNS6)
static_host("Tracker_Server", ip6=TRK6, gw6="FE80::1", dns6=DNS6)
services("Web_Server", http=True, https=True, dns=[])
services("DNS_Server", http=False, https=False, dns=[
    ("www." + DOMAIN, WEB6), (DOMAIN, WEB6), ("tracker." + DOMAIN, TRK6), ("dns." + DOMAIN, DNS6)])
services("Tracker_Server", http=False, https=False, dns=[])  # el puerto 80 lo usa el programa Tracker Relay
http_index("Web_Server", open(os.path.join(HERE, "web", "index.html")).read())

# ---------------- Bogota VLAN 30 ----------------
static_host("DHCP_Server", "172.16.5.130", "255.255.255.240", "172.16.5.129",
            "2001:1200:EA15:30::10", "FE80::1", DNS6)
# DNS interno (secundario) en DHCP_Server: atiende por IPv4 a los clientes doble pila y
# responde los mismos registros AAAA del DNS de la DMZ.
services("DHCP_Server", http=False, https=False, dns=[
    ("www." + DOMAIN, WEB6), (DOMAIN, WEB6), ("tracker." + DOMAIN, TRK6), ("dns." + DOMAIN, DNS6)])
dhcp_pools("DHCP_Server", [
    dict(name="serverPool", net="172.16.5.0", mask="255.255.255.224", gw="172.16.5.1",
         start="172.16.5.10", end="172.16.5.30", max=21),
    dict(name="BOG_INTERNAL_20", net="172.16.5.32", mask="255.255.255.224", gw="172.16.5.33",
         start="172.16.5.42", end="172.16.5.62", max=21),
    dict(name="MAD_GUEST_40", net="172.16.5.64", mask="255.255.255.224", gw="172.16.5.65",
         start="172.16.5.74", end="172.16.5.94", max=21),
    dict(name="MAD_INTERNAL_50", net="172.16.5.96", mask="255.255.255.224", gw="172.16.5.97",
         start="172.16.5.106", end="172.16.5.126", max=21),
])
static_host("Printer0", "172.16.5.131", "255.255.255.240", "172.16.5.129", "2001:1200:EA15:30::31", "FE80::1", DNS6)
static_host("Printer1", "172.16.5.132", "255.255.255.240", "172.16.5.129", "2001:1200:EA15:30::32", "FE80::1", DNS6)
# ---------------- Madrid VLAN 60 ----------------
static_host("Printer2", "172.16.5.146", "255.255.255.240", "172.16.5.145", "2001:1200:EB25:60::46", "FE80::3", DNS6)
static_host("Printer3", "172.16.5.147", "255.255.255.240", "172.16.5.145", "2001:1200:EB25:60::47", "FE80::3", DNS6)
# ---------------- PCs ----------------
for i in range(1, 9):
    dhcp_client(f"PC{i}", "FE80::1" if i <= 4 else "FE80::3")

def project(name, proj, code, run=True, replace=False):
    """Inserta/reemplaza un proyecto de programacion (carpeta en Dev:) y lo deja en ejecucion."""
    def fn(b):
        txt = html.escape(code, quote=False)
        if replace:
            pos = 0
            while True:
                i = b.find(f"<NAME>{proj}</NAME>", pos)
                if i < 0:
                    break
                i = b.index("<NAME>main.py</NAME>", i)
                s = b.index("<TEXT>", i) + len("<TEXT>")
                e = b.index("</TEXT>", s)
                b = b[:s] + txt + b[e:]
                pos = s + len(txt)
        elif f"<NAME>{proj}</NAME>" in b:
            i = b.index(f"<NAME>{proj}</NAME>")
            i = b.index("<NAME>main.py</NAME>", i)
            s = b.index("<TEXT>", i) + len("<TEXT>")
            e = b.index("</TEXT>", s)
            b = b[:s] + txt + b[e:]
        else:
            d = b.index("<NAME>Dev:</NAME>")
            f = b.index("<FILES", d)
            entry = ('<FILE class="CDirectory"><FILE_NUMBER>1</FILE_NUMBER><NAME>' + proj + '</NAME>'
                     '<DATE_TIME>0</DATE_TIME><PERMISSION>6</PERMISSION><FILE_CONTENT/><FILES>'
                     '<FILE class="CFile"><FILE_NUMBER>2</FILE_NUMBER><NAME>main.py</NAME><DATE_TIME>0</DATE_TIME>'
                     '<PERMISSION>6</PERMISSION><FILE_CONTENT class="CTextFileContent"><TEXT>' + txt +
                     '</TEXT></FILE_CONTENT></FILE></FILES></FILE>')
            if b.startswith("<FILES/>", f):
                b = b[:f] + "<FILES>" + entry + "</FILES>" + b[f + len("<FILES/>"):]
            else:
                g = f + len("<FILES>")
                b = b[:g] + entry + b[g:]
            c = b.index("<FILE_COUNTER>", d)
            ce = b.index("</FILE_COUNTER>", c)
            b = b[:c] + "<FILE_COUNTER>2" + b[ce:]
        if run:
            b = re.sub(r"<RUNNING_APPS\s*/>|<RUNNING_APPS>.*?</RUNNING_APPS>",
                       f"<RUNNING_APPS><USER_APP>{proj}</USER_APP></RUNNING_APPS>", b, count=1, flags=re.S)
        return b
    edit(name, fn)

def bt_on(name):
    def fn(b):
        i = b.index("<BLUETOOTH_PORT>")
        j = b.index("</BLUETOOTH_PORT>", i)
        seg = re.sub(r"<POWER>false</POWER>", "<POWER>true</POWER>", b[i:j], count=1)
        return b[:i] + seg + b[j:]
    edit(name, fn)

def move_physical(name, x, x_pn):
    global doc
    i = doc.index(f'<NAME translate="true">{name}</NAME>')
    s = doc.index("<PHYSICAL_CPUR>", i)
    e = doc.index("</PHYSICAL_CPUR>", s)
    seg = doc[s:e]
    seg = re.sub(r"<X_PN>[^<]*</X_PN>", f"<X_PN>{x_pn}</X_PN>", seg, count=1)
    seg = re.sub(r"<X>[^<]*</X>", f"<X>{x}</X>", seg, count=1)
    doc = doc[:s] + seg + doc[e:]

bt_on("PC4")
bt_on("Beacon_Employee")

T = os.path.join(HERE, "tracker")
project("Beacon_Employee", "Beacon (Python)", open(os.path.join(T, "beacon_main.py")).read(), replace=True)
project("PC4", "TrackerApp (Python)", open(os.path.join(T, "tracker_app_main.py")).read())
project("Tracker_Server", "TrackerRelay (Python)", open(os.path.join(T, "tracker_relay_main.py")).read())
project("PC7", "TrackerDashboard (Python)", open(os.path.join(T, "tracker_dashboard_main.py")).read())

out = doc.encode("utf-8")
import xml.etree.ElementTree as ET
ET.fromstring(out)
open(DST + ".xml", "wb").write(out)
open(DST, "wb").write(pkt.encode(out))
print("ok", DST)
