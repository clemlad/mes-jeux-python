"""
debug_discovery.py – Outil de diagnostic pour la découverte réseau.
 
Lance ce script sur les DEUX machines en même temps.
Il envoie ET écoute simultanément, et affiche tout ce qu'il reçoit.
 
Usage : python debug_discovery.py
"""
import json
import socket
import threading
import time
import sys
 
DISCOVERY_PORT = 37020
TEST_DURATION  = 15   # secondes
 
 
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()
 
 
def get_broadcast_addr(local_ip):
    """Calcule l'adresse de broadcast du sous-réseau /24 de l'IP locale."""
    parts = local_ip.split(".")
    return f"{parts[0]}.{parts[1]}.{parts[2]}.255"
 
 
def sender(local_ip, broadcast_addr, stop_event):
    """Envoie des paquets de test toutes les secondes."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    payload = json.dumps({
        "type": "debug_test",
        "from_ip": local_ip,
        "msg": "test_broadcast"
    }).encode("utf-8")
 
    destinations = [
        ("255.255.255.255",  "broadcast global"),
        (broadcast_addr,     f"broadcast réseau ({broadcast_addr})"),
        ("127.0.0.1",        "loopback"),
    ]
 
    print(f"\n[ENVOI] Démarrage — IP locale : {local_ip}")
    print(f"[ENVOI] Broadcast réseau : {broadcast_addr}")
    print("-" * 60)
 
    i = 0
    while not stop_event.is_set():
        i += 1
        for dest, label in destinations:
            try:
                sock.sendto(payload, (dest, DISCOVERY_PORT))
                print(f"[ENVOI #{i}] → {dest:<20} ({label})")
            except OSError as e:
                print(f"[ENVOI #{i}] ✗ ERREUR vers {dest}: {e}")
        time.sleep(1)
    sock.close()
 
 
def listener(stop_event):
    """Écoute sur le port UDP et affiche tout ce qui arrive."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except OSError:
            pass
    try:
        sock.bind(("", DISCOVERY_PORT))
        print(f"[ÉCOUTE] Socket UDP ouvert sur port {DISCOVERY_PORT} ✓")
    except OSError as e:
        print(f"[ÉCOUTE] ✗ IMPOSSIBLE d'ouvrir le port {DISCOVERY_PORT} : {e}")
        print(f"[ÉCOUTE]   → Cause probable : pare-feu ou port déjà utilisé.")
        stop_event.set()
        return
 
    sock.settimeout(1.0)
    received = 0
    while not stop_event.is_set():
        try:
            data, addr = sock.recvfrom(4096)
            received += 1
            try:
                msg = json.loads(data.decode("utf-8"))
                src = msg.get("from_ip", "?")
                print(f"[REÇU ✓] Paquet #{received} de {addr[0]}:{addr[1]}  (expéditeur déclaré : {src})")
            except Exception:
                print(f"[REÇU ✓] Paquet #{received} de {addr[0]}:{addr[1]}  (données brutes : {data[:60]})")
        except socket.timeout:
            continue
        except OSError:
            break
    sock.close()
    print(f"\n[ÉCOUTE] Terminé — {received} paquet(s) reçu(s) au total.")
 
 
def main():
    local_ip = get_local_ip()
    broadcast_addr = get_broadcast_addr(local_ip)
 
    print("=" * 60)
    print("   DIAGNOSTIC DÉCOUVERTE RÉSEAU — LOUP-GAROU")
    print("=" * 60)
    print(f"IP locale détectée : {local_ip}")
    print(f"Durée du test      : {TEST_DURATION} secondes")
    print(f"Port UDP testé     : {DISCOVERY_PORT}")
    print("=" * 60)
    print("\nLance ce script sur les DEUX machines en même temps.")
    print("Si les machines se voient, tu verras '[REÇU ✓]' apparaître.\n")
 
    stop_event = threading.Event()
 
    t_listen = threading.Thread(target=listener, args=(stop_event,), daemon=True)
    t_send   = threading.Thread(target=sender,   args=(local_ip, broadcast_addr, stop_event), daemon=True)
 
    t_listen.start()
    time.sleep(0.3)   # laisser le socket s'ouvrir avant d'envoyer
    t_send.start()
 
    try:
        time.sleep(TEST_DURATION)
    except KeyboardInterrupt:
        pass
 
    stop_event.set()
    time.sleep(1.5)
 
    print("\n" + "=" * 60)
    print("RÉSUMÉ — Que faire selon le résultat :")
    print("=" * 60)
    print("""
✓ Tu vois '[REÇU ✓]' avec l'IP de l'autre machine
  → La découverte fonctionne. Le bug est ailleurs (dans le jeu).
 
✓ Tu vois '[REÇU ✓]' avec '127.0.0.1' seulement
  → Le loopback marche, mais le broadcast est bloqué entre les deux PC.
  → Cause : pare-feu Windows ou isolation Wi-Fi sur le routeur.
 
✗ Aucun '[REÇU ✓]' du tout
  → Le port UDP 37020 est bloqué sur CETTE machine.
  → Lance en administrateur :
     netsh advfirewall firewall add rule name="LG-Discovery" protocol=UDP dir=in localport=37020 action=allow
 
✗ '[ÉCOUTE] IMPOSSIBLE d'ouvrir le port'
  → Un autre programme utilise déjà le port 37020.
  → Ferme le jeu loup-garou s'il tourne, puis relance ce script.
""")
 
 
if __name__ == "__main__":
    main()