#!/usr/bin/env python3
"""Compara los running-config guardados en el .pkt con las configuraciones deseadas."""
import sys, re, os
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pkt

raw = open(sys.argv[1], "rb").read()
x = pkt.decode(raw)
open(sys.argv[1] + ".xml", "wb").write(x)
root = ET.fromstring(x)
OUT = os.path.join(os.path.dirname(__file__), "running")
os.makedirs(OUT, exist_ok=True)
SKIP = {"enable", "configure terminal", "exit", "end", "write memory", "no", ""}
for d in root.find("NETWORK/DEVICES"):
    e = d.find("ENGINE")
    name = e.find("NAME").text
    rc = e.find("RUNNINGCONFIG")
    if rc is None:
        continue
    lines = [l.text or "" for l in rc.findall("LINE")]
    open(os.path.join(OUT, name + ".txt"), "w").write("\n".join(lines) + "\n")
    want = os.path.join(os.path.dirname(__file__), "configs", name + ".txt")
    if not os.path.exists(want):
        continue
    run = set(l.strip() for l in lines)
    missing = []
    for l in open(want).read().replace("\r", "").split("\n"):
        s = l.strip()
        if s in SKIP or s.startswith(("password ", "enable secret", "crypto key generate", "username ",
                                      "banner motd", "secret")):
            continue
        if s.startswith("interface range"):
            continue
        if s not in run:
            missing.append(s)
    print(f"== {name}: {len(missing)} lineas no encontradas")
    for m in missing:
        print("   ", m)
