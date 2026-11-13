from bluetooth import *
from tcp import *
from time import *

# Tracker App (PC4 - Intranet BOG)
# Detecta el beacon BLE del empleado, genera el paquete de seguimiento y lo envia
# cada segundo al Tracker Relay (Tracker_Server, DMZ) por un socket TCP.
BEACON_UUID = "{00000000-0000-0000-0000-0000000000E5}"
RELAY_IP = "2001:1200:EC15:1::30"
RELAY_PORT = 5000
ESTADOS = ["En reposo", "En movimiento", "Alta actividad"]

beacon = {"id": None, "x": 0.0, "y": 0.0, "t": 0}
state = {"seq": 0, "estado": 0, "acks": 0, "rx": ""}
conn = {"c": None}

def ok_conn():
    try:
        return conn["c"] is not None and conn["c"].connected()
    except Exception:
        return False
_seed = [987654]

def rnd():
    _seed[0] = (_seed[0] * 1103515245 + 12345 + int(uptime() * 1000)) % 2147483648
    return _seed[0] / 2147483648.0

def next_activity():
    # Cadena de Markov simple: normalmente cambia gradualmente, a veces hay saltos bruscos
    r = rnd()
    e = state["estado"]
    if r < 0.60:
        return e
    if r < 0.92:
        if e == 0:
            return 1
        if e == 2:
            return 1
        if rnd() < 0.5:
            return 0
        return 2
    return int(rnd() * 3) % 3

def on_beacon(srcMac, srcService, dstMac, dstService, data):
    parts = data.split(";")
    if len(parts) >= 3:
        beacon["id"] = parts[0]
        beacon["x"] = float(parts[1])
        beacon["y"] = float(parts[2])
        beacon["t"] = uptime()
        beacon["mac"] = srcMac

def on_receive(data):
    state["rx"] = state["rx"] + data
    while "\n" in state["rx"]:
        i = state["rx"].index("\n")
        line = state["rx"][:i]
        state["rx"] = state["rx"][i + 1:]
        if line.startswith("ACK|") or line.startswith("DACK|"):
            state["acks"] = state["acks"] + 1
            state["last_ack"] = uptime()
            print("<- " + line)

def on_conn(t):
    print("Conexion con Tracker Relay: " + str(t))

def connected():
    # PT a veces reporta connected()=False con la sesion activa: tambien se considera viva
    # si llego un ACK en los ultimos 6 s (evita abrir sockets duplicados)
    if conn["c"] is None:
        return False
    # viva si hubo ACK reciente; durante los primeros 10 s tras conectar se confia en connected()
    if (uptime() - state.get("last_ack", -99)) < 10:
        return True
    return ok_conn() and (uptime() - state.get("last_try", -99)) < 10

def ensure_connected():
    # Si no hay conexion abierta, cada 5 s se crea un socket TCP nuevo y se reintenta
    if not connected() and (uptime() - state.get("last_try", -99)) > 5:
        state["last_try"] = uptime()
        print("Conectando a Tracker Relay [" + RELAY_IP + "]:" + str(RELAY_PORT))
        if conn["c"] is not None:
            try:
                conn["c"].close()
            except Exception:
                pass
        c = TCPClient()
        c.onReceive(on_receive)
        c.onConnectionChange(on_conn)
        conn["c"] = c
        c.connect(RELAY_IP, RELAY_PORT)

def main():
    Bluetooth.init()
    svc = BluetoothService()
    svc.onReceive(on_beacon)
    print("Escuchando beacons BLE: " + str(svc.start(BEACON_UUID)))
    while True:
        ensure_connected()
        if beacon["id"] is not None and connected():
            state["seq"] = state["seq"] + 1
            state["estado"] = next_activity()
            msg = "TRK|" + str(state["seq"]) + "|" + beacon["id"] + "|" + str(beacon["x"]) + "|" + \
                  str(beacon["y"]) + "|" + ESTADOS[state["estado"]] + "|" + str(int(uptime()))
            try:
                conn["c"].send(msg + "\n")
                print("-> " + msg)
            except Exception:
                conn["c"] = None
        elif beacon["id"] is None:
            print("Esperando beacon...")
        sleep(1)

if __name__ == "__main__":
    main()
