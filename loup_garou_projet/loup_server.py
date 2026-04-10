
import json
import random
import socket
import threading
from collections import Counter
from pathlib import Path

from chat_moderation import ChatModerator
from loup_shared import (
    MIN_PLAYERS,
    MAX_PLAYERS,
    ROLE_DEFS,
    build_roles,
    check_winner,
    get_role_def,
    role_config_label,
    serialize_players_for,
    team_of,
)
from server_discovery import ServerBroadcaster, get_local_ip

HOST = "0.0.0.0"
PORT = 5555
BASE_DIR = Path(__file__).resolve().parent
MODERATION_CSV = BASE_DIR / "moderation_loup_garou_fr_en.csv"


class WerewolfServer:
    def __init__(self, host_name="Joueur", host=HOST, port=PORT, max_players=MAX_PLAYERS, role_config=None):
        self.host = host
        self.port = port
        self.server_name = f"Salon de {host_name}"
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.lock = threading.Lock()
        self.running = True
        self.host_ip = get_local_ip()
        self.max_players = max(MIN_PLAYERS, min(MAX_PLAYERS, int(max_players)))
        self.role_config = role_config or {"Loup-garou": 1, "Voyante": 1, "Sorciere": 1}
        self.broadcaster = ServerBroadcaster(self.server_name, host_ip=self.host_ip, game_port=self.port)
        self.broadcaster.set_room_config(self.max_players, role_config_label(self.role_config))
        self.clients = [None] * self.max_players
        self.chat_history = []
        self.moderator = ChatModerator(MODERATION_CSV)
        self.reset_lobby_state()

    def reset_lobby_state(self):
        self.players = []
        self.host_id = 0
        self.game_started = False
        self.phase = "lobby"
        self.day_count = 0
        self.winner = None
        self.message = "En attente des joueurs."
        self.last_deaths = []
        self.pending_night = {}
        self.day_votes = {}
        self.witch_heal_used = False
        self.witch_poison_used = False
        self.pending_wolf_target = None
        self.resume_phase = None
        self.pending_hunter_queue = []
        self.pending_hunter_id = None

    def connected_player_count(self):
        return sum(1 for c in self.clients if c is not None)

    def send_json(self, conn, data):
        conn.sendall((json.dumps(data) + "\n").encode("utf-8"))

    def append_chat(self, author, message, system=False):
        entry = {"author": author, "message": message[:220], "system": system}
        self.chat_history.append(entry)
        self.chat_history = self.chat_history[-60:]

    def role_note_for(self, player):
        notes = []
        if player["role"] == "Sniper" and player.get("sniper_target_name"):
            status = "objectif accompli" if player.get("sniper_ready") else f"cible : {player['sniper_target_name']}"
            notes.append(status)
        if player.get("lover_ids"):
            lover_names = [self.players[i]["name"] for i in player["lover_ids"] if i < len(self.players)]
            if lover_names:
                notes.append("amoureux : " + ", ".join(lover_names))
        if player["role"] == "Enfant sauvage" and player.get("mentor_id") is not None:
            notes.append("mentor : " + self.players[player["mentor_id"]]["name"])
        if player["role"] == "Renard" and not player.get("renard_active", True):
            notes.append("flair perdu")
        if player["role"] == "Pyroman":
            doused_names = [p["name"] for p in self.players if p.get("doused")]
            if doused_names:
                notes.append("joueurs arrosés : " + ", ".join(doused_names[:4]))
        if player["role"] == "Sirène":
            charmed = [p["name"] for p in self.players if p.get("charmed_by") == player["id"]]
            if charmed:
                notes.append("envoûtés : " + ", ".join(charmed[:4]))
        return " | ".join(notes)

    def available_actions_for(self, player_id):
        if player_id >= len(self.players):
            return []
        player = self.players[player_id]
        actions = []
        if self.phase == "lobby":
            return actions
        if self.phase == "hunter" and player_id == self.pending_hunter_id:
            alive_targets = [p for p in self.players if p["alive"] and p["id"] != player_id]
            if alive_targets:
                actions.append({"id": "hunter_shot", "label": "TIRER", "min_targets": 1, "max_targets": 1})
            return actions
        if not player["alive"]:
            return actions
        role = player["role"]
        if self.phase == "day":
            actions.append({"id": "vote", "label": "VOTER", "min_targets": 1, "max_targets": 1})
            return actions
        if self.phase != "night":
            return actions

        done = self.pending_night.get("done", set())

        if role in ("Loup-garou", "Infect Père des Loups") and player_id not in done:
            actions.append({"id": "wolf_kill", "label": "ATTAQUER", "min_targets": 1, "max_targets": 1})
        if role == "Voyante" and player_id not in done:
            actions.append({"id": "seer_peek", "label": "RÉVÉLER", "min_targets": 1, "max_targets": 1})
        if role == "Sorciere" and player_id not in done:
            if self.pending_wolf_target is not None and not self.witch_heal_used:
                actions.append({"id": "witch_save", "label": "SAUVER", "min_targets": 0, "max_targets": 0})
            if not self.witch_poison_used and self.day_count > 1:
                actions.append({"id": "witch_poison", "label": "EMPOISONNER", "min_targets": 1, "max_targets": 1})
            actions.append({"id": "witch_skip", "label": "PASSER", "min_targets": 0, "max_targets": 0})
        if role == "Salvateur" and player_id not in done:
            actions.append({"id": "salvator_guard", "label": "PROTÉGER", "min_targets": 1, "max_targets": 1})
        if role == "Cupidon" and self.day_count == 1 and player_id not in done and not player.get("couple_done"):
            actions.append({"id": "cupidon_link", "label": "LIER", "min_targets": 2, "max_targets": 2})
        if role == "Renard" and player_id not in done and player.get("renard_active", True):
            actions.append({"id": "renard_sniff", "label": "RENIFLER", "min_targets": 3, "max_targets": 3})
        if role == "Enfant sauvage" and self.day_count == 1 and player_id not in done and player.get("mentor_id") is None:
            actions.append({"id": "wild_child_mentor", "label": "CHOISIR MENTOR", "min_targets": 1, "max_targets": 1})
        if role == "Sirène" and player_id not in done:
            actions.append({"id": "sirene_enchant", "label": "ENVOÛTER", "min_targets": 3, "max_targets": 3})
            if any(p.get("charmed_by") == player_id and p["alive"] for p in self.players):
                actions.append({"id": "sirene_kill", "label": "TUER ENVOÛTÉS", "min_targets": 1, "max_targets": 2})
        if role == "Pyroman" and player_id not in done:
            actions.append({"id": "pyro_douse", "label": "ARROSER", "min_targets": 2, "max_targets": 2})
            if any(p.get("doused") and p["alive"] for p in self.players):
                actions.append({"id": "pyro_ignite", "label": "BRÛLER", "min_targets": 0, "max_targets": 0})
        return actions

    def player_snapshot(self, player_id):
        player = self.players[player_id]
        role_name = player["role"] if self.game_started else None
        role_card = None
        if role_name:
            role_def = get_role_def(role_name)
            role_card = {
                "name": role_name,
                "camp": role_def["camp"],
                "aura": role_def["aura"],
                "description": role_def["description"],
            }

        action_hint = self.message
        actions = self.available_actions_for(player_id)
        if self.phase == "night" and actions:
            role = player["role"]
            hints = {
                "Loup-garou": "Choisis une victime parmi les autres joueurs vivants.",
                "Infect Père des Loups": "Comme loup spécial, ton vote compte double cette nuit.",
                "Voyante": "Choisis un joueur pour découvrir son rôle.",
                "Sorciere": "Tu peux sauver, empoisonner ou passer.",
                "Salvateur": "Choisis un joueur à protéger cette nuit.",
                "Cupidon": "Choisis les deux amoureux.",
                "Renard": "Choisis trois joueurs pour flairer la présence d'un loup.",
                "Enfant sauvage": "Choisis ton mentor.",
                "Sirène": "Envoûte trois joueurs, ou tue des joueurs déjà envoûtés.",
                "Pyroman": "Arrose deux joueurs, ou brûle tous ceux déjà arrosés.",
            }
            action_hint = hints.get(role, action_hint)
        elif self.phase == "day" and player["alive"]:
            action_hint = "Vote contre un joueur vivant que tu suspectes."
        elif self.phase == "hunter" and player_id == self.pending_hunter_id:
            action_hint = "Tu es chasseur : choisis un joueur à éliminer avant de quitter la partie."

        return {
            "type": "state_sync",
            "server_name": self.server_name,
            "phase": self.phase,
            "day_count": self.day_count,
            "your_id": player_id,
            "host_id": self.host_id,
            "players": serialize_players_for(player_id, self.players, reveal_all=self.winner is not None),
            "game_started": self.game_started,
            "winner": self.winner,
            "message": self.message,
            "last_deaths": list(self.last_deaths),
            "night_target_name": self.players[self.pending_wolf_target]["name"] if self.pending_wolf_target is not None and player["role"] == "Sorciere" else None,
            "can_act": bool(actions),
            "action_hint": action_hint,
            "seer_result": self.pending_night.get("seer_results", {}).get(player_id),
            "connected_count": self.connected_player_count(),
            "max_players": self.max_players,
            "role_config": self.role_config,
            "chat_history": list(self.chat_history),
            "available_actions": actions,
            "your_role_card": role_card,
            "role_note": self.role_note_for(player),
        }

    def broadcast_snapshots(self):
        for player in self.players:
            conn = self.clients[player["id"]] if player["id"] < len(self.clients) else None
            if conn is None or not player.get("connected"):
                continue
            try:
                self.send_json(conn, self.player_snapshot(player["id"]))
            except OSError:
                pass

    def remove_client(self, player_id):
        self.clients[player_id] = None
        if player_id < len(self.players):
            self.players[player_id]["alive"] = False
            self.players[player_id]["connected"] = False
            self.append_chat("Système", f"{self.players[player_id]['name']} a quitté la partie.", system=True)
        self.broadcaster.set_player_count(self.connected_player_count())
        self.message = "Un joueur s'est déconnecté."
        self.winner = check_winner(self.players) if self.game_started else None
        self.broadcast_snapshots()

    def handle_join(self, player_id, msg):
        name = str(msg.get("name", "")).strip()[:20] or f"Joueur {player_id + 1}"
        while len(self.players) <= player_id:
            self.players.append({
                "id": len(self.players),
                "name": f"Joueur {len(self.players) + 1}",
                "role": None,
                "alive": True,
                "connected": False,
                "revealed_role": None,
                "lover_ids": [],
                "mentor_id": None,
                "renard_active": True,
                "charmed_by": None,
                "doused": False,
                "sniper_target": None,
                "sniper_target_name": None,
                "sniper_ready": False,
                "last_guard_target": None,
                "couple_done": False,
            })
        self.players[player_id].update({"name": name, "connected": True, "alive": True})
        self.message = f"{name} a rejoint la partie."
        self.append_chat("Système", self.message, system=True)
        self.broadcaster.set_player_count(self.connected_player_count())
        self.broadcast_snapshots()
        return self.player_snapshot(player_id)

    def start_game(self, player_id):
        if player_id != self.host_id:
            return {"type": "error", "message": "Seul l'hôte peut lancer la partie."}
        active_players = [p for p in self.players if p.get("connected")]
        if len(active_players) < MIN_PLAYERS:
            return {"type": "error", "message": f"Il faut au moins {MIN_PLAYERS} joueurs."}
        try:
            roles = build_roles(len(active_players), self.role_config)
        except ValueError as exc:
            return {"type": "error", "message": str(exc)}

        for p, role in zip(active_players, roles):
            p.update({
                "role": role,
                "alive": True,
                "revealed_role": None,
                "lover_ids": [],
                "mentor_id": None,
                "renard_active": True,
                "charmed_by": None,
                "doused": False,
                "sniper_target": None,
                "sniper_target_name": None,
                "sniper_ready": False,
                "last_guard_target": None,
                "couple_done": False,
            })

        snipers = [p for p in active_players if p["role"] == "Sniper"]
        for sniper in snipers:
            targets = [p for p in active_players if p["id"] != sniper["id"]]
            if targets:
                target = random.choice(targets)
                sniper["sniper_target"] = target["id"]
                sniper["sniper_target_name"] = target["name"]

        self.game_started = True
        self.winner = None
        self.day_count = 0
        self.message = "La partie commence. La nuit tombe..."
        self.append_chat("Système", f"La partie démarre avec {role_config_label(self.role_config)}.", system=True)
        self.start_night()
        return None

    def alive_ids(self, exclude=None):
        return [p["id"] for p in self.players if p.get("connected") and p["alive"] and p["id"] != exclude]

    def start_night(self):
        self.phase = "night"
        self.day_count += 1
        self.last_deaths = []
        self.pending_night = {
            "done": set(),
            "seer_results": {},
            "wolf_votes": [],
            "protected": set(),
            "special_kills": set(),
            "saved": False,
        }
        self.day_votes = {}
        self.pending_wolf_target = None
        self.message = f"Nuit {self.day_count} : les rôles de nuit agissent."
        self.broadcast_snapshots()

    def weighted_wolf_target(self):
        votes = self.pending_night.get("wolf_votes", [])
        if not votes:
            return None
        counts = Counter()
        for _, target, weight in votes:
            counts[target] += weight
        return max(counts.items(), key=lambda x: (x[1], -x[0]))[0]

    def mark_done(self, player_id):
        self.pending_night.setdefault("done", set()).add(player_id)

    def night_players_waiting(self):
        waiting = []
        for p in self.players:
            if p.get("connected") and self.available_actions_for(p["id"]):
                waiting.append(p["id"])
        return waiting

    def apply_death_queue(self, initial_ids):
        queue = list(initial_ids)
        processed = []
        while queue:
            pid = queue.pop(0)
            if pid is None or pid >= len(self.players):
                continue
            player = self.players[pid]
            if not player["alive"]:
                continue
            player["alive"] = False
            player["revealed_role"] = player["role"]
            processed.append(pid)

            if player["role"] == "Sirène":
                for other in self.players:
                    if other["alive"] and other.get("charmed_by") == pid:
                        queue.append(other["id"])

            for lover_id in player.get("lover_ids", []):
                if lover_id < len(self.players) and self.players[lover_id]["alive"]:
                    queue.append(lover_id)

            for child in self.players:
                if child["alive"] and child["role"] == "Enfant sauvage" and child.get("mentor_id") == pid:
                    child["role"] = "Loup-garou"
                    self.append_chat("Système", f"{child['name']} a sombré du côté des loups.", system=True)

            if player["role"] == "Chasseur":
                self.pending_hunter_queue.append(pid)

        return processed

    def finalize_after_deaths(self, next_phase):
        self.winner = check_winner(self.players)
        if self.winner is not None:
            self.phase = "end"
            self.message = f"Victoire du camp : {self.winner}."
            self.broadcast_snapshots()
            return

        if self.pending_hunter_queue:
            self.phase = "hunter"
            self.resume_phase = next_phase
            self.pending_hunter_id = self.pending_hunter_queue.pop(0)
            self.message = f"{self.players[self.pending_hunter_id]['name']} peut tirer une dernière fois."
            self.broadcast_snapshots()
            return

        if next_phase == "day":
            self.phase = "day"
            if self.last_deaths:
                self.message = "Jour : " + ", ".join(self.last_deaths) + " a/ont été éliminé(s). Votez."
            else:
                self.message = "Jour : personne n'est mort cette nuit. Votez."
        else:
            self.start_night()
            return
        self.broadcast_snapshots()

    def resolve_night_if_ready(self):
        waiting = self.night_players_waiting()
        if waiting:
            return

        self.pending_wolf_target = self.weighted_wolf_target()
        deaths = set(self.pending_night.get("special_kills", set()))

        wolf_target = self.pending_wolf_target
        if wolf_target is not None:
            target_player = self.players[wolf_target]
            if target_player["role"] == "Villageois maudit":
                target_player["role"] = "Loup-garou"
                self.append_chat("Système", f"{target_player['name']} a été corrompu par les loups.", system=True)
            elif not self.pending_night.get("saved") and wolf_target not in self.pending_night.get("protected", set()):
                deaths.add(wolf_target)

        poison_target = self.pending_night.get("poison_target")
        if poison_target is not None:
            deaths.add(poison_target)

        ignite = self.pending_night.get("ignite", False)
        if ignite:
            for p in self.players:
                if p["alive"] and p.get("doused"):
                    deaths.add(p["id"])
                    p["doused"] = False

        dead_ids = self.apply_death_queue(deaths)
        self.last_deaths = [self.players[pid]["name"] for pid in dead_ids]
        self.finalize_after_deaths("day")

    def validate_targets(self, player_id, targets, min_targets=1, max_targets=1, allow_self=False):
        if not isinstance(targets, list):
            return False, "Cibles invalides."
        uniq = []
        for t in targets:
            if isinstance(t, int) and t not in uniq:
                uniq.append(t)
        targets = uniq
        if len(targets) < min_targets or len(targets) > max_targets:
            return False, "Nombre de cibles invalide."
        for t in targets:
            if t >= len(self.players) or not self.players[t]["alive"]:
                return False, "Une cible n'est pas valide."
            if not allow_self and t == player_id:
                return False, "Tu ne peux pas te cibler."
        return True, targets

    def handle_game_action(self, player_id, msg):
        if player_id >= len(self.players):
            return {"type": "error", "message": "Joueur inconnu."}
        player = self.players[player_id]
        action = msg.get("action")
        targets = msg.get("targets", [])
        role = player["role"]

        if self.phase == "hunter":
            if player_id != self.pending_hunter_id:
                return {"type": "error", "message": "Ce n'est pas à toi de tirer."}
            ok, targets = self.validate_targets(player_id, targets, 1, 1)
            if not ok:
                return {"type": "error", "message": targets}
            dead_ids = self.apply_death_queue(targets)
            self.last_deaths.extend(self.players[pid]["name"] for pid in dead_ids if self.players[pid]["name"] not in self.last_deaths)
            if self.pending_hunter_queue:
                self.pending_hunter_id = self.pending_hunter_queue.pop(0)
                self.message = f"{self.players[self.pending_hunter_id]['name']} peut tirer une dernière fois."
                self.broadcast_snapshots()
            else:
                phase = self.resume_phase or "day"
                self.pending_hunter_id = None
                self.finalize_after_deaths(phase)
            return self.player_snapshot(player_id)

        if self.phase == "day":
            if not player["alive"]:
                return {"type": "error", "message": "Tu es éliminé."}
            if action != "vote":
                return {"type": "error", "message": "Action de jour invalide."}
            ok, targets = self.validate_targets(player_id, targets, 1, 1)
            if not ok:
                return {"type": "error", "message": targets}
            target = targets[0]
            self.day_votes[player_id] = target
            alive_voters = [p for p in self.players if p.get("connected") and p["alive"]]
            if len(self.day_votes) == len(alive_voters):
                counts = Counter(self.day_votes.values())
                chosen, _ = max(counts.items(), key=lambda x: (x[1], -x[0]))
                dead_ids = self.apply_death_queue([chosen])

                for sniper in self.players:
                    if sniper.get("role") == "Sniper" and sniper["alive"] and sniper.get("sniper_target") == chosen:
                        sniper["sniper_ready"] = True

                self.last_deaths = [self.players[pid]["name"] for pid in dead_ids]
                self.message = f"{self.players[chosen]['name']} a été éliminé."
                self.finalize_after_deaths("night")
                return self.player_snapshot(player_id)
            self.broadcast_snapshots()
            return self.player_snapshot(player_id)

        if self.phase != "night":
            return {"type": "error", "message": "Aucune action possible maintenant."}
        if not player["alive"]:
            return {"type": "error", "message": "Tu es éliminé."}

        done = self.pending_night.setdefault("done", set())
        if player_id in done:
            return {"type": "error", "message": "Tu as déjà joué cette nuit."}

        if action == "wolf_kill" and role in ("Loup-garou", "Infect Père des Loups"):
            ok, targets = self.validate_targets(player_id, targets, 1, 1)
            if not ok:
                return {"type": "error", "message": targets}
            weight = 2 if role == "Infect Père des Loups" else 1
            self.pending_night["wolf_votes"].append((player_id, targets[0], weight))
            self.mark_done(player_id)
        elif action == "seer_peek" and role == "Voyante":
            ok, targets = self.validate_targets(player_id, targets, 1, 1)
            if not ok:
                return {"type": "error", "message": targets}
            target = targets[0]
            self.pending_night["seer_results"][player_id] = f"{self.players[target]['name']} est {self.players[target]['role']}."
            self.mark_done(player_id)
        elif action == "witch_save" and role == "Sorciere":
            self.pending_night["saved"] = True
            self.witch_heal_used = True
            self.mark_done(player_id)
        elif action == "witch_poison" and role == "Sorciere":
            if self.day_count == 1:
                return {"type": "error", "message": "La potion de mort est bloquée la première nuit."}
            ok, targets = self.validate_targets(player_id, targets, 1, 1)
            if not ok:
                return {"type": "error", "message": targets}
            self.pending_night["poison_target"] = targets[0]
            self.witch_poison_used = True
            self.mark_done(player_id)
        elif action == "witch_skip" and role == "Sorciere":
            self.mark_done(player_id)
        elif action == "salvator_guard" and role == "Salvateur":
            ok, targets = self.validate_targets(player_id, targets, 1, 1)
            if not ok:
                return {"type": "error", "message": targets}
            if player.get("last_guard_target") == targets[0]:
                return {"type": "error", "message": "Tu ne peux pas protéger deux nuits de suite la même personne."}
            player["last_guard_target"] = targets[0]
            self.pending_night["protected"].add(targets[0])
            self.mark_done(player_id)
        elif action == "cupidon_link" and role == "Cupidon" and self.day_count == 1:
            ok, targets = self.validate_targets(player_id, targets, 2, 2)
            if not ok:
                return {"type": "error", "message": targets}
            a, b = targets
            self.players[a]["lover_ids"] = [b]
            self.players[b]["lover_ids"] = [a]
            player["couple_done"] = True
            self.append_chat("Système", f"Deux amoureux se sont trouvés cette nuit.", system=True)
            self.mark_done(player_id)
        elif action == "renard_sniff" and role == "Renard" and player.get("renard_active", True):
            ok, targets = self.validate_targets(player_id, targets, 3, 3)
            if not ok:
                return {"type": "error", "message": targets}
            found = any(team_of(self.players[t]) == "Loups" for t in targets)
            if found:
                self.pending_night["seer_results"][player_id] = "Ton flair détecte au moins un loup parmi les trois cibles."
            else:
                self.pending_night["seer_results"][player_id] = "Aucun loup détecté. Tu perds ton flair et deviens villageois."
                player["renard_active"] = False
                player["role"] = "Villageois"
            self.mark_done(player_id)
        elif action == "wild_child_mentor" and role == "Enfant sauvage" and self.day_count == 1:
            ok, targets = self.validate_targets(player_id, targets, 1, 1)
            if not ok:
                return {"type": "error", "message": targets}
            player["mentor_id"] = targets[0]
            self.mark_done(player_id)
        elif action == "sirene_enchant" and role == "Sirène":
            ok, targets = self.validate_targets(player_id, targets, 3, 3)
            if not ok:
                return {"type": "error", "message": targets}
            for t in targets:
                self.players[t]["charmed_by"] = player_id
            self.mark_done(player_id)
        elif action == "sirene_kill" and role == "Sirène":
            ok, targets = self.validate_targets(player_id, targets, 1, 2)
            if not ok:
                return {"type": "error", "message": targets}
            if not all(self.players[t].get("charmed_by") == player_id for t in targets):
                return {"type": "error", "message": "Tu ne peux tuer que des joueurs déjà envoûtés par toi."}
            self.pending_night["special_kills"].update(targets)
            self.mark_done(player_id)
        elif action == "pyro_douse" and role == "Pyroman":
            ok, targets = self.validate_targets(player_id, targets, 2, 2)
            if not ok:
                return {"type": "error", "message": targets}
            for t in targets:
                self.players[t]["doused"] = True
            self.mark_done(player_id)
        elif action == "pyro_ignite" and role == "Pyroman":
            self.pending_night["ignite"] = True
            self.mark_done(player_id)
        else:
            return {"type": "error", "message": "Action inconnue ou indisponible."}

        self.resolve_night_if_ready()
        self.broadcast_snapshots()
        return self.player_snapshot(player_id)

    def handle_chat(self, player_id, msg):
        raw = str(msg.get("message", "")).strip()
        if not raw:
            return self.player_snapshot(player_id)
        raw = raw[:220]
        clean, flagged = self.moderator.moderate(raw)
        author = self.players[player_id]["name"] if player_id < len(self.players) else f"Joueur {player_id + 1}"

        if flagged:
            clean = "*" * len(raw)

        self.append_chat(author, clean)
        if flagged:
            self.append_chat("Système", f"Un message de {author} a été modéré automatiquement.", system=True)
        self.broadcast_snapshots()
        return self.player_snapshot(player_id)

    def handle_client(self, conn, player_id):
        buffer = ""
        try:
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
                        elif kind == "start_game":
                            response = self.start_game(player_id)
                        elif kind == "game_action":
                            response = self.handle_game_action(player_id, msg)
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
                        self.send_json(conn, {"type": "info", "message": "Le serveur s'arrête."})
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
        self.server.bind((self.host, self.port))
        self.server.listen(self.max_players)
        self.server.settimeout(1.0)
        self.broadcaster.start()
        print(f"Serveur lancé sur {self.host}:{self.port}")
        print(f"IP locale du serveur : {self.host_ip}")
        print(f"Configuration : max {self.max_players} joueurs | {role_config_label(self.role_config)}")
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


if __name__ == "__main__":
    server = WerewolfServer()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt demandé par l'utilisateur...")
    finally:
        server.shutdown()
