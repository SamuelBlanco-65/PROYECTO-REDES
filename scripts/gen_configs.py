#!/usr/bin/env python3
"""Genera las configuraciones CLI de todos los equipos del Proyecto Final RCD.
Fuente única de verdad del diseño: X=5, dominio sslmjp.net."""
import os, json

X = 5
OUT = os.path.join(os.path.dirname(__file__), "configs")
os.makedirs(OUT, exist_ok=True)

DOMAIN = "sslmjp.net"
ENABLE_SECRET = "RcdClass2026"
LINE_PASS = "RcdLine2026"
VPN_KEY = "RcdVpnKey2026"
SNMP_RO = "RCD_RO"
SNMP_RW = "RCD_RW"
EIGRP_AS = 55
BANNER = "Acceso restringido - Proyecto Final RCD - Equipo 5"

# ---------------- IPv4 Internet (86.106.76+X.0/24) -----------------
NET = f"86.106.{76+X}"
L = {  # nombre: (red, ipA, ipB)  A = primer equipo listado
    "R1-ISPBOG":   (f"{NET}.0",  f"{NET}.2",  f"{NET}.1"),
    "ISPBOG-NET":  (f"{NET}.4",  f"{NET}.5",  f"{NET}.6"),
    "ISPBOG-FL":   (f"{NET}.8",  f"{NET}.9",  f"{NET}.10"),
    "NET-ESP":     (f"{NET}.12", f"{NET}.13", f"{NET}.14"),
    "NET-FL":      (f"{NET}.16", f"{NET}.17", f"{NET}.18"),
    "FL-ESP":      (f"{NET}.20", f"{NET}.21", f"{NET}.22"),
    "ESP-R2":      (f"{NET}.24", f"{NET}.25", f"{NET}.26"),
}
M30 = "255.255.255.252"
W30 = "0.0.0.3"

# ---------------- IPv6 -----------------
BOG6 = f"2001:1200:EA1{X}"
MAD6 = f"2001:1200:EB2{X}"
DMZ6 = f"2001:1200:EC1{X}"
LO6 = f"2001:1200:ED1{X}"
ESP6 = f"2001:1200:ED2{X}"
WEB6 = f"{DMZ6}:1::10"
DNS6 = f"{DMZ6}:1::53"
TRK6 = f"{DMZ6}:1::30"

# ---------------- IPv4 privada intranets (VLSM 172.16.X.0/24) ------
P = f"172.16.{X}"
DHCP4 = f"{P}.130"

def hdr(name):
    return ["enable", "configure terminal", f"hostname {name}", "no ip domain-lookup",
            f"ip domain-name {DOMAIN}", f"enable secret {ENABLE_SECRET}",
            "service password-encryption", f"banner motd #{BANNER}#"]

def lines_sec(ssh=False):
    out = ["line console 0", f"password {LINE_PASS}", "login", "logging synchronous", "exit"]
    if ssh:
        out += ["username admin privilege 15 secret " + ENABLE_SECRET,
                "crypto key generate rsa general-keys modulus 1024", "ip ssh version 2",
                "line vty 0 4", "login local", "transport input ssh", "exit"]
    else:
        out += ["line vty 0 4", f"password {LINE_PASS}", "login", "exit"]
    return out

def end():
    return ["end", "write memory"]

def serial(ifname, ip, desc, clock=True):
    c = [f"interface {ifname}", f"description {desc}", f"ip address {ip} {M30}"]
    if clock:
        c.append("clock rate 2000000")
    c += ["no shutdown", "exit"]
    return c

cfg = {}

# =================== ISP routers (IPv4 only) =======================
# ISP_BOG: S0/0/0 -> R1_BOG ; S0/0/1 -> ISP_NET ; S0/1/0 -> ISP_FL
c = hdr("ISP_BOG") + lines_sec()
c += serial("Serial0/0/0", L["R1-ISPBOG"][2], "Enlace a R1_BOG (cliente Bogota)")
c += serial("Serial0/0/1", L["ISPBOG-NET"][1], "Enlace a ISP_NET (EIGRP)")
c += serial("Serial0/2/0", L["ISPBOG-FL"][1], "Enlace a ISP_FL (OSPF)")
c += ["interface Loopback0", f"ip address {NET}.241 255.255.255.255", "exit",
      f"router eigrp {EIGRP_AS}", "no auto-summary",
      f"network {L['ISPBOG-NET'][0]} {W30}", f"network {L['R1-ISPBOG'][0]} {W30}",
      "passive-interface Serial0/0/0",
      "redistribute ospf 1 metric 1544 2000 255 1 1500", "exit",
      "router ospf 1", f"router-id {NET}.241",
      f"network {L['ISPBOG-FL'][0]} {W30} area 0",
      f"redistribute eigrp {EIGRP_AS} subnets", "exit"]
cfg["ISP_BOG"] = c + end()

# ISP_NET: S0/0/0 -> ISP_BOG ; S0/0/1 -> ISP_ESP ; S0/1/0 -> ISP_FL
c = hdr("ISP_NET") + lines_sec()
c += serial("Serial0/0/0", L["ISPBOG-NET"][2], "Enlace a ISP_BOG (EIGRP)", clock=False)
c += serial("Serial0/0/1", L["NET-ESP"][1], "Enlace a ISP_ESP (EIGRP)")
c += serial("Serial0/2/0", L["NET-FL"][1], "Enlace a ISP_FL (OSPF)")
c += ["interface Loopback0", f"ip address {NET}.242 255.255.255.255", "exit",
      f"router eigrp {EIGRP_AS}", "no auto-summary",
      f"network {L['ISPBOG-NET'][0]} {W30}", f"network {L['NET-ESP'][0]} {W30}", "exit",
      "router ospf 1", f"router-id {NET}.242",
      f"network {L['NET-FL'][0]} {W30} area 0", "exit"]
cfg["ISP_NET"] = c + end()

# ISP_FL: S0/0/0 -> ISP_BOG ; S0/0/1 -> ISP_NET ; S0/1/0 -> ISP_ESP
c = hdr("ISP_FL") + lines_sec()
c += serial("Serial0/0/0", L["ISPBOG-FL"][2], "Enlace a ISP_BOG (OSPF)", clock=False)
c += serial("Serial0/0/1", L["NET-FL"][2], "Enlace a ISP_NET (OSPF)", clock=False)
c += serial("Serial0/2/0", L["FL-ESP"][1], "Enlace a ISP_ESP (OSPF)")
c += ["interface Loopback0", f"ip address {NET}.243 255.255.255.255", "exit",
      "router ospf 1", f"router-id {NET}.243",
      f"network {L['ISPBOG-FL'][0]} {W30} area 0",
      f"network {L['NET-FL'][0]} {W30} area 0",
      f"network {L['FL-ESP'][0]} {W30} area 0", "exit"]
cfg["ISP_FL"] = c + end()

# ISP_ESP: S0/0/0 -> ISP_NET ; S0/0/1 -> ISP_FL ; S0/1/0 -> R2_ESP
c = hdr("ISP_ESP") + lines_sec()
c += serial("Serial0/0/0", L["NET-ESP"][2], "Enlace a ISP_NET (EIGRP)", clock=False)
c += serial("Serial0/0/1", L["FL-ESP"][2], "Enlace a ISP_FL (OSPF)", clock=False)
c += serial("Serial0/2/0", L["ESP-R2"][1], "Enlace a R2_ESP (cliente Madrid)")
c += ["interface Loopback0", f"ip address {NET}.244 255.255.255.255", "exit",
      f"router eigrp {EIGRP_AS}", "no auto-summary",
      f"network {L['NET-ESP'][0]} {W30}", f"network {L['ESP-R2'][0]} {W30}",
      "passive-interface Serial0/2/0",
      "redistribute ospf 1 metric 1544 2000 255 1 1500", "exit",
      "router ospf 1", f"router-id {NET}.244",
      f"network {L['FL-ESP'][0]} {W30} area 0",
      f"redistribute eigrp {EIGRP_AS} subnets", "exit"]
cfg["ISP_ESP"] = c + end()

# =================== VPN common ===================================
def vpn(local_pub, peer_pub, wan_if):
    return ["crypto isakmp policy 10", "encryption aes 256", "hash sha", "authentication pre-share",
            "group 5", "lifetime 86400", "exit",
            f"crypto isakmp key {VPN_KEY} address {peer_pub}",
            "crypto ipsec transform-set TS-RCD esp-aes 256 esp-sha-hmac",
            "access-list 110 remark Trafico de los tuneles GRE y 6in4 protegido por IPsec",
            f"access-list 110 permit ip host {local_pub} host {peer_pub}",
            "crypto map VPN-RCD 10 ipsec-isakmp", f"set peer {peer_pub}",
            "set transform-set TS-RCD", "match address 110", "exit",
            f"interface {wan_if}", "crypto map VPN-RCD", "exit"]

# SNMP: ACL IPv4 de bloqueo para invitados y servidores (solo VLAN interna gestiona)
def snmp_block_acl(name, internal_net, internal_wc, mgmt_targets):
    """ACL extendida aplicada IN en las VLAN que NO deben gestionar.
    Bloquea SNMP (161/162) y permite el resto."""
    return [f"ip access-list extended {name}",
            "remark Bloquea SNMP desde VLAN no autorizadas",
            "deny udp any any eq snmp", "deny udp any any eq 162",
            "permit ip any any", "exit"]

def snmp_internal_acl(name, own_net, own_wc):
    """VLAN interna: solo puede hacer SNMP a los equipos de su propia intranet."""
    return [f"ip access-list extended {name}",
            "remark VLAN interna: SNMP solo hacia su propia intranet",
            f"permit udp any {own_net} {own_wc} eq snmp",
            "deny udp any any eq snmp", "deny udp any any eq 162",
            "permit ip any any", "exit"]

def snmp_server(loc):
    return [f"snmp-server community {SNMP_RO} RO", f"snmp-server community {SNMP_RW} RW"]

WEB_ACL6 = ["ipv6 access-list WEB-POLICY",
            f"permit tcp {BOG6}:10::/64 host {WEB6} eq www",
            f"deny tcp {BOG6}:10::/64 host {WEB6} eq 443",
            f"permit tcp {BOG6}:20::/64 host {WEB6} eq 443",
            f"deny tcp {BOG6}:20::/64 host {WEB6} eq www",
            f"permit tcp {MAD6}:40::/64 host {WEB6} eq www",
            f"deny tcp {MAD6}:40::/64 host {WEB6} eq 443",
            f"permit tcp {MAD6}:50::/64 host {WEB6} eq 443",
            f"deny tcp {MAD6}:50::/64 host {WEB6} eq www",
            "permit ipv6 any any", "exit"]

# =================== R1_BOG =======================================
c = hdr("R1_BOG") + lines_sec(ssh=True) + ["ipv6 unicast-routing"]
c += snmp_block_acl("SNMP-BLOCK", None, None, None)
c += ["ip access-list extended SNMP-INT-BOG", "remark VLAN interna: SNMP solo hacia su propia intranet",
      f"permit udp any {P}.0 0.0.0.63 eq snmp", f"permit udp any {P}.128 0.0.0.15 eq snmp",
      f"permit udp any host 10.255.{X}.1 eq snmp",
      "deny udp any any eq snmp", "deny udp any any eq 162", "permit ip any any", "exit"]
c += WEB_ACL6
c += ["ipv6 dhcp pool DHCPV6-BOG-G10", f"address prefix {BOG6}:10::/64 lifetime 172800 86400",
      f"dns-server {DNS6}", f"domain-name {DOMAIN}", "exit",
      "ipv6 dhcp pool DHCPV6-BOG-I20", f"address prefix {BOG6}:20::/64 lifetime 172800 86400",
      f"dns-server {DNS6}", f"domain-name {DOMAIN}", "exit",
      "ipv6 dhcp pool DHCPV6-BOG-S30", f"dns-server {DNS6}", f"domain-name {DOMAIN}", "exit"]
c += ["interface Loopback0", "description Gestion / router-id", f"ip address 10.255.{X}.1 255.255.255.255",
      f"ipv6 address {LO6}::1/128", "exit"]
c += ["interface FastEthernet0/0", "description DMZ (solo IPv6)", "no ip address",
      f"ipv6 address {DMZ6}:1::1/64", "ipv6 address FE80::1 link-local",
      "ipv6 traffic-filter WEB-POLICY out", "no shutdown", "exit"]
c += ["interface FastEthernet0/1", "description Trunk a SW1_Intranet", "no ip address", "no shutdown", "exit",
      "interface FastEthernet0/1.10", "description VLAN 10 GUEST_BOG", "encapsulation dot1Q 10",
      f"ip address {P}.1 255.255.255.224", f"ip helper-address {DHCP4}", "ip access-group SNMP-BLOCK in",
      f"ipv6 address {BOG6}:10::1/64", "ipv6 address FE80::1 link-local",
      "ipv6 nd managed-config-flag", "ipv6 nd other-config-flag", "ipv6 dhcp server DHCPV6-BOG-G10", "exit",
      "interface FastEthernet0/1.20", "description VLAN 20 INTERNAL_BOG", "encapsulation dot1Q 20",
      f"ip address {P}.33 255.255.255.224", f"ip helper-address {DHCP4}", "ip access-group SNMP-INT-BOG in",
      f"ipv6 address {BOG6}:20::1/64", "ipv6 address FE80::1 link-local",
      "ipv6 nd managed-config-flag", "ipv6 nd other-config-flag", "ipv6 dhcp server DHCPV6-BOG-I20", "exit",
      "interface FastEthernet0/1.30", "description VLAN 30 SRV_PRN_BOG", "encapsulation dot1Q 30",
      f"ip address {P}.129 255.255.255.240", "ip access-group SNMP-BLOCK in",
      f"ipv6 address {BOG6}:30::1/64", "ipv6 address FE80::1 link-local",
      "ipv6 nd other-config-flag", "ipv6 dhcp server DHCPV6-BOG-S30", "exit",
      "interface FastEthernet0/1.99", "description VLAN 99 NATIVE_BOG", "encapsulation dot1Q 99 native", "exit"]
c += serial("Serial0/0/0", L["R1-ISPBOG"][1], "WAN a ISP_BOG (Internet IPv4)", clock=False)
c += ["interface Tunnel0", f"ip address {P}.161 {M30}", "tunnel source Serial0/0/0", f"tunnel destination {L['ESP-R2'][2]}",
      "tunnel mode gre ip", "no shutdown", "exit",
      "interface Tunnel1", f"ipv6 address {DMZ6}:FF::1/64", "ipv6 address FE80::1 link-local",
      "tunnel source Serial0/0/0", f"tunnel destination {L['ESP-R2'][2]}",
      "tunnel mode ipv6ip", "no shutdown", "exit"]
c += vpn(L["R1-ISPBOG"][1], L["ESP-R2"][2], "Serial0/0/0")
c += [f"ip route 0.0.0.0 0.0.0.0 {L['R1-ISPBOG'][2]}",
      "router ospf 10", "router-id 1.1.1.1",
      f"network {P}.0 0.0.0.31 area 0", f"network {P}.32 0.0.0.31 area 0",
      f"network {P}.128 0.0.0.15 area 0", f"network {P}.160 0.0.0.3 area 0",
      f"network 10.255.{X}.1 0.0.0.0 area 0",
      "passive-interface FastEthernet0/1.10", "passive-interface FastEthernet0/1.20",
      "passive-interface FastEthernet0/1.30", "exit",
      "ipv6 router ospf 10", "router-id 1.1.1.1", "exit"]
for i in ["Loopback0", "FastEthernet0/0", "FastEthernet0/1.10", "FastEthernet0/1.20", "FastEthernet0/1.30", "Tunnel1"]:
    c += [f"interface {i}", "ipv6 ospf 10 area 0", "exit"]
c += snmp_server("Bogota - R1_BOG")
cfg["R1_BOG"] = c + end()

# =================== R2_ESP =======================================
c = hdr("R2_ESP") + lines_sec(ssh=True) + ["ipv6 unicast-routing"]
c += ["interface Loopback0", "description Gestion / router-id", f"ip address 10.255.{X}.2 255.255.255.255",
      f"ipv6 address {LO6}::2/128", "exit",
      "interface FastEthernet0/0", "description Enlace enrutado a MLSW_MAD",
      f"ip address {P}.165 {M30}", f"ipv6 address {ESP6}:1::1/64", "ipv6 address FE80::2 link-local",
      "no shutdown", "exit"]
c += serial("Serial0/2/0", L["ESP-R2"][2], "WAN a ISP_ESP (Internet IPv4)", clock=False)
c += ["interface Tunnel0", f"ip address {P}.162 {M30}", "tunnel source Serial0/2/0", f"tunnel destination {L['R1-ISPBOG'][1]}",
      "tunnel mode gre ip", "no shutdown", "exit",
      "interface Tunnel1", f"ipv6 address {DMZ6}:FF::2/64", "ipv6 address FE80::2 link-local",
      "tunnel source Serial0/2/0", f"tunnel destination {L['R1-ISPBOG'][1]}",
      "tunnel mode ipv6ip", "no shutdown", "exit"]
c += vpn(L["ESP-R2"][2], L["R1-ISPBOG"][1], "Serial0/2/0")
c += [f"ip route 0.0.0.0 0.0.0.0 {L['ESP-R2'][1]}",
      "router ospf 10", "router-id 2.2.2.2",
      f"network {P}.164 0.0.0.3 area 0", f"network {P}.160 0.0.0.3 area 0",
      f"network 10.255.{X}.2 0.0.0.0 area 0", "exit",
      "ipv6 router ospf 10", "router-id 2.2.2.2", "exit"]
for i in ["Loopback0", "FastEthernet0/0", "Tunnel1"]:
    c += [f"interface {i}", "ipv6 ospf 10 area 0", "exit"]
c += snmp_server("Madrid - R2_ESP")
cfg["R2_ESP"] = c + end()

# =================== MLSW_MAD (3650) ==============================
c = hdr("MLSW_MAD") + lines_sec(ssh=True) + ["ip routing", "ipv6 unicast-routing"]
c += ["vlan 40", "name GUEST_MAD", "exit", "vlan 50", "name INTERNAL_MAD", "exit",
      "vlan 60", "name SRV_PRN_MAD", "exit", "vlan 98", "name NATIVE_MAD", "exit",
      "spanning-tree mode rapid-pvst", "spanning-tree vlan 40,50,60,98 root primary"]
c += snmp_block_acl("SNMP-BLOCK", None, None, None)
c += [f"ip access-list extended SNMP-INT-MAD", "remark VLAN interna: SNMP solo hacia su propia intranet",
      f"permit udp any {P}.64 0.0.0.63 eq snmp", f"permit udp any {P}.144 0.0.0.15 eq snmp",
      f"permit udp any {P}.164 0.0.0.3 eq snmp", f"permit udp any host 10.255.{X}.2 eq snmp",
      f"permit udp any host 10.255.{X}.3 eq snmp",
      "deny udp any any eq snmp", "deny udp any any eq 162", "permit ip any any", "exit"]
c += ["ipv6 dhcp pool DHCPV6-MAD-G40", f"address prefix {MAD6}:40::/64 lifetime 172800 86400",
      f"dns-server {DNS6}", f"domain-name {DOMAIN}", "exit",
      "ipv6 dhcp pool DHCPV6-MAD-I50", f"address prefix {MAD6}:50::/64 lifetime 172800 86400",
      f"dns-server {DNS6}", f"domain-name {DOMAIN}", "exit",
      "ipv6 dhcp pool DHCPV6-MAD-S60", f"dns-server {DNS6}", f"domain-name {DOMAIN}", "exit"]
c += ["interface Loopback0", "description Gestion / router-id", f"ip address 10.255.{X}.3 255.255.255.255",
      f"ipv6 address {LO6}::3/128", "exit",
      "interface GigabitEthernet1/0/1", "description Enlace enrutado a R2_ESP", "no switchport",
      f"ip address {P}.166 {M30}", f"ipv6 address {ESP6}:1::2/64", "ipv6 address FE80::3 link-local",
      "no shutdown", "exit",
      "interface range GigabitEthernet1/0/2 - 3", "description Trunk a SW4/SW5",
      "switchport mode trunk", "switchport trunk native vlan 98",
      "switchport trunk allowed vlan 40,50,60,98", "switchport nonegotiate", "no shutdown", "exit",
      "interface Vlan40", "description GUEST_MAD", f"ip address {P}.65 255.255.255.224",
      f"ip helper-address {DHCP4}", "ip access-group SNMP-BLOCK in",
      f"ipv6 address {MAD6}:40::1/64", "ipv6 address FE80::3 link-local",
      "ipv6 nd managed-config-flag", "ipv6 nd other-config-flag", "ipv6 dhcp server DHCPV6-MAD-G40",
      "no shutdown", "exit",
      "interface Vlan50", "description INTERNAL_MAD", f"ip address {P}.97 255.255.255.224",
      f"ip helper-address {DHCP4}", "ip access-group SNMP-INT-MAD in",
      f"ipv6 address {MAD6}:50::1/64", "ipv6 address FE80::3 link-local",
      "ipv6 nd managed-config-flag", "ipv6 nd other-config-flag", "ipv6 dhcp server DHCPV6-MAD-I50",
      "no shutdown", "exit",
      "interface Vlan60", "description SRV_PRN_MAD", f"ip address {P}.145 255.255.255.240",
      "ip access-group SNMP-BLOCK in",
      f"ipv6 address {MAD6}:60::1/64", "ipv6 address FE80::3 link-local",
      "ipv6 nd other-config-flag", "ipv6 dhcp server DHCPV6-MAD-S60", "no shutdown", "exit"]
c += ["router ospf 10", "router-id 3.3.3.3",
      f"network {P}.64 0.0.0.31 area 0", f"network {P}.96 0.0.0.31 area 0",
      f"network {P}.144 0.0.0.15 area 0", f"network {P}.164 0.0.0.3 area 0",
      f"network 10.255.{X}.3 0.0.0.0 area 0",
      "passive-interface Vlan40", "passive-interface Vlan50", "passive-interface Vlan60", "exit",
      "ipv6 router ospf 10", "router-id 3.3.3.3", "exit"]
for i in ["Loopback0", "GigabitEthernet1/0/1", "Vlan40", "Vlan50", "Vlan60"]:
    c += [f"interface {i}", "ipv6 ospf 10 area 0", "exit"]
c += snmp_server("Madrid - MLSW_MAD")
cfg["MLSW_MAD"] = c + end()

# =================== 2960 switches ================================
def sw(name, vlans, native, mgmt_vlan, mgmt_ip, mgmt_mask, gw, trunks, access, loc, root=False):
    c = hdr(name) + lines_sec()
    for vid, vname in vlans:
        c += [f"vlan {vid}", f"name {vname}", "exit"]
    c += ["spanning-tree mode rapid-pvst"]
    if root:
        c += ["spanning-tree vlan " + ",".join(str(v) for v, _ in vlans) + " root primary"]
    for t in trunks:
        c += [f"interface {t}", "switchport mode trunk", f"switchport trunk native vlan {native}",
              "switchport trunk allowed vlan " + ",".join(str(v) for v, _ in vlans),
              "switchport nonegotiate", "no shutdown", "exit"]
    for port, vid, desc in access:
        c += [f"interface {port}", f"description {desc}", "switchport mode access",
              f"switchport access vlan {vid}", "spanning-tree portfast", "spanning-tree bpduguard enable",
              "no shutdown", "exit"]
    if mgmt_ip:
        c += [f"interface Vlan{mgmt_vlan}", "description Gestion (SNMP)", f"ip address {mgmt_ip} {mgmt_mask}",
              "no shutdown", "exit", f"ip default-gateway {gw}"]
        c += snmp_server(loc)
    return c + end()

BOGV = [(10, "GUEST_BOG"), (20, "INTERNAL_BOG"), (30, "SRV_PRN_BOG"), (99, "NATIVE_BOG")]
MADV = [(40, "GUEST_MAD"), (50, "INTERNAL_MAD"), (60, "SRV_PRN_MAD"), (98, "NATIVE_MAD")]
M28 = "255.255.255.240"
cfg["SW1_Intranet"] = sw("SW1_Intranet", BOGV, 99, 30, f"{P}.135", M28, f"{P}.129",
    ["GigabitEthernet0/1", "FastEthernet0/2", "FastEthernet0/3"], [], "Bogota - SW1", root=True)
cfg["SW2_Intranet"] = sw("SW2_Intranet", BOGV, 99, 30, f"{P}.136", M28, f"{P}.129",
    ["FastEthernet0/1", "FastEthernet0/2"],
    [("FastEthernet0/10", 30, "DHCP_Server"), ("FastEthernet0/11", 10, "PC1 invitado"),
     ("FastEthernet0/12", 20, "PC2 interno")], "Bogota - SW2")
cfg["SW3_Intranet"] = sw("SW3_Intranet", BOGV, 99, 30, f"{P}.137", M28, f"{P}.129",
    ["FastEthernet0/1", "FastEthernet0/2"],
    [("FastEthernet0/11", 10, "PC3 invitado"), ("FastEthernet0/12", 20, "PC4 interno - Tracker App"),
     ("FastEthernet0/20", 30, "Printer0"), ("FastEthernet0/21", 30, "Printer1")], "Bogota - SW3")
cfg["SW4_Intranet"] = sw("SW4_Intranet", MADV, 98, 60, f"{P}.150", M28, f"{P}.145",
    ["GigabitEthernet0/1", "FastEthernet0/1"],
    [("FastEthernet0/10", 60, "Printer2"), ("FastEthernet0/11", 40, "PC5 invitado"),
     ("FastEthernet0/12", 50, "PC6 interno")], "Madrid - SW4")
cfg["SW5_Intranet"] = sw("SW5_Intranet", MADV, 98, 60, f"{P}.151", M28, f"{P}.145",
    ["GigabitEthernet0/1", "FastEthernet0/1"],
    [("FastEthernet0/11", 50, "PC7 interno - Tracker Dashboard"), ("FastEthernet0/12", 40, "PC8 invitado"),
     ("FastEthernet0/20", 60, "Printer3")], "Madrid - SW5")
# SW_DMZ: capa 2 plano, solo IPv6 en hosts; sin IP de gestion
c = hdr("SW_DMZ") + lines_sec() + ["vlan 70", "name DMZ", "exit", "spanning-tree mode rapid-pvst"]
for port, desc in [("GigabitEthernet0/1", "Uplink R1_BOG Fa0/0"), ("FastEthernet0/1", "Web_Server"),
                   ("FastEthernet0/2", "DNS_Server"), ("FastEthernet0/3", "Tracker_Server")]:
    c += [f"interface {port}", f"description {desc}", "switchport mode access", "switchport access vlan 70"]
    if port.startswith("Fast"):
        c += ["spanning-tree portfast", "spanning-tree bpduguard enable"]
    c += ["no shutdown", "exit"]
cfg["SW_DMZ"] = c + end()

for name, lines in cfg.items():
    with open(os.path.join(OUT, f"{name}.txt"), "w", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")
print("OK", len(cfg), "configs ->", OUT)
