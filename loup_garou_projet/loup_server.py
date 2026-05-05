"""
loup_server.py – Serveur TCP multithreadé pour le mode en ligne.

Architecture : un thread par client (handle_client), toutes les mutations d'état
protégées par self.lock. Les snapshots sont envoyés en broadcast après chaque action.

Protocole : messages JSON terminés par '\n', un message par ligne.
"""
import json
import socket
import threading
from collections import Counter
from pathlib import Path

from chat_moderation import ChatModerator
from loup_shared import (
    MIN_PLAYERS,
    MAX_PLAYERS,
    build_roles,
    check_winner,
    is_wolf_role,
    normalize_role_config,
    role_config_label,
    serialize_players_for,
    min_players_for_config,
    role_config_error,
)
from server_discovery import ServerBroadcaster, get_local_ip

HOST = "0.0.0.0"
PORT = 5555
BASE_DIR = Path(__file__).resolve().parent
MODERATION_CSV = BASE_DIR / "moderation_loup_garou_fr_en.csv"


class WerewolfServer:
    def __init__(self, host_name="Joueur", host=HOST, port=PORT,
                 max_players=MAX_PLAYERS, role_config=None,
                 ready_event: threading.Event = None):
        self.host = host
        self.port = port
        self.server_name = f"Salon de {host_name}"
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.lock = threading.Lock()
        self.running = True
        self.bind_ok = False                    # True seulement si le bind a réussi
        self.ready_event = ready_event          # signalé quand le bind est OK
        self.host_ip = get_local_ip()
        self.max_players = max(MIN_PLAYERS, min(MAX_PLAYERS, int(max_players)))
        self.role_config = normalize_role_config(role_config)
        self.broadcaster = ServerBroadcaster(self.server_name,
                                             host_ip=self.host_ip,
                                             game_port=self.port)
        self.broadcaster.set_room_config(self.max_players, role_config_label(self.role_config))
        # Tableau clients dynamique : index = player_id
        self.clients: list = []
        self.chat_history: list = []
        self.moderator = ChatModerator(MODERATION_CSV)
        self.reset_lobby_state()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def reset_lobby_state(self):
        self.players: list = []
        self.host_id = 0
        self.game_started = False
        self.phase = "lobby"
        self.day_count = 0
        self.winner = None
        self.message = f"En attente des joueurs. Minimum : {MIN_PLAYERS}."
        self.last_deaths: list = []
        self.pending_night: dict = {}
        self.wolf_votes: dict = {}
        self.day_votes: dict = {}
        self.witch_heal_used = False
        self.witch_poison_used = False
        self.pending_wolf_target = None

    def _ensure_slot(self, player_id: int):
        """Étend clients[] pour que l'index player_id existe (liste dynamique)."""
        while len(self.clients) <= player_id:
            self.clients.append(None)

    def connected_player_count(self) -> int:
        return sum(1 for c in self.clients if c is not None)

    def send_json(self, conn, data: dict):
        try:
            conn.sendall((json.dumps(data) + "\n").encode("utf-8"))
        except OSError:
            pass

    def append_chat(self, author: str, message: str, system: bool = False, wolf_only: bool = False):
        entry = {"author": author, "message": message[:220], "system": system, "wolf_only": wolf_only}
        self.chat_history.append(entry)
        self.chat_history = self.chat_history[-80:]

    def broadcast_snapshots(self):
        for player in self.players:
            pid = player["id"]
            if pid >= len(self.clients):
                continue
            conn = self.clients[pid]
            if conn is None or not player.get("connected"):
                continue
            try:
                self.send_json(conn, self.player_snapshot(pid))
            except OSError:
                pass

    # ── Snapshots ────────────────────────────────────────────────────────────

    def player_snapshot(self, player_id: int) -> dict:
        player = self.players[player_id]
        alive_players = [p for p in self.players if p["alive"]]
        wolves_alive  = [p for p in alive_players if is_wolf_role(p["role"])]
        current_role  = player["role"] if self.game_started else None
        is_wolf = is_wolf_role(current_role) if current_role else False
        can_act = False
        action_hint = ""

        if self.phase == "night" and player["alive"]:
            if is_wolf_role(current_role):
                can_act = True
                action_hint = "Choisissez une victime parmi les joueurs vivants."
            elif current_role == "Voyante" and not self.pending_night.get("seer_done", False):
                can_act = True
                action_hint = "Choisissez un joueur pour découvrir son rôle."
            elif current_role == "Sorcière":
                if not self.pending_night.get("witch_done", False):
                    can_act = True
                    heal_ok  = not self.witch_heal_used
                    poison_ok = not self.witch_poison_used
                    parts = []
                    if heal_ok:
                        parts.append("sauver la victime")
                    if poison_ok:
                        parts.append("empoisonner un joueur")
                    action_hint = ("Vous pouvez " + " ou ".join(parts) + "."
                                   if parts else "Passez votre tour.")
        elif self.phase == "day" and player["alive"]:
            can_act = True
            action_hint = "Votez contre un joueur que vous suspectez."

        night_target_name = None
        if (self.pending_wolf_target is not None
                and current_role == "Sorcière"
                and self.pending_wolf_target < len(self.players)):
            night_target_name = self.players[self.pending_wolf_target]["name"]

        # Potions disponibles (uniquement communiquées à la sorcière)
        witch_heal_available   = (current_role == "Sorcière" and not self.witch_heal_used)
        witch_poison_available = (current_role == "Sorcière" and not self.witch_poison_used)

        # Chat : la nuit seuls les loups peuvent écrire
        can_chat = True
        if self.phase == "night" and self.game_started and player["alive"]:
            can_chat = is_wolf

        # Filtrer les messages loup-only pour les non-loups
        if is_wolf:
            visible_chat = list(self.chat_history)
        else:
            visible_chat = [e for e in self.chat_history if not e.get("wolf_only")]

        # Progression des votes du jour (feedback au joueur)
        has_voted = (player_id in self.day_votes) if self.phase == "day" else False

        return {
            "type":                  "state_sync",
            "server_name":           self.server_name,
            "phase":                 self.phase,
            "day_count":             self.day_count,
            "your_id":               player_id,
            "host_id":               self.host_id,
            "players":               serialize_players_for(player_id, self.players,
                                                           reveal_all=(self.winner is not None)),
            "game_started":          self.game_started,
            "winner":                self.winner,
            "message":               self.message,
            "last_deaths":           list(self.last_deaths),
            "night_target_name":     night_target_name,
            "can_act":               can_act,
            "action_hint":           action_hint,
            "seer_result":           self.pending_night.get(("seer_result", player_id)),
            "wolf_count":            len(wolves_alive),
            "connected_count":       self.connected_player_count(),
            "max_players":           self.max_players,
            "role_config":           self.role_config,
            "chat_history":          visible_chat,
            "witch_heal_available":  witch_heal_available,
            "witch_poison_available": witch_poison_available,
            "can_chat":              can_chat,
            "has_voted":             has_voted,
            "votes_cast":            len(self.day_votes),
            "votes_needed":          len([p for p in self.players
                                          if p.get("connected") and p["alive"]]),
        }

    # ── Gestion des connexions ────────────────────────────────────────────────

    def remove_client(self, player_id: int):
        if player_id < len(self.clients):
            self.clients[player_id] = None
        if player_id < len(self.players):
            self.players[player_id]["alive"]     = False
            self.players[player_id]["connected"] = False
            self.append_chat("Systeme",
                             f"{self.players[player_id]['name']} a quitte la partie.",
                             system=True)
        self.broadcaster.set_player_count(self.connected_player_count())
        self.message = "Un joueur s'est deconnecte."
        self.winner = check_winner(self.players) if self.game_started else None
        self.broadcast_snapshots()

    # ── Handlers messages ────────────────────────────────────────────────────

    def handle_join(self, player_id: int, msg: dict):
        name = str(msg.get("name", "")).strip()[:20] or f"Joueur {player_id + 1}"
        while len(self.players) <= player_id:
            self.players.append({
                "id":           len(self.players),
                "name":         f"Joueur {len(self.players) + 1}",
                "role":         None,
                "alive":        True,
                "connected":    False,
                "revealed_role": None,
            })
        self.players[player_id].update({"name": name, "connected": True, "alive": True})
        self.message = f"{name} a rejoint la partie."
        self.append_chat("Systeme", self.message, system=True)
        self.broadcaster.set_player_count(self.connected_player_count())
        self.broadcast_snapshots()
        return self.player_snapshot(player_id)

    def update_role_config(self, player_id: int, msg: dict):
        if player_id != self.host_id:
            return {"type": "error", "message": "Seul l'hote peut modifier les roles."}
        if self.game_started or self.phase != "lobby":
            return {"type": "error", "message": "Modification impossible en cours de partie."}
        new_config = normalize_role_config(msg.get("role_config", {}))
        required = min_players_for_config(new_config)
        if required > MAX_PLAYERS:
            return {"type": "error", "message": f"Configuration impossible : max {MAX_PLAYERS} joueurs."}
        self.role_config = new_config
        if self.max_players < required:
            self.max_players = required
        self.broadcaster.set_room_config(self.max_players, role_config_label(self.role_config))
        self.message = "Configuration des roles mise a jour."
        self.broadcast_snapshots()
        return self.player_snapshot(player_id)

    def update_max_players(self, player_id: int, msg: dict):
        if player_id != self.host_id:
            return {"type": "error", "message": "Seul l'hote peut modifier le nombre de joueurs."}
        if self.game_started or self.phase != "lobby":
            return {"type": "error", "message": "Modification impossible en cours de partie."}
        requested = int(msg.get("max_players", self.max_players))
        requested = max(MIN_PLAYERS, min(MAX_PLAYERS, requested))
        requested = max(requested, self.connected_player_count(),
                        min_players_for_config(self.role_config))
        self.max_players = requested
        self.broadcaster.set_room_config(self.max_players, role_config_label(self.role_config))
        self.message = f"Salon regle sur {self.max_players} joueurs."
        self.broadcast_snapshots()
        return self.player_snapshot(player_id)

    def start_game(self, player_id: int):
        if player_id != self.host_id:
            return {"type": "error", "message": "Seul l'hote peut lancer la partie."}
        active = [p for p in self.players if p.get("connected")]
        if len(active) < MIN_PLAYERS:
            return {"type": "error", "message": f"Il faut au moins {MIN_PLAYERS} joueurs."}
        if len(active) != self.max_players:
            return {"type": "error",
                    "message": f"Il faut exactement {self.max_players} joueurs connectes."}
        err = role_config_error(self.max_players, self.role_config)
        if err:
            return {"type": "error", "message": err}
        try:
            roles = build_roles(len(active), self.role_config)
        except ValueError as exc:
            return {"type": "error", "message": str(exc)}
        for p, role in zip(active, roles):
            p["role"]          = role
            p["alive"]         = True
            p["revealed_role"] = None
        self.game_started = True
        self.winner = None
        self.day_count = 0
        self.message = "La partie commence !"
        self.append_chat("Systeme",
                         f"La partie demarre : {role_config_label(self.role_config)}.",
                         system=True)
        self.start_night()
        return None

    # ── Phases ───────────────────────────────────────────────────────────────

    def alive_ids(self) -> list:
        return [p["id"] for p in self.players if p.get("connected") and p["alive"]]

    def start_night(self):
        self.phase = "night"
        self.day_count += 1
        self.last_deaths = []
        self.pending_night = {"seer_done": False, "witch_done": False}
        self.wolf_votes = {}
        self.day_votes  = {}
        self.pending_wolf_target = None
        self.message = f"Nuit {self.day_count} : les roles de nuit agissent."
        self.broadcast_snapshots()

    def resolve_wolves_if_ready(self) -> bool:
        """
        Agrège les votes des loups dès qu'ils ont tous voté.
        Retourne True si la cible est déterminée (ou s'il n'y a pas de loup vivant).
        En cas d'égalité, le joueur avec le plus petit id l'emporte (déterministe).
        """
        wolves = [p for p in self.players
                  if p.get("connected") and p["alive"] and is_wolf_role(p["role"])]
        if wolves and len(self.wolf_votes) == len(wolves):
            counts = Counter(self.wolf_votes.values())
            self.pending_wolf_target = max(counts.items(), key=lambda x: (x[1], -x[0]))[0]
        return self.pending_wolf_target is not None or not wolves

    def resolve_night_if_ready(self):
        """
        Résout la nuit uniquement quand tous les rôles de nuit ont agi.
        Le all() vérifie : soit le joueur n'a pas ce rôle, soit il est mort,
        soit il a déjà effectué son action (seer_done / witch_done).
        """
        wolves_ready = self.resolve_wolves_if_ready()
        seer_ready   = all(
            p["role"] != "Voyante" or not p["alive"]
            or self.pending_night.get("seer_done", False)
            for p in self.players if p.get("connected")
        )
        witch_ready  = all(
            p["role"] != "Sorcière" or not p["alive"]
            or self.pending_night.get("witch_done", False)
            for p in self.players if p.get("connected")
        )
        if not (wolves_ready and seer_ready and witch_ready):
            return

        deaths: set = set()
        if (self.pending_wolf_target is not None
                and not self.pending_night.get("saved", False)):
            deaths.add(self.pending_wolf_target)
        pt = self.pending_night.get("poison_target")
        if pt is not None:
            deaths.add(pt)

        for pid in deaths:
            if self.players[pid]["alive"]:
                self.players[pid]["alive"]         = False
                self.players[pid]["revealed_role"] = self.players[pid]["role"]

        self.last_deaths = [self.players[pid]["name"] for pid in deaths]
        self.winner = check_winner(self.players)
        if self.winner is not None:
            self.phase   = "end"
            self.message = f"Victoire du camp : {self.winner} !"
        else:
            self.phase = "day"
            self.message = ("Jour : " + ", ".join(self.last_deaths) + " elimine(s). Votez."
                            if self.last_deaths else "Jour : personne n'est mort cette nuit. Votez.")
        self.broadcast_snapshots()

    # ── Actions de nuit ──────────────────────────────────────────────────────

    def handle_night_action(self, player_id: int, msg: dict):
        if self.phase != "night":
            return {"type": "error", "message": "Ce n'est pas la nuit."}
        player = self.players[player_id]
        if not player["alive"]:
            return {"type": "error", "message": "Tu es elimine."}
        action = msg.get("action")
        target = msg.get("target")

        if action == "wolf_kill":
            if not is_wolf_role(player["role"]):
                return {"type": "error", "message": "Action reservee aux loups."}
            if target == player_id or target not in self.alive_ids():
                return {"type": "error", "message": "Cible invalide."}
            self.wolf_votes[player_id] = target
            self.resolve_night_if_ready()
            return self.player_snapshot(player_id)

        if action == "seer_peek":
            if player["role"] != "Voyante" or self.pending_night.get("seer_done", False):
                return {"type": "error", "message": "Action voyante indisponible."}
            if target not in self.alive_ids() or target == player_id:
                return {"type": "error", "message": "Cible invalide."}
            result = f"{self.players[target]['name']} est {self.players[target]['role']}."
            self.pending_night[("seer_result", player_id)] = result
            self.pending_night["seer_done"] = True
            self.resolve_night_if_ready()
            return self.player_snapshot(player_id)

        if action == "witch_save":
            if player["role"] != "Sorcière" or self.pending_night.get("witch_done", False):
                return {"type": "error", "message": "Action sorciere indisponible."}
            if self.witch_heal_used:
                return {"type": "error", "message": "Potion de soin deja utilisee."}
            self.pending_night["saved"]      = True
            self.pending_night["witch_done"] = True
            self.witch_heal_used = True
            self.resolve_night_if_ready()
            return self.player_snapshot(player_id)

        if action == "witch_poison":
            if player["role"] != "Sorcière" or self.pending_night.get("witch_done", False):
                return {"type": "error", "message": "Action sorciere indisponible."}
            if self.witch_poison_used:
                return {"type": "error", "message": "Potion de mort deja utilisee."}
            if target not in self.alive_ids() or target == player_id:
                return {"type": "error", "message": "Cible invalide."}
            self.pending_night["poison_target"] = target
            self.pending_night["witch_done"]    = True
            self.witch_poison_used = True
            self.resolve_night_if_ready()
            return self.player_snapshot(player_id)

        if action == "witch_skip":
            if player["role"] != "Sorcière" or self.pending_night.get("witch_done", False):
                return {"type": "error", "message": "Action sorciere indisponible."}
            self.pending_night["witch_done"] = True
            self.resolve_night_if_ready()
            return self.player_snapshot(player_id)

        return {"type": "error", "message": "Action inconnue."}

    def handle_vote(self, player_id: int, msg: dict):
        if self.phase != "day":
            return {"type": "error", "message": "Ce n'est pas le moment de voter."}
        if not self.players[player_id]["alive"]:
            return {"type": "error", "message": "Tu es elimine."}
        target = msg.get("target")
        if target not in self.alive_ids() or target == player_id:
            return {"type": "error", "message": "Cible invalide."}
        self.day_votes[player_id] = target
        alive_voters = [p for p in self.players if p.get("connected") and p["alive"]]
        if len(self.day_votes) == len(alive_voters):
            counts = Counter(self.day_votes.values())
            chosen, _ = max(counts.items(), key=lambda x: (x[1], -x[0]))
            self.players[chosen]["alive"]         = False
            self.players[chosen]["revealed_role"] = self.players[chosen]["role"]
            self.last_deaths = [self.players[chosen]["name"]]
            self.winner = check_winner(self.players)
            if self.winner is not None:
                self.phase   = "end"
                self.message = (f"{self.players[chosen]['name']} elimine. "
                                f"Victoire : {self.winner} !")
            else:
                self.message = f"{self.players[chosen]['name']} elimine. La nuit tombe..."
                self.start_night()
                return self.player_snapshot(player_id)
        self.broadcast_snapshots()
        return self.player_snapshot(player_id)

    def handle_chat(self, player_id: int, msg: dict):
        raw = str(msg.get("message", "")).strip()
        if not raw:
            return self.player_snapshot(player_id)
        raw = raw[:220]

        player = self.players[player_id] if player_id < len(self.players) else None
        if player is None:
            return self.player_snapshot(player_id)

        # La nuit : seuls les loups peuvent écrire
        if self.phase == "night" and self.game_started:
            if not is_wolf_role(player.get("role", "")):
                return {"type": "error",
                        "message": "Seuls les loups-garous peuvent parler la nuit."}

        clean, flagged = self.moderator.moderate(raw)
        author = player.get("name", f"Joueur {player_id + 1}")
        if flagged:
            clean = "*" * len(raw)

        wolf_only = (self.phase == "night" and self.game_started
                     and is_wolf_role(player.get("role", "")))

        self.append_chat(author, clean, wolf_only=wolf_only)
        if flagged:
            self.append_chat("Systeme", f"Message de {author} modéré.", system=True)
        self.broadcast_snapshots()
        return self.player_snapshot(player_id)

    # ── Boucle serveur ───────────────────────────────────────────────────────

    def handle_client(self, conn, player_id: int):
        """Boucle de réception pour un client. Tourne dans son propre thread daemon.
        Toute mutation de l'état partagé est faite sous self.lock."""
        buf = ""
        try:
            while self.running:
                data = conn.recv(4096)
                if not data:
                    break
                buf += data.decode("utf-8")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    if not line.strip():
                        continue
                    msg = json.loads(line)
                    with self.lock:
                        kind = msg.get("type")
                        if kind == "join":
                            response = self.handle_join(player_id, msg)
                        elif kind == "update_role_config":
                            response = self.update_role_config(player_id, msg)
                        elif kind == "start_game":
                            response = self.start_game(player_id)
                        elif kind == "update_max_players":
                            response = self.update_max_players(player_id, msg)
                        elif kind == "night_action":
                            response = self.handle_night_action(player_id, msg)
                        elif kind == "vote_action":
                            response = self.handle_vote(player_id, msg)
                        elif kind == "chat_message":
                            response = self.handle_chat(player_id, msg)
                        elif kind == "sync_request":
                            response = self.player_snapshot(player_id)
                        else:
                            response = {"type": "error", "message": "Commande inconnue."}
                    if response is not None:
                        self.send_json(conn, response)
        except (ConnectionResetError, json.JSONDecodeError, OSError):
            pass
        except Exception as e:
            print(f"[SERVEUR] Erreur inattendue joueur {player_id}: {e}")
        finally:
            with self.lock:
                if player_id < len(self.clients) and self.clients[player_id] is conn:
                    self.remove_client(player_id)
            try:
                conn.close()
            except OSError:
                pass

    def shutdown(self):
        self.running = False
        self.broadcaster.stop()
        with self.lock:
            for i, conn in enumerate(self.clients):
                if conn is not None:
                    try:
                        self.send_json(conn, {"type": "info", "message": "Le serveur s'arrete."})
                    except OSError:
                        pass
                    try:
                        conn.close()
                    except OSError:
                        pass
                    self.clients[i] = None
        try:
            self.server.close()
        except OSError:
            pass

    def serve_forever(self):
        try:
            self.server.bind((self.host, self.port))
        except OSError as e:
            print(f"[SERVEUR] Impossible de binder sur {self.host}:{self.port} : {e}")
            if self.ready_event:
                self.ready_event.set()   # débloque l'attente côté main (bind_ok reste False)
            return

        self.server.listen(MAX_PLAYERS + 2)
        # Timeout sur accept() pour que la boucle puisse vérifier self.running régulièrement
        self.server.settimeout(1.0)
        self.broadcaster.start()
        self.bind_ok = True

        # Signale au Launcher que le socket est prêt → il peut se connecter en client
        if self.ready_event:
            self.ready_event.set()

        print(f"[SERVEUR] Lance sur {self.host}:{self.port}")
        print(f"[SERVEUR] IP locale : {self.host_ip}")
        print(f"[SERVEUR] Config : max {self.max_players} | {role_config_label(self.role_config)}")

        while self.running:
            try:
                conn, addr = self.server.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            with self.lock:
                # Trouver un slot libre ou en créer un nouveau
                try:
                    player_id = self.clients.index(None)
                except ValueError:
                    if len(self.clients) < MAX_PLAYERS:
                        player_id = len(self.clients)
                        self.clients.append(None)
                    else:
                        self.send_json(conn, {"type": "error", "message": "Serveur plein."})
                        conn.close()
                        continue
                self.clients[player_id] = conn
                self.broadcaster.set_player_count(self.connected_player_count())

            print(f"[SERVEUR] Joueur {player_id + 1} connecte depuis {addr}")
            threading.Thread(target=self.handle_client,
                             args=(conn, player_id), daemon=True).start()


if __name__ == "__main__":
    server = WerewolfServer()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArret demande.")
    finally:
        server.shutdown()
