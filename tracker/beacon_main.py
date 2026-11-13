from physical import *
from bluetooth import *
from time import *

# Beacon BLE simulado del empleado: emite su ID y su posicion estimada (X,Y) cada segundo.
# Recorrido ciclico por la planta (100 m x 100 m) que incluye una permanencia de ~75 s en la
# zona restringida (Sala de servidores, X 70-100 / Y 70-100) para poder evidenciar la alerta.
BEACON_UUID = "{00000000-0000-0000-0000-0000000000E5}"
EMPLOYEE_ID = "EMP-001"
# (x, y, segundos de permanencia en el punto)
RUTA = [(20.0, 20.0, 10), (50.0, 30.0, 5), (85.0, 85.0, 75), (40.0, 60.0, 10), (10.0, 80.0, 5)]

_seed = [12345]
def rnd():
    _seed[0] = (_seed[0] * 1103515245 + 12345 + int(uptime() * 1000)) % 2147483648
    return _seed[0] / 2147483648.0

def main():
    Bluetooth.init()
    Bluetooth.enableBroadcast(True)
    x, y = RUTA[0][0], RUTA[0][1]
    i = 1
    espera = 0
    while True:
        tx, ty, quieto = RUTA[i]
        dx = tx - x
        dy = ty - y
        dist = (dx * dx + dy * dy) ** 0.5
        if dist < 3:
            # en el punto: pequeno movimiento aleatorio mientras permanece
            espera = espera + 1
            x = tx + (rnd() - 0.5) * 4
            y = ty + (rnd() - 0.5) * 4
            if espera >= quieto:
                espera = 0
                i = (i + 1) % len(RUTA)
        else:
            paso = 3.0 + rnd() * 3.0
            if paso > dist:
                paso = dist
            x = x + paso * dx / dist
            y = y + paso * dy / dist
        data = EMPLOYEE_ID + ";" + str(round(x, 1)) + ";" + str(round(y, 1))
        Bluetooth.broadcastBeacon(BEACON_UUID, data)
        print("BEACON " + data)
        sleep(1)

if __name__ == "__main__":
    main()
