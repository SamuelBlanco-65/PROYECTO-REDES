from tcp import *
from time import *

# Tracker Dashboard (PC7 - Intranet MAD)
# Se suscribe al Tracker Relay, muestra en tiempo real la ubicacion y actividad
# de los empleados y genera alertas:
#  - permanencia > 60 s en la zona restringida (Sala de servidores: X 70-100, Y 70-100)
#  - cambio brusco de "En reposo" a "Alta actividad"
# Las alertas se envian tambien al Relay (ALR|...), que publica el tablero web (bonus)
# consultado desde el Web Browser de PC7: http://tracker.sslmjp.net
RELAY_IP = "2001:1200:EC15:1::30"
RELAY_PORT = 5001
ZONA = {"nombre": "Sala de servidores", "x1": 70.0, "x2": 100.0, "y1": 70.0, "y2": 100.0}
LIMITE_ZONA = 60

emp = {}
alertas = []
st = {"rx": "", "total": 0}
conn = {"c": None}

def ok_conn():
    try:
        return conn["c"] is not None and conn["c"].connected()
    except Exception:
        return False

def en_zona(x, y):
    return ZONA["x1"] <= x <= ZONA["x2"] and ZONA["y1"] <= y <= ZONA["y2"]

def alerta(texto):
    linea = "[t=" + str(int(uptime())) + "s] ALERTA: " + texto
    alertas.insert(0, linea)
    if len(alertas) > 15:
        alertas.pop()
    print("!!! " + linea)
    if conn["c"] is not None and ok_conn():
        try:
            conn["c"].send("ALR|" + linea + "\n")
        except Exception:
            pass

def procesar(line):
    p = line.split("|")
    if len(p) < 7:
        return
    seq, eid, x, y, estado = p[1], p[2], float(p[3]), float(p[4]), p[5]
    st["total"] = st["total"] + 1
    e = emp.get(eid)
    if e is None:
        e = {"estado": estado, "entrada": None, "alertado": False}
        emp[eid] = e
    prev = e["estado"]
    if prev == "En reposo" and estado == "Alta actividad":
        alerta(eid + " paso de 'En reposo' a 'Alta actividad' (actividad fisica anormal)")
    ahora = uptime()
    if en_zona(x, y):
        if e["entrada"] is None:
            e["entrada"] = ahora
            e["alertado"] = False
        elif (ahora - e["entrada"]) > LIMITE_ZONA and not e["alertado"]:
            alerta(eid + " permanece mas de " + str(LIMITE_ZONA) + " s en zona restringida (" + ZONA["nombre"] + ")")
            e["alertado"] = True
    else:
        e["entrada"] = None
        e["alertado"] = False
    e.update({"x": x, "y": y, "estado": estado, "seq": seq, "t": ahora})
    zona = "SI" if en_zona(x, y) else "no"
    print("DASH " + eid + " pos=(" + str(x) + "," + str(y) + ") estado=" + estado + " zona_restringida=" + zona)
    try:
        conn["c"].send("DACK|" + seq + "\n")
    except Exception:
        pass

def on_receive(data):
    st["rx"] = st["rx"] + data
    while "\n" in st["rx"]:
        i = st["rx"].index("\n")
        line = st["rx"][:i]
        st["rx"] = st["rx"][i + 1:]
        if line.startswith("TRK|"):
            st["last_rx"] = uptime()
            procesar(line)

def main():
    while True:
        # se considera viva solo si llegan datos; sin datos en 10 s se abre un socket nuevo
        vivo = conn["c"] is not None and (uptime() - max(st.get("last_rx", -99), st.get("last_try", -99))) < 10
        if not vivo and (uptime() - st.get("last_try", -99)) > 5:
            st["last_try"] = uptime()
            print("Conectando a Tracker Relay [" + RELAY_IP + "]:" + str(RELAY_PORT))
            if conn["c"] is not None:
                try:
                    conn["c"].close()
                except Exception:
                    pass
            c = TCPClient()
            c.onReceive(on_receive)
            conn["c"] = c
            c.connect(RELAY_IP, RELAY_PORT)
        sleep(1)

if __name__ == "__main__":
    main()
