import json
import socket
import threading
from naval_shared import Board, layout_from_board
from server_discovery import ServerBroadcaster, get_local_ip

HOST = "0.0.0.0"
PORT = 5555


class NavalServer:
    def __init__(self, host_name="Joueur", host=HOST, port=PORT):
        """
        Initialise le serveur TCP de Bataille Navale pour deux joueurs.

        :param host_name: Nom du joueur hôte, utilisé dans le nom de la partie (str).
        :param host: Adresse d'écoute du serveur (str), '0.0.0.0' par défaut.
        :param port: Port TCP d'écoute (int), 5555 par défaut.
        """
        self.host = host
        self.port = port
        self.server_name = f"Partie de {host_name}"
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.clients = [None, None]
        self.player_names = [None, None]
        self.lock = threading.Lock()
        self.running = True
        self.host_ip = get_local_ip()
        self.broadcaster = ServerBroadcaster(self.server_name, host_ip=self.host_ip, game_port=self.port)
        self.reset_game()

    def reset_game(self):
        """Réinitialise l'état de la partie : grilles, placements, tour, gagnant et demandes de revanche."""
        self.boards = [Board(), Board()]
        self.placed = [False, False]
        self.current_turn = 0
        self.game_started = False
        self.winner = None
        self.rematch_requests = set()

    def connected_player_count(self):
        """Retourne le nombre de joueurs actuellement connectés (int, 0 à 2)."""
        return sum(1 for conn in self.clients if conn is not None)

    def safe_name(self, player_id):
        """
        Retourne le nom enregistré du joueur, ou un nom par défaut s'il est absent.

        :param player_id: Indice du joueur (int), 0 ou 1.
        :return: str
        """
        return self.player_names[player_id] or f"Joueur {player_id + 1}"

    def send_json(self, conn, data):
        """
        Sérialise `data` en JSON et l'envoie sur la connexion avec un saut de ligne comme délimiteur.

        :param conn: Socket client connecté (socket.socket).
        :param data: Dictionnaire Python à envoyer (dict).
        """
        conn.sendall((json.dumps(data) + "\n").encode("utf-8"))

    def broadcast(self, data):
        """
        Envoie un message JSON à tous les joueurs connectés.

        :param data: Dictionnaire Python à diffuser (dict).
        """
        for conn in self.clients:
            if conn is not None:
                try:
                    self.send_json(conn, data)
                except OSError:
                    pass

    def player_snapshot(self, player_id):
        """
        Construit un dict d'état de jeu personnalisé pour le joueur donné (sa grille visible, celle de l'ennemi masquée).

        :param player_id: Indice du joueur destinataire (int), 0 ou 1.
        :return: dict contenant le type 'state_sync', les grilles, le tour, le gagnant, etc.
        """
        enemy = 1 - player_id
        return {
            "type": "state_sync",
            "phase": "battle" if self.game_started and self.winner is None else ("end" if self.winner is not None else "placement"),
            "your_turn": self.current_turn == player_id,
            "your_board": self.boards[player_id].serialize(reveal_positions=True),
            "enemy_board": self.boards[enemy].serialize(reveal_positions=False),
            "winner": self.winner,
            "player_names": [self.safe_name(0), self.safe_name(1)],
            "server_name": self.server_name,
            "rematch_requests": sorted(self.rematch_requests),
        }

    def handle_join(self, player_id, msg):
        """
        Enregistre le nom du joueur lors de sa connexion et diffuse son arrivée.

        :param player_id: Indice du joueur (int), 0 ou 1.
        :param msg: Message reçu contenant la clé 'name' (dict).
        :return: dict snapshot d'état pour le joueur.
        """
        name = str(msg.get("name", "")).strip()[:20] or f"Joueur {player_id + 1}"
        self.player_names[player_id] = name
        self.broadcast({"type": "info", "message": f"{name} a rejoint la partie."})
        return self.player_snapshot(player_id)

    def handle_place(self, player_id, msg):
        """
        Valide et enregistre le placement des bateaux d'un joueur ; démarre la partie si les deux ont placé.

        :param player_id: Indice du joueur (int), 0 ou 1.
        :param msg: Message contenant la clé 'layout' (list de dicts) décrivant les positions des bateaux.
        :return: dict d'erreur ou d'info, ou None si la partie démarre (les snapshots sont envoyés directement).
        """
        if self.placed[player_id]:
            return {"type": "error", "message": "Placement déjà validé."}
        layout = msg.get("layout", [])
        board = Board()
        try:
            board.place_all_from_layout(layout)
        except Exception:
            return {"type": "error", "message": "Placement invalide."}

        if len(board.ships) != 5:
            return {"type": "error", "message": "Il faut placer les 5 bateaux."}

        self.boards[player_id] = board
        self.placed[player_id] = True

        if all(self.placed) and all(conn is not None for conn in self.clients):
            self.game_started = True
            self.current_turn = 0
            self.rematch_requests.clear()
            for pid, conn in enumerate(self.clients):
                if conn is not None:
                    self.send_json(conn, self.player_snapshot(pid))
        else:
            return {"type": "info", "message": "Placement enregistré. En attente de l'autre joueur..."}
        return None

    def handle_shoot(self, player_id, msg):
        """
        Traite un tir du joueur sur la grille adverse et met à jour l'état de la partie.

        :param player_id: Indice du joueur qui tire (int), 0 ou 1.
        :param msg: Message contenant les clés 'row' et 'col' (int) des coordonnées visées.
        :return: dict d'erreur ou None (les mises à jour sont broadcastées directement).
        """
        if not self.game_started or self.winner is not None:
            return {"type": "error", "message": "La partie n'a pas commencé."}
        if self.current_turn != player_id:
            return {"type": "error", "message": "Ce n'est pas ton tour."}

        row = msg.get("row")
        col = msg.get("col")
        if not isinstance(row, int) or not isinstance(col, int):
            return {"type": "error", "message": "Coordonnées invalides."}

        enemy = 1 - player_id
        result, ship = self.boards[enemy].receive_shot(row, col)
        if result == "already":
            return {"type": "error", "message": "Case déjà jouée."}

        shooter = self.safe_name(player_id)
        if result == "miss":
            self.current_turn = enemy
            message = f"{shooter} tire en {col + 1},{row + 1} : raté."
        elif result == "hit":
            message = f"{shooter} touche un bateau ennemi."
        else:
            message = f"{shooter} coule {ship.name.replace(' T', '')} !"

        if self.boards[enemy].all_sunk():
            self.winner = player_id
            self.game_started = False
            self.rematch_requests.clear()

        for pid, conn in enumerate(self.clients):
            if conn is not None:
                payload = self.player_snapshot(pid)
                payload["type"] = "shot_result"
                payload["message"] = message
                self.send_json(conn, payload)
        return None

    def handle_rematch(self, player_id):
        """
        Enregistre la demande de revanche d'un joueur ; réinitialise la partie si les deux joueurs acceptent.

        :param player_id: Indice du joueur demandeur (int), 0 ou 1.
        :return: dict d'erreur ou None.
        """
        if self.winner is None:
            return {"type": "error", "message": "Le match n'est pas terminé."}
        self.rematch_requests.add(player_id)
        if len(self.rematch_requests) < 2:
            other = self.safe_name(player_id)
            for pid, conn in enumerate(self.clients):
                if conn is not None:
                    payload = self.player_snapshot(pid)
                    payload["type"] = "info"
                    payload["message"] = f"{other} propose de rejouer."
                    self.send_json(conn, payload)
            return None

        self.reset_game()
        for pid, conn in enumerate(self.clients):
            if conn is not None:
                payload = self.player_snapshot(pid)
                payload["type"] = "state_sync"
                self.send_json(conn, payload)
        return None

    def remove_client(self, player_id):
        """
        Déconnecte un joueur, notifie l'autre et réinitialise la partie.

        :param player_id: Indice du joueur à retirer (int), 0 ou 1.
        """
        conn = self.clients[player_id]
        name = self.safe_name(player_id)
        self.clients[player_id] = None
        self.broadcaster.set_player_count(self.connected_player_count())
        if conn:
            try:
                conn.close()
            except OSError:
                pass
        self.broadcast({"type": "info", "message": f"{name} s'est déconnecté."})
        self.reset_game()

    def handle_client(self, conn, player_id):
        """
        Boucle de réception des messages d'un joueur dans son thread dédié.
        Dispatche chaque message vers le gestionnaire approprié (join, place, shoot, etc.).

        :param conn: Socket du joueur connecté (socket.socket).
        :param player_id: Indice du joueur (int), 0 ou 1.
        """
        try:
            self.send_json(conn, {"type": "welcome", "player_id": player_id, "server_name": self.server_name})
            buffer = ""
            while self.running:
                data = conn.recv(4096)
                if not data:
                    break
                buffer += data.decode("utf-8")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if not line.strip():
                        continue
                    msg = json.loads(line)
                    with self.lock:
                        kind = msg.get("type")
                        if kind == "join":
                            response = self.handle_join(player_id, msg)
                        elif kind == "place_ships":
                            response = self.handle_place(player_id, msg)
                        elif kind == "shoot":
                            response = self.handle_shoot(player_id, msg)
                        elif kind == "sync_request":
                            response = self.player_snapshot(player_id)
                        elif kind == "rematch_request":
                            response = self.handle_rematch(player_id)
                        else:
                            response = {"type": "error", "message": "Commande inconnue."}
                    if response is not None:
                        self.send_json(conn, response)
        except (ConnectionResetError, json.JSONDecodeError, OSError):
            pass
        finally:
            with self.lock:
                if self.clients[player_id] is conn:
                    self.remove_client(player_id)

    def shutdown(self):
        """Arrête le serveur proprement : notifie les clients, ferme leurs connexions et le socket serveur."""
        self.running = False
        self.broadcaster.stop()
        with self.lock:
            for index, conn in enumerate(self.clients):
                if conn is not None:
                    try:
                        self.send_json(conn, {"type": "info", "message": "Le serveur s'arrête."})
                    except OSError:
                        pass
                    try:
                        conn.close()
                    except OSError:
                        pass
                    self.clients[index] = None
        try:
            self.server.close()
        except OSError:
            pass

    def serve_forever(self):
        """Lance l'écoute TCP et accepte les connexions entrantes jusqu'à l'arrêt du serveur."""
        self.server.bind((self.host, self.port))
        self.server.listen(2)
        self.server.settimeout(1.0)
        self.broadcaster.start()
        print(f"Serveur lancé sur {self.host}:{self.port}")
        print(f"IP locale du serveur : {self.host_ip}")
        print("En attente de 2 joueurs...")
        while self.running:
            try:
                conn, addr = self.server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with self.lock:
                try:
                    player_id = self.clients.index(None)
                except ValueError:
                    self.send_json(conn, {"type": "error", "message": "Serveur plein."})
                    conn.close()
                    continue
                self.clients[player_id] = conn
                self.broadcaster.set_player_count(self.connected_player_count())
            print(f"Joueur {player_id + 1} connecté depuis {addr}")
            threading.Thread(target=self.handle_client, args=(conn, player_id), daemon=True).start()
        print("Serveur arrêté.")


if __name__ == "__main__":
    server = NavalServer()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt demandé par l'utilisateur...")
    finally:
        server.shutdown()
