from tcp import *
from http import *
from time import *

# Tracker Relay (Tracker_Server - DMZ IPv6)
# TCP 5000: recibe los paquetes de las Tracker App (PC4) y responde ACK.
# TCP 5001: el Tracker Dashboard (PC7) se suscribe; el Relay le reenvia cada paquete y
#           devuelve a la Tracker App la confirmacion (DACK) del Dashboard.
# HTTP 8080: vista web del tablero (bonus), consultada desde el navegador de PC7:
#           http://tracker.sslmjp.net
APP_PORT = 5000
DASH_PORT = 5001
WEB_PORT = 80

apps = []
dashboards = []
buffers = {}
stats = {"rx": 0, "fwd": 0, "dack": 0}
ultimo = {}
alertas = []

def lines_from(client, data):
    try:
        key = str(client.remoteIP()) + ":" + str(client.remotePort())
    except Exception:
        key = "?"
    buf = buffers.get(key, "") + data
    out = []
    while "\n" in buf:
        i = buf.index("\n")
        out.append(buf[:i])
        buf = buf[i + 1:]
    buffers[key] = buf
    return out

def vivos(lista):
    # Solo se descartan los sockets cuyo objeto ya no existe (PT puede reportar
    # connected()=False en el lado servidor aunque la sesion siga activa)
    out = []
    for c in lista:
        try:
            c.remotePort()
            out.append(c)
        except Exception:
            pass
    lista[:] = out
    return out

def enviar(c, texto):
    try:
        c.send(texto)
        return True
    except Exception:
        for lista in (apps, dashboards):
            if c in lista:
                lista.remove(c)
        return False

def make_app_handler(client):
    def handler(data):
        for line in lines_from(client, data):
            if not line.startswith("TRK|"):
                continue
            stats["rx"] = stats["rx"] + 1
            p = line.split("|")
            enviar(client, "ACK|" + p[1] + "\n")
            if len(p) >= 7:
                ultimo[p[2]] = {"seq": p[1], "x": p[3], "y": p[4], "estado": p[5], "t": int(uptime())}
            n = 0
            for d in vivos(dashboards):
                if enviar(d, line + "\n"):
                    n = n + 1
            stats["fwd"] = stats["fwd"] + n
    return handler

def make_dash_handler(client):
    def handler(data):
        for line in lines_from(client, data):
            if line.startswith("DACK|"):
                stats["dack"] = stats["dack"] + 1
                for a in vivos(apps):
                    enviar(a, line + "\n")
            elif line.startswith("ALR|"):
                alertas.insert(0, line[4:])
                if len(alertas) > 15:
                    alertas.pop()
                print("ALERTA desde Dashboard: " + line[4:])
    return handler

def on_new_app(client):
    print("Nueva Tracker App: " + str(client.remoteIP()))
    vivos(apps)
    apps.append(client)
    client.onReceive(make_app_handler(client))

def on_new_dash(client):
    print("Nuevo Tracker Dashboard: " + str(client.remoteIP()))
    vivos(dashboards)
    dashboards.append(client)
    client.onReceive(make_dash_handler(client))

def en_zona(x, y):
    return 70.0 <= x <= 100.0 and 70.0 <= y <= 100.0

def pagina():
    h = "<html><head><meta http-equiv='refresh' content='2'><title>Employee Tracker</title></head><body>"
    h += "<h2>Employee Tracker - Tablero web</h2>"
    h += "<p>Datos en tiempo real recibidos por el Tracker Relay (DMZ) y analizados por el Tracker Dashboard (PC7).</p>"
    h += "<p>Paquetes de Tracker App: " + str(stats["rx"]) + " | Reenviados al Dashboard: " + str(stats["fwd"])
    h += " | Confirmaciones del Dashboard: " + str(stats["dack"]) + " | t=" + str(int(uptime())) + " s</p>"
    h += "<table border='1' cellpadding='4'><tr><th>Empleado</th><th>X (m)</th><th>Y (m)</th>"
    h += "<th>Actividad</th><th>Zona restringida</th><th>Secuencia</th></tr>"
    for k in ultimo:
        e = ultimo[k]
        z = "SI" if en_zona(float(e["x"]), float(e["y"])) else "no"
        h += "<tr><td>" + k + "</td><td>" + e["x"] + "</td><td>" + e["y"] + "</td><td>" + e["estado"]
        h += "</td><td>" + z + "</td><td>" + e["seq"] + "</td></tr>"
    h += "</table><h3>Alertas (generadas por el Dashboard en PC7)</h3><ul>"
    for a in alertas:
        h += "<li>" + a + "</li>"
    h += "</ul><p>Zona restringida: Sala de servidores (X 70-100 m, Y 70-100 m)</p></body></html>"
    return h

def on_web(url, response):
    response.setContentType("text/html")
    response.send(pagina())

def on_new_web(client):
    print("WEB 8081: nueva conexion de " + str(client.remoteIP()))
    # Servidor HTTP minimo sobre socket TCP (alternativa a HTTPServer para clientes remotos)
    def handler(data):
        print("WEB 8081 <- " + str(client.remoteIP()) + " : " + str(data)[:60])
        body = pagina()
        resp = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: " + str(len(body)) + \
               "\r\nConnection: close\r\n\r\n" + body
        try:
            client.send(resp)
        except Exception:
            pass
    client.onReceive(handler)

def main():
    s_web = TCPServer()
    s_web.onNewClient(on_new_web)
    s_web.listen(8081)
    s_app = TCPServer()
    s_app.onNewClient(on_new_app)
    s_app.listen(APP_PORT)
    s_dash = TCPServer()
    s_dash.onNewClient(on_new_dash)
    s_dash.listen(DASH_PORT)
    HTTPServer.route("/*", on_web)
    HTTPServer.route("/", on_web)
    print("Tracker Relay: TCP " + str(APP_PORT) + " (apps), TCP " + str(DASH_PORT) + " (dashboards), HTTP " +
          str(WEB_PORT) + " -> " + str(HTTPServer.start(WEB_PORT)))
    while True:
        sleep(10)
        print("Relay: recibidos=" + str(stats["rx"]) + " reenviados=" + str(stats["fwd"]) + " dack=" + str(stats["dack"]))

if __name__ == "__main__":
    main()
