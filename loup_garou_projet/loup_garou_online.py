"""
loup_garou_online.py – Interface graphique du mode multijoueur.

Communique avec loup_server.py via NetworkClient (JSON sur TCP).
L'état de jeu arrive entièrement du serveur via des paquets "state_sync" :
le client ne calcule rien lui-même, il affiche et envoie des actions.
"""
import json
import socket
import threading

import pygame

from loup_shared import (
    MIN_PLAYERS, MAX_PLAYERS,
    ROLE_CATALOG, CLASSIC_ROLE_NAMES, SPECIAL_ROLE_NAMES,
    camp_balance, min_players_for_config, normalize_role_config, role_config_error,
    is_wolf_role,
)
from loup_ui_theme import (
    WOLF_RED, BLOOD_RED,
    MIST_PURPLE, MIST_LIGHT,
    GOLD_WARM, GOLD_PALE,
    CYAN_COOL, WHITE_SOFT, GREY_DIM, GREY_DARK,
    MOON_SILVER,
    ROLE_WOLF_CLR, ROLE_VILLAGE_CLR,
    BTN_PRIMARY, BTN_PRIMARY_H,
    BTN_DANGER,
    BTN_SUCCESS, BTN_SUCCESS_H,
    BTN_NEUTRAL, BTN_NEUTRAL_H,
    BTN_BORDER,
    draw_gradient_bg, draw_glass_panel, draw_text, wrap_text,
    draw_moon, draw_tree_silhouette,
    ParticleSystem, Button, InputBox,
    scaled_fonts,
)

BASE_W, BASE_H = 1380, 900
MIN_W,  MIN_H  = 1060, 720
FPS = 60

BAR_VILLAGE = (32,  90, 160)
BAR_WOLVES  = (150, 18,  32)

ROLE_CAMP_COLOR = {
    "Loups":   ROLE_WOLF_CLR,
    "Village": ROLE_VILLAGE_CLR,
    "Solo":    (100, 60, 20),
    "Village / Loups": (80, 80, 40),
}

NIGHT_BG_TOP = (6,   4,  14)
NIGHT_BG_BOT = (30, 16,  50)
DAY_BG_TOP   = (30, 55,  80)
DAY_BG_BOT   = (70, 100, 60)


# ── Réseau ────────────────────────────────────────────────────────────────────

class NetworkClient:
    def __init__(self, host: str, player_name: str, port: int = 5555):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(8)
        self.sock.connect((host, port))
        self.sock.settimeout(None)
        self.messages: list = []
        self.lock = threading.Lock()
        self.running = True
        threading.Thread(target=self._listen, daemon=True).start()
        self.send({"type": "join", "name": player_name})

    def _listen(self):
        """Lit les messages entrants. Protocole : JSON terminé par '\n', un message par ligne.
        Le buffer accumule les données partielles jusqu'à trouver un '\n' complet."""
        buf = ""
        try:
            while self.running:
                data = self.sock.recv(4096)
                if not data:
                    break
                buf += data.decode("utf-8")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    if line.strip():
                        with self.lock:
                            self.messages.append(json.loads(line))
        except (OSError, json.JSONDecodeError):
            pass
        finally:
            self.running = False

    def send(self, payload: dict):
        try:
            self.sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        except OSError:
            self.running = False

    def pop_messages(self) -> list:
        with self.lock:
            msgs = self.messages[:]
            self.messages.clear()
        return msgs

    def close(self):
        self.running = False
        try:
            self.sock.close()
        except OSError:
            pass


# ── Jeu en ligne ──────────────────────────────────────────────────────────────

class WerewolfOnlineGame:
    def __init__(self, host: str, player_name: str):
        pygame.init()
        self.screen = pygame.display.set_mode((BASE_W, BASE_H), pygame.RESIZABLE)
        pygame.display.set_caption("Loup-Garou - En ligne")
        self.clock  = pygame.time.Clock()
        self.t      = 0.0
        self.network = NetworkClient(host, player_name)
        self.running = True

        # État
        self.state       = "connecting"
        self.server_name = "Salon"
        self.message     = "Connexion au serveur..."
        self.action_hint = ""
        self.players: list     = []
        self.your_id           = None
        self.host_id           = None
        self.phase             = "lobby"
        self.prev_phase        = None
        self.day_count         = 0
        self.winner            = None
        self.selected_target   = None
        self.last_deaths: list = []
        self.night_target_name = None
        self.seer_result       = None
        self.can_act           = False
        self.can_chat          = True
        self.has_voted         = False
        self.votes_cast        = 0
        self.votes_needed      = 0
        self.witch_heal_available   = True
        self.witch_poison_available = True
        self.night_step        = "wolves"
        self.max_players       = 8
        self.role_config       = normalize_role_config({})
        self.chat_history: list = []
        self.chat_scroll        = 0
        self.role_scroll        = 0
        self.selected_role_name = CLASSIC_ROLE_NAMES[0]
        self.show_role_info     = False

        # Boutons
        self.btn_start       = Button("LANCER LA PARTIE",    BTN_SUCCESS, BTN_SUCCESS_H)
        self.btn_vote        = Button("VALIDER L'ACTION",    BTN_PRIMARY, BTN_PRIMARY_H)
        self.btn_sync        = Button("SYNC",                BTN_NEUTRAL, BTN_NEUTRAL_H)
        self.btn_skip        = Button("PASSER",              BTN_NEUTRAL, BTN_NEUTRAL_H)
        self.btn_save        = Button("SAUVER LA VICTIME",   BTN_SUCCESS, BTN_SUCCESS_H)
        self.btn_poison      = Button("EMPOISONNER",         (90, 24, 80), (120, 38, 108))
        self.btn_send_chat   = Button("ENVOYER",             BTN_PRIMARY, BTN_PRIMARY_H)
        self.btn_end         = Button("RETOUR AU MENU",      BTN_NEUTRAL, BTN_NEUTRAL_H)
        self.chat_input      = InputBox(placeholder="Écris un message...", max_len=220)

        self.player_rects: list    = []
        self.role_row_rects: dict  = {}
        self.role_minus_rects: dict = {}
        self.role_plus_rects: dict  = {}
        self.count_left_rect      = pygame.Rect(0, 0, 0, 0)
        self.count_right_rect     = pygame.Rect(0, 0, 0, 0)
        self.role_list_rect       = pygame.Rect(0, 0, 0, 0)
        self.role_info_close_rect = pygame.Rect(0, 0, 0, 0)
        self.btn_end_rect         = pygame.Rect(0, 0, 0, 0)

        self.particles = ParticleSystem(BASE_W, BASE_H, 35)
        self.compute_layout()

    # ── Fonts / Layout ───────────────────────────────────────────────────────

    def fonts(self) -> dict:
        w, h = self.screen.get_size()
        return scaled_fonts(w, h, BASE_W, BASE_H)

    def compute_layout(self):
        w, h = self.screen.get_size()
        pad = 16
        self.top_rect    = pygame.Rect(pad, pad, w - pad * 2, 66)
        self.left_rect   = pygame.Rect(pad, 90, int(w * 0.22), h - 150)
        self.center_rect = pygame.Rect(self.left_rect.right + pad, 90,
                                       int(w * 0.39), h - 150)
        self.chat_rect   = pygame.Rect(self.center_rect.right + pad, 90,
                                       w - self.left_rect.width - self.center_rect.width - pad * 4,
                                       h - 150)
        self.bottom_rect = pygame.Rect(pad, h - 50, w - pad * 2, 36)

        bx = self.center_rect.x + 20
        by = self.center_rect.bottom - 56
        full_w = self.center_rect.width - 40
        bw = min(250, full_w)
        skip_x = bx + bw + 10
        skip_w = max(80, self.center_rect.right - 20 - skip_x)

        self.btn_start.set_rect((bx, by, full_w, 44))
        self.btn_vote.set_rect ((bx, by, bw, 44))
        self.btn_skip.set_rect ((skip_x, by, skip_w, 44))
        self.btn_save.set_rect ((skip_x, by, skip_w, 44))

        # Boutons sorcière (3 colonnes égales)
        wb = max(70, full_w // 3 - 6)
        self.btn_save.set_rect  ((bx,            by, wb, 44))
        self.btn_poison.set_rect((bx + wb + 8,   by, wb, 44))
        self.btn_skip.set_rect  ((bx + wb*2 + 16, by, max(60, full_w - wb*2 - 16), 44))

        # Bouton fin de partie
        ew = min(300, full_w)
        self.btn_end.set_rect((self.center_rect.centerx - ew // 2, by, ew, 44))

        self.btn_sync.set_rect     ((self.top_rect.right - 110, self.top_rect.y + 13, 90, 38))
        self.chat_input.set_rect   ((self.chat_rect.x + 12, self.chat_rect.bottom - 54,
                                     self.chat_rect.width - 110, 40))
        self.btn_send_chat.set_rect((self.chat_rect.right - 96, self.chat_rect.bottom - 54, 80, 40))

        # Sous-zones lobby dans center_rect
        top_x = self.center_rect.x + 14
        top_w = self.center_rect.width - 28
        self.player_count_rect = pygame.Rect(top_x, self.center_rect.y + 80,  top_w, 96)
        self.balance_rect      = pygame.Rect(top_x, self.center_rect.y + 188, top_w, 76)
        self.roles_title_y     = self.center_rect.y + 278
        self.roles_notice_y    = self.center_rect.y + 320
        role_list_top          = self.center_rect.y + 350
        role_list_bot          = self.center_rect.bottom - 70
        self.role_list_rect    = pygame.Rect(top_x, role_list_top,
                                             top_w, max(60, role_list_bot - role_list_top))

    # ── Accesseurs ───────────────────────────────────────────────────────────

    def current_role(self):
        if self.your_id is None:
            return None
        for p in self.players:
            if p["id"] == self.your_id:
                return p.get("role")
        return None

    def is_host(self) -> bool:
        return self.your_id is not None and self.your_id == self.host_id

    # ── Réseau ───────────────────────────────────────────────────────────────

    def process_network(self):
        for msg in self.network.pop_messages():
            mt = msg.get("type")
            if mt == "state_sync":
                self.state             = "game"
                self.server_name       = msg.get("server_name", self.server_name)
                new_phase              = msg.get("phase", "lobby")
                self.day_count         = msg.get("day_count", 0)
                self.players           = msg.get("players", [])
                self.your_id           = msg.get("your_id", self.your_id)
                self.host_id           = msg.get("host_id", self.host_id)
                self.message           = msg.get("message", self.message)
                self.last_deaths       = msg.get("last_deaths", [])
                self.night_target_name = msg.get("night_target_name")
                self.winner            = msg.get("winner")
                self.can_act           = msg.get("can_act", False)
                self.can_chat          = msg.get("can_chat", True)
                self.has_voted         = msg.get("has_voted", False)
                self.votes_cast        = msg.get("votes_cast", 0)
                self.votes_needed      = msg.get("votes_needed", 0)
                self.action_hint       = msg.get("action_hint", "")
                self.seer_result       = msg.get("seer_result")
                self.max_players       = msg.get("max_players", self.max_players)
                self.witch_heal_available   = msg.get("witch_heal_available", self.witch_heal_available)
                self.witch_poison_available = msg.get("witch_poison_available", self.witch_poison_available)
                self.night_step  = msg.get("night_step", "wolves")
                self.role_config = normalize_role_config(
                    msg.get("role_config", self.role_config))

                # Réinitialise la sélection à chaque changement de phase
                if new_phase != self.prev_phase:
                    self.selected_target = None
                    self.prev_phase = new_phase
                self.phase = new_phase

                if (self.selected_role_name is None
                        or self.selected_role_name not in self.role_config):
                    self.selected_role_name = (CLASSIC_ROLE_NAMES[0]
                                               if CLASSIC_ROLE_NAMES else
                                               next(iter(self.role_config), None))
                old = len(self.chat_history)
                new_chat = msg.get("chat_history", [])
                if new_chat:
                    self.chat_history = new_chat
                if len(self.chat_history) > old:
                    self.chat_scroll = 0
                # Annule la sélection si le joueur ciblé est mort
                if (self.selected_target is not None
                        and all(p["id"] != self.selected_target or not p["alive"]
                                for p in self.players)):
                    self.selected_target = None
            elif mt == "error":
                self.message = "⚠ " + msg.get("message", "")
            elif mt == "info":
                self.message = msg.get("message", self.message)

    def _send_role_config_update(self, role_name: str, delta: int):
        if not self.is_host() or self.phase != "lobby":
            return
        new = dict(self.role_config)
        cur = new.get(role_name, 0)
        mx  = ROLE_CATALOG[role_name]["max"]
        val = max(0, min(mx, cur + delta))
        if role_name == "Loup-garou":
            val = max(1, val)
        new[role_name] = val
        if sum(new.values()) >= MAX_PLAYERS:
            self.message = f"Trop de roles (max {MAX_PLAYERS} joueurs)."
            return
        if min_players_for_config(new) > MAX_PLAYERS:
            self.message = "Configuration impossible."
            return
        req = min_players_for_config(new)
        if self.max_players < req:
            self.network.send({"type": "update_max_players", "max_players": req})
        if new != self.role_config:
            self.network.send({"type": "update_role_config", "role_config": new})

    def _send_max_players_update(self, delta: int):
        if not self.is_host() or self.phase != "lobby":
            return
        req = min_players_for_config(self.role_config)
        tgt = max(MIN_PLAYERS, min(MAX_PLAYERS, self.max_players + delta))
        tgt = max(tgt, len(self.players), req)
        if tgt != self.max_players:
            self.network.send({"type": "update_max_players", "max_players": tgt})

    def send_action(self):
        role = self.current_role()
        if self.phase == "lobby":
            self.network.send({"type": "start_game"})
            return
        if self.phase == "day" and self.selected_target is not None:
            self.network.send({"type": "vote_action", "target": self.selected_target})
            self.selected_target = None
            return
        if self.phase == "night" and self.selected_target is not None:
            if is_wolf_role(role):
                self.network.send({"type": "night_action", "action": "wolf_kill",
                                   "target": self.selected_target})
                self.selected_target = None
            elif role == "Voyante":
                self.network.send({"type": "night_action", "action": "seer_peek",
                                   "target": self.selected_target})
                self.selected_target = None

    def send_witch_poison(self):
        if self.selected_target is not None:
            self.network.send({"type": "night_action", "action": "witch_poison",
                               "target": self.selected_target})
            self.selected_target = None

    def send_witch_skip(self):
        self.network.send({"type": "night_action", "action": "witch_skip"})

    def send_witch_save(self):
        self.network.send({"type": "night_action", "action": "witch_save"})

    def send_chat(self):
        txt = self.chat_input.consume()
        if txt:
            self.network.send({"type": "chat_message", "message": txt})

    # ── Fond animé ───────────────────────────────────────────────────────────

    def _draw_bg(self):
        w, h = self.screen.get_size()
        is_day = (self.phase == "day")
        if is_day:
            draw_gradient_bg(self.screen, DAY_BG_TOP, DAY_BG_BOT)
            sx, sy = int(w * 0.85), int(h * 0.12)
            sr = max(16, int(min(w, h) * 0.05))
            for step in range(5):
                hr = sr + step * 5
                ss = pygame.Surface((hr * 2 + 4, hr * 2 + 4), pygame.SRCALPHA)
                a = max(0, 38 - step * 8)
                pygame.draw.circle(ss, (255, 230, 100, a), (hr + 2, hr + 2), hr)
                self.screen.blit(ss, (sx - hr - 2, sy - hr - 2))
            pygame.draw.circle(self.screen, (255, 240, 120), (sx, sy), sr)
            tree_col = (18, 48, 24)
        else:
            draw_gradient_bg(self.screen, NIGHT_BG_TOP, NIGHT_BG_BOT)
            draw_moon(self.screen, int(w * 0.86), int(h * 0.13),
                      max(16, int(min(w, h) * 0.055)), self.t)
            tree_col = (5, 4, 12)

        for xi, hi in [(0.0, 0.18), (0.08, 0.14), (0.93, 0.16), (0.99, 0.18)]:
            draw_tree_silhouette(self.screen, int(xi * w), h, int(hi * h), tree_col)

        self.particles.update()
        self.particles.draw(self.screen)

    # ── Liste joueurs ────────────────────────────────────────────────────────

    def draw_player_list(self):
        f = self.fonts()
        draw_glass_panel(self.screen, self.left_rect, radius=22)
        draw_text(self.screen, "Joueurs", f["big"], MOON_SILVER,
                  topleft=(self.left_rect.x + 12, self.left_rect.y + 10), shadow=True)
        alive = sum(1 for p in self.players if p.get("alive"))
        draw_text(self.screen, f"{alive}/{len(self.players)}",
                  f["xs"], GOLD_PALE,
                  topleft=(self.left_rect.x + 12, self.left_rect.y + 48))

        self.player_rects = []
        y = self.left_rect.y + 72
        my_role = self.current_role() or ""

        for p in self.players:
            row_h = 50
            rect  = pygame.Rect(self.left_rect.x + 8, y, self.left_rect.width - 16, row_h)

            if y + row_h > self.left_rect.bottom - 6:
                break  # plus de place

            sel   = (p["id"] == self.selected_target)
            is_me = (p["id"] == self.your_id)
            dead  = not p["alive"]

            bg = (14, 10, 28) if dead else ((56, 34, 84) if sel else (26, 18, 48))
            pygame.draw.rect(self.screen, bg, rect, border_radius=12)
            pygame.draw.rect(self.screen, MIST_LIGHT if sel else (44, 36, 70),
                             rect, 2, border_radius=12)

            # Logique de révélation correcte (parenthèses explicites)
            both_wolves = is_wolf_role(my_role) and is_wolf_role(p.get("role", ""))
            reveal = dead or is_me or both_wolves
            role_str = (p.get("revealed_role") or p.get("role") or "?") if reveal else "?"

            bc = ROLE_WOLF_CLR if is_wolf_role(role_str) else MIST_PURPLE
            badge = pygame.Rect(rect.x + 7, rect.y + 9, 36, 28)
            pygame.draw.rect(self.screen, bc, badge, border_radius=8)
            draw_text(self.screen,
                      role_str[:2].upper() if role_str not in ("?",) else "?",
                      f["xs"], WHITE_SOFT, center=badge.center)

            name_col = GREY_DARK if dead else (GOLD_WARM if is_me else WHITE_SOFT)
            draw_text(self.screen, p["name"], f["xs"], name_col,
                      topleft=(rect.x + 50, rect.y + 5))
            draw_text(self.screen,
                      ("Elimine - " + role_str) if dead else role_str,
                      f["xs"], WOLF_RED if dead else CYAN_COOL,
                      topleft=(rect.x + 50, rect.y + 24))
            if is_me:
                pygame.draw.circle(self.screen, GOLD_WARM, (rect.right - 10, rect.centery), 5)
            if sel:
                pygame.draw.circle(self.screen, GOLD_WARM, (rect.right - 10, rect.centery), 6)

            self.player_rects.append((p["id"], rect))
            y += row_h + 4

    # ── Panneau Lobby ────────────────────────────────────────────────────────

    def draw_player_count_selector(self, rect: pygame.Rect, f: dict):
        draw_text(self.screen, "Joueurs dans le salon", f["medium"], MOON_SILVER,
                  topleft=(rect.x, rect.y + 4))
        pill = pygame.Rect(rect.x, rect.y + 36, rect.width, 44)
        pygame.draw.rect(self.screen, (10, 8, 24), pill, border_radius=22)

        slots = 5
        sw = max(1, pill.width // slots)
        vals = [max(MIN_PLAYERS, min(MAX_PLAYERS, self.max_players - 2 + i))
                for i in range(slots)]
        ax = pill.x + 2 * sw
        pygame.draw.rect(self.screen, MIST_PURPLE,
                         (ax + 3, pill.y + 3, sw - 6, pill.height - 6), border_radius=18)
        for i, v in enumerate(vals):
            cx = pill.x + sw * i + sw // 2
            col  = MOON_SILVER if i == 2 else GREY_DIM
            fnt  = f["medium"] if i == 2 else f["xs"]
            draw_text(self.screen, str(v), fnt, col, center=(cx, pill.centery))

        left_ok  = (self.is_host()
                    and self.max_players > max(MIN_PLAYERS, len(self.players),
                                               min_players_for_config(self.role_config)))
        right_ok = self.is_host() and self.max_players < MAX_PLAYERS
        self.count_left_rect  = pygame.Rect(pill.x + 4,      pill.y + 4, 36, 36)
        self.count_right_rect = pygame.Rect(pill.right - 40,  pill.y + 4, 36, 36)
        for r2, sym, ok in [(self.count_left_rect, "<", left_ok),
                            (self.count_right_rect, ">", right_ok)]:
            col = WHITE_SOFT if ok else GREY_DIM
            pygame.draw.ellipse(self.screen, col, r2)
            draw_text(self.screen, sym, f["medium"], (10, 8, 22), center=r2.center)

    def draw_balance_bar(self, rect: pygame.Rect, f: dict):
        bal = camp_balance(self.max_players, self.role_config)
        draw_text(self.screen, "Equilibre", f["medium"], MOON_SILVER,
                  topleft=(rect.x, rect.y + 2))
        label = ("Equilibre" if 0.38 < bal["village_ratio"] < 0.62
                 else ("Village favori" if bal["village_ratio"] > 0.62 else "Loups favoris"))
        draw_text(self.screen, label, f["xs"], GOLD_PALE,
                  topleft=(rect.x + rect.width // 3, rect.y + 4))
        bar = pygame.Rect(rect.x, rect.y + 32, rect.width, 16)
        vw = max(1, int(bar.width * bal["village_ratio"]))
        ww = max(1, bar.width - vw)
        pygame.draw.rect(self.screen, BAR_VILLAGE, (bar.x, bar.y, vw, bar.height), border_radius=8)
        pygame.draw.rect(self.screen, BAR_WOLVES,  (bar.x + vw, bar.y, ww, bar.height), border_radius=8)
        pygame.draw.ellipse(self.screen, WHITE_SOFT, (bar.x + vw - 8, bar.y - 3, 16, bar.height + 6))
        draw_text(self.screen, f"Connectes : {len(self.players)}/{self.max_players}",
                  f["xs"], CYAN_COOL, topleft=(rect.x, rect.y + 54))

    def draw_role_rows(self, f: dict):
        self.role_row_rects   = {}
        self.role_minus_rects = {}
        self.role_plus_rects  = {}

        sections = [("Roles classiques", CLASSIC_ROLE_NAMES),
                    ("Roles speciaux",   SPECIAL_ROLE_NAMES)]
        ROW_H   = 46
        HEAD_H  = 26
        GAP     = 4
        total_h = 0
        flat: list = []
        for title, names in sections:
            flat.append(("header", title))
            total_h += HEAD_H + 4
            for n in names:
                flat.append(("role", n))
                total_h += ROW_H + GAP
            total_h += 4

        vis_h   = self.role_list_rect.height - 8
        max_scr = max(0, total_h - vis_h)
        self.role_scroll = max(0, min(self.role_scroll, max_scr))
        cy      = self.role_list_rect.y + 4 - self.role_scroll
        # Clip pour masquer les lignes qui dépassent la zone scrollable
        old_clip = self.screen.get_clip()
        self.screen.set_clip(self.role_list_rect)
        mouse = pygame.mouse.get_pos()

        for kind, value in flat:
            if kind == "header":
                if cy + HEAD_H > self.role_list_rect.bottom and cy < self.role_list_rect.top:
                    cy += HEAD_H + 4
                    continue
                pygame.draw.rect(self.screen, (60, 44, 98),
                                 (self.role_list_rect.x + 4, cy,
                                  self.role_list_rect.width - 12, HEAD_H),
                                 border_radius=10)
                draw_text(self.screen, value, f["xs"], GOLD_PALE,
                          topleft=(self.role_list_rect.x + 12, cy + 4))
                cy += HEAD_H + 4
                continue

            rn  = value
            det = ROLE_CATALOG.get(rn)
            if det is None:
                cy += ROW_H + GAP
                continue

            row = pygame.Rect(self.role_list_rect.x + 4, cy,
                              self.role_list_rect.width - 12, ROW_H)
            sel = (rn == self.selected_role_name)
            hov = row.collidepoint(mouse)
            bg  = (70, 48, 108) if sel else ((50, 36, 80) if hov else (30, 22, 52))
            pygame.draw.rect(self.screen, bg, row, border_radius=12)
            pygame.draw.rect(self.screen, BTN_BORDER if sel else (46, 36, 72),
                             row, 1, border_radius=12)

            camp_col = ROLE_CAMP_COLOR.get(det["camp"], MIST_PURPLE)
            badge = pygame.Rect(row.x + 6, row.y + 7, 40, 28)
            pygame.draw.rect(self.screen, camp_col, badge, border_radius=10)
            draw_text(self.screen, det.get("ui_icon", rn[:2]), f["xs"], WHITE_SOFT,
                      center=badge.center)
            draw_text(self.screen, rn,         f["xs"], WHITE_SOFT,
                      topleft=(row.x + 52, row.y + 4))
            draw_text(self.screen, det["camp"], f["xs"], CYAN_COOL,
                      topleft=(row.x + 52, row.y + 22))

            # Compteur ± boutons (tout à droite)
            cnt_r = pygame.Rect(row.right - 128, row.y + 7, 38, 28)
            min_r = pygame.Rect(row.right - 84,  row.y + 7, 30, 28)
            pls_r = pygame.Rect(row.right - 46,  row.y + 7, 30, 28)
            en    = self.is_host()
            for r2, sym, col in [(min_r, "-", BTN_DANGER   if en else GREY_DARK),
                                  (pls_r, "+", BTN_SUCCESS  if en else GREY_DARK)]:
                pygame.draw.rect(self.screen, col, r2, border_radius=9)
                pygame.draw.rect(self.screen, BTN_BORDER, r2, 1, border_radius=9)
                draw_text(self.screen, sym, f["xs"], WHITE_SOFT if en else GREY_DIM,
                          center=r2.center)
            pygame.draw.rect(self.screen, (10, 8, 22), cnt_r, border_radius=9)
            pygame.draw.rect(self.screen, BTN_BORDER, cnt_r, 1, border_radius=9)
            draw_text(self.screen, str(self.role_config.get(rn, 0)), f["xs"], MOON_SILVER,
                      center=cnt_r.center)

            self.role_row_rects[rn]   = row
            self.role_minus_rects[rn] = min_r
            self.role_plus_rects[rn]  = pls_r
            cy += ROW_H + GAP

        self.screen.set_clip(old_clip)

        # Scrollbar
        if total_h > vis_h and max_scr > 0:
            bx  = self.role_list_rect.right - 7
            by2 = self.role_list_rect.y + 4
            bh  = self.role_list_rect.height - 8
            pygame.draw.rect(self.screen, (28, 22, 50), (bx, by2, 5, bh), border_radius=3)
            th  = max(22, int(bh * vis_h / total_h))
            ty  = by2 + int((bh - th) * (self.role_scroll / max_scr))
            pygame.draw.rect(self.screen, CYAN_COOL, (bx, ty, 5, th), border_radius=3)

    def draw_role_info_popup(self, f: dict):
        if not self.show_role_info or not self.selected_role_name:
            return
        det = ROLE_CATALOG.get(self.selected_role_name)
        if det is None:
            return
        ir = pygame.Rect(self.center_rect.x + 12,
                         self.center_rect.bottom - 200,
                         self.center_rect.width - 24, 144)
        pygame.draw.rect(self.screen, (36, 26, 64), ir, border_radius=14)
        pygame.draw.rect(self.screen, BTN_BORDER, ir, 1, border_radius=14)
        self.role_info_close_rect = pygame.Rect(ir.x + 8, ir.y + 8, 22, 22)
        pygame.draw.rect(self.screen, MIST_PURPLE, self.role_info_close_rect, border_radius=8)
        draw_text(self.screen, "x", f["xs"], WHITE_SOFT,
                  center=self.role_info_close_rect.center)
        draw_text(self.screen, self.selected_role_name, f["small"], CYAN_COOL,
                  topleft=(ir.x + 36, ir.y + 8))
        draw_text(self.screen, f"Camp : {det['camp']}  |  Aura : {det['aura']}",
                  f["xs"], GOLD_PALE, topleft=(ir.x + 10, ir.y + 32))
        lines = wrap_text(det.get("description", ""),
                          max(28, (ir.width - 20) // 8))
        yl = ir.y + 52
        for line in lines:
            if yl + 16 > ir.bottom - 4:
                break
            draw_text(self.screen, line, f["xs"], WHITE_SOFT, topleft=(ir.x + 10, yl))
            yl += 16

    def draw_lobby_panel(self):
        f = self.fonts()
        draw_glass_panel(self.screen, self.center_rect, radius=22)
        draw_text(self.screen, self.server_name, f["big"], MOON_SILVER,
                  topleft=(self.center_rect.x + 14, self.center_rect.y + 10), shadow=True)
        draw_text(self.screen, "Lobby - configuration de la partie",
                  f["small"], GOLD_PALE,
                  topleft=(self.center_rect.x + 14, self.center_rect.y + 54))

        draw_glass_panel(self.screen, self.player_count_rect, radius=16, alpha_fill=150)
        self.draw_player_count_selector(self.player_count_rect, f)

        draw_glass_panel(self.screen, self.balance_rect, radius=16, alpha_fill=150)
        self.draw_balance_bar(self.balance_rect, f)

        tx = self.center_rect.x + 14
        tw = self.center_rect.width - 28
        draw_text(self.screen, "Composition des roles", f["medium"], MOON_SILVER,
                  topleft=(tx, self.roles_title_y))
        pygame.draw.line(self.screen, (68, 52, 106),
                         (tx, self.roles_title_y + 28), (tx + tw, self.roles_title_y + 28))

        note = ("Tu peux modifier la composition." if self.is_host()
                else "Seul l'hote peut modifier les roles.")
        draw_text(self.screen, note, f["xs"],
                  GOLD_WARM if self.is_host() else GREY_DIM,
                  topleft=(tx, self.roles_notice_y))
        err = role_config_error(self.max_players, self.role_config)
        if err:
            draw_text(self.screen, err, f["xs"], WOLF_RED,
                      topleft=(tx, self.roles_notice_y + 20))

        pygame.draw.rect(self.screen, (16, 12, 32), self.role_list_rect, border_radius=14)
        pygame.draw.rect(self.screen, (52, 40, 84), self.role_list_rect, 1, border_radius=14)
        self.draw_role_rows(f)

        if self.show_role_info:
            self.draw_role_info_popup(f)

        # Footer bouton lancer
        footer = pygame.Rect(self.center_rect.x + 6, self.center_rect.bottom - 62,
                             self.center_rect.width - 12, 54)
        pygame.draw.rect(self.screen, (22, 16, 42), footer, border_radius=16)
        pygame.draw.rect(self.screen, (52, 40, 84), footer, 1, border_radius=16)
        can_start = (self.is_host()
                     and len(self.players) == self.max_players
                     and err is None)
        self.btn_start.draw(self.screen, f["small"], pygame.mouse.get_pos(),
                            enabled=can_start)
        if not can_start and self.is_host():
            needed = self.max_players - len(self.players)
            hint = (f"En attente de {needed} joueur(s)." if needed > 0
                    else "Corrige la configuration.")
            draw_text(self.screen, hint, f["xs"], GREY_DIM,
                      center=(footer.centerx, footer.y + 14))

    # ── Panneau jeu ──────────────────────────────────────────────────────────

    def draw_game_panel(self):
        f     = self.fonts()
        mouse = pygame.mouse.get_pos()
        is_day = (self.phase == "day")

        # Panneau teinté selon phase
        panel_s = pygame.Surface((self.center_rect.width, self.center_rect.height),
                                  pygame.SRCALPHA)
        col = (28, 48, 32, 205) if is_day else (22, 14, 38, 210)
        pygame.draw.rect(panel_s, col,
                         (0, 0, self.center_rect.width, self.center_rect.height),
                         border_radius=22)
        bord = (56, 96, 64, 160) if is_day else (88, 68, 128, 140)
        pygame.draw.rect(panel_s, bord,
                         (0, 0, self.center_rect.width, self.center_rect.height),
                         width=2, border_radius=22)
        self.screen.blit(panel_s, self.center_rect.topleft)

        # ----- Ecran de fin de partie
        if self.phase == "end" and self.winner:
            self._draw_end_screen(f, mouse)
            return

        phase_labels = {
            "night": (f"  Nuit {self.day_count}", MOON_SILVER),
            "day":   (f"  Jour {self.day_count}",  GOLD_WARM),
        }
        ph_txt, ph_col = phase_labels.get(self.phase, (self.phase.capitalize(), WHITE_SOFT))
        draw_text(self.screen, ph_txt, f["big"], ph_col,
                  topleft=(self.center_rect.x + 18, self.center_rect.y + 12), shadow=True)

        role = self.current_role() or "Non attribue"
        det  = ROLE_CATALOG.get(role, ROLE_CATALOG["Villageois"])
        camp_col = ROLE_CAMP_COLOR.get(det["camp"], MIST_PURPLE)
        rb = pygame.Rect(self.center_rect.x + 18, self.center_rect.y + 56, 140, 28)
        pygame.draw.rect(self.screen, camp_col, rb, border_radius=14)
        draw_text(self.screen, role, f["xs"], WHITE_SOFT, center=rb.center)

        # Badge cible selectionnee
        if self.selected_target is not None:
            tgt_name = next((p["name"] for p in self.players
                             if p["id"] == self.selected_target), "?")
            sr = pygame.Rect(rb.right + 10, rb.y, 160, 28)
            pygame.draw.rect(self.screen, (80, 48, 14), sr, border_radius=14)
            pygame.draw.rect(self.screen, GOLD_WARM, sr, 1, border_radius=14)
            draw_text(self.screen, f"Cible : {tgt_name}", f["xs"], GOLD_WARM, center=sr.center)

        # Indicateur d'ordre des tours (nuit uniquement)
        if self.phase == "night":
            self._draw_night_steps(f, sy=self.center_rect.y + 90)

        y = self.center_rect.y + (122 if self.phase == "night" else 100)

        def line(txt, col):
            nonlocal y
            if not txt:
                return
            for ln in wrap_text(txt, max(24, (self.center_rect.width - 40) // 9)):
                if y + 16 > self.center_rect.bottom - 76:
                    return
                draw_text(self.screen, ln, f["xs"], col,
                          topleft=(self.center_rect.x + 18, y))
                y += 18
            y += 4

        line(self.message, WHITE_SOFT)
        line(self.action_hint, GOLD_PALE)

        if self.phase == "day" and self.votes_needed > 0:
            line(f"Votes : {self.votes_cast}/{self.votes_needed}",
                 GOLD_WARM if self.has_voted else GREY_DIM)
            if self.has_voted:
                line("Vote enregistre - en attente des autres joueurs.", CYAN_COOL)
            else:
                line("Selectionnez un joueur puis cliquez VALIDER LE VOTE.", GOLD_PALE)

        if self.phase == "night":
            if self.night_target_name:
                line(f"Victime des loups : {self.night_target_name}", WOLF_RED)
            if self.seer_result:
                line(self.seer_result, CYAN_COOL)

        if self.last_deaths:
            line("Elimine(s) : " + ", ".join(self.last_deaths), BLOOD_RED)

        pygame.draw.line(self.screen, (58, 48, 88),
                         (self.center_rect.x + 18, y + 4),
                         (self.center_rect.right - 18, y + 4))
        y += 12
        line(f"Aura : {det['aura']}  |  Camp : {det['camp']}", CYAN_COOL)
        for ln in wrap_text(det["description"],
                            max(28, (self.center_rect.width - 36) // 9))[:3]:
            if y + 16 > self.center_rect.bottom - 76:
                break
            draw_text(self.screen, ln, f["xs"], GREY_DIM,
                      topleft=(self.center_rect.x + 18, y))
            y += 17

        # ---- Boutons d'action
        is_witch = role.startswith("Sorci") and self.phase == "night" and self.can_act
        if is_witch:
            self._draw_witch_buttons(f, mouse)
        elif self.phase in ("night", "day"):
            lbl = "VALIDER LE VOTE" if self.phase == "day" else "VALIDER L'ACTION"
            self.btn_vote.text = lbl
            vote_ok = (self.can_act and self.selected_target is not None
                       and not self.has_voted)
            self.btn_vote.draw(self.screen, f["small"], mouse, enabled=vote_ok)

    def _draw_night_steps(self, f: dict, sy: int):
        """Affiche la progression des tours de nuit : Loups → Voyante → Sorcière."""
        steps = [
            ("wolves", "LOUPS",    WOLF_RED),
            ("seer",   "VOYANTE",  CYAN_COOL),
            ("witch",  "SORCIÈRE", (160, 60, 180)),
        ]
        total_w = self.center_rect.width - 40
        pill_w  = total_w // 3 - 8
        pill_h  = 24
        sx      = self.center_rect.x + 20
        for i, (step, label, col) in enumerate(steps):
            px      = sx + i * (pill_w + 8)
            is_cur  = (step == self.night_step)
            pill    = pygame.Rect(px, sy, pill_w, pill_h)
            surf    = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
            bg_col  = (*col, 210) if is_cur else (40, 32, 60, 130)
            pygame.draw.rect(surf, bg_col, (0, 0, pill_w, pill_h), border_radius=11)
            if is_cur:
                pygame.draw.rect(surf, (*col, 255), (0, 0, pill_w, pill_h), 2, border_radius=11)
            self.screen.blit(surf, pill.topleft)
            txt_col = WHITE_SOFT if is_cur else GREY_DIM
            draw_text(self.screen, label, f["xs"], txt_col, center=pill.center)
            # Flèche entre les étapes
            if i < len(steps) - 1:
                ax = px + pill_w + 2
                ay = sy + pill_h // 2
                draw_text(self.screen, "›", f["xs"], GREY_DIM, center=(ax + 4, ay))

    def _draw_witch_buttons(self, f: dict, mouse):
        save_ok   = (self.witch_heal_available and self.night_target_name is not None)
        poison_ok = (self.witch_poison_available and self.selected_target is not None)
        lbl_save = ("SAUVER " + (self.night_target_name or "")[:10]).strip()
        self.btn_save.text   = lbl_save
        self.btn_poison.text = "EMPOISONNER"
        self.btn_skip.text   = "PASSER"
        self.btn_save.draw  (self.screen, f["xs"], mouse, enabled=save_ok)
        self.btn_poison.draw(self.screen, f["xs"], mouse, enabled=poison_ok)
        self.btn_skip.draw  (self.screen, f["xs"], mouse, enabled=True)
        iy = self.btn_save.rect.y - 18
        draw_text(self.screen,
                  "Potion soin" if self.witch_heal_available else "Soin epuise",
                  f["xs"], GOLD_WARM if self.witch_heal_available else GREY_DIM,
                  topleft=(self.btn_save.rect.x, iy))
        draw_text(self.screen,
                  "Potion mort" if self.witch_poison_available else "Mort epuisee",
                  f["xs"], (160, 60, 180) if self.witch_poison_available else GREY_DIM,
                  topleft=(self.btn_poison.rect.x, iy))

    def _draw_end_screen(self, f: dict, mouse):
        cr = self.center_rect
        is_village = (self.winner == "Village")
        bg = pygame.Surface((cr.width, cr.height), pygame.SRCALPHA)
        bg_col  = (20, 44, 28, 230) if is_village else (40, 10, 16, 230)
        brd_col = (56, 140, 70, 200) if is_village else (180, 30, 48, 200)
        pygame.draw.rect(bg, bg_col,  (0, 0, cr.width, cr.height), border_radius=22)
        pygame.draw.rect(bg, brd_col, (0, 0, cr.width, cr.height), width=3, border_radius=22)
        self.screen.blit(bg, cr.topleft)

        title = "VICTOIRE DU VILLAGE !" if is_village else "VICTOIRE DES LOUPS !"
        tcol  = (80, 220, 100) if is_village else WOLF_RED
        draw_text(self.screen, title, f["big"], tcol,
                  center=(cr.centerx, cr.y + 42), shadow=True)
        draw_text(self.screen, self.message, f["xs"], GOLD_PALE,
                  center=(cr.centerx, cr.y + 82))

        y = cr.y + 112
        col_w = cr.width - 28
        for p in self.players:
            if y + 28 > cr.bottom - 66:
                break
            role_str = p.get("revealed_role") or p.get("role") or "?"
            alive    = p["alive"]
            bg2 = (52, 14, 14) if is_wolf_role(role_str) else \
                  (24, 52, 28) if alive else (30, 26, 48)
            row = pygame.Rect(cr.x + 14, y, col_w, 26)
            pygame.draw.rect(self.screen, bg2, row, border_radius=8)
            name_col   = WHITE_SOFT if alive else GREY_DIM
            status     = "Survivant" if alive else "Elimine"
            status_col = GOLD_WARM  if alive else WOLF_RED
            draw_text(self.screen, p["name"],  f["xs"], name_col,   topleft=(row.x + 8,   row.y + 5))
            draw_text(self.screen, role_str,    f["xs"], CYAN_COOL,  topleft=(row.x + 130, row.y + 5))
            draw_text(self.screen, status,      f["xs"], status_col, topleft=(row.x + 260, row.y + 5))
            y += 30

        self.btn_end.draw(self.screen, f["small"], mouse, enabled=True)

    # ── Chat ─────────────────────────────────────────────────────────────────

    def draw_chat_panel(self):
        f = self.fonts()
        draw_glass_panel(self.screen, self.chat_rect, radius=22)
        draw_text(self.screen, "Chat", f["big"], MOON_SILVER,
                  topleft=(self.chat_rect.x + 12, self.chat_rect.y + 10), shadow=True)

        vis_top = self.chat_rect.y + 54
        vis_bot = self.chat_rect.bottom - 66
        line_h  = 40          # hauteur par entrée de chat (auteur + message)
        avail   = max(0, vis_bot - vis_top)
        max_vis = max(1, avail // line_h)

        total   = len(self.chat_history)
        max_scr = max(0, total - max_vis)
        self.chat_scroll = max(0, min(self.chat_scroll, max_scr))
        start   = max(0, total - max_vis - self.chat_scroll)
        visible = self.chat_history[start:start + max_vis]

        y = vis_top
        for entry in visible:
            if y + line_h > vis_bot:
                break
            system    = entry.get("system")
            wolf_only = entry.get("wolf_only", False)
            author = "[Systeme]" if system else entry.get("author", "?")
            acol   = WOLF_RED if system else (WOLF_RED if wolf_only else GOLD_WARM)
            draw_text(self.screen, author + ":", f["xs"], acol,
                      topleft=(self.chat_rect.x + 12, y))
            msg_txt = entry.get("message", "")
            max_c = max(10, (self.chat_rect.width - 24) // 8)
            if len(msg_txt) > max_c:
                msg_txt = msg_txt[:max_c - 2] + ".."
            msg_col = (200, 140, 140) if wolf_only else WHITE_SOFT
            draw_text(self.screen, msg_txt, f["xs"], msg_col,
                      topleft=(self.chat_rect.x + 18, y + 18))
            y += line_h

        # Scrollbar
        if total > max_vis and max_scr > 0:
            bx  = self.chat_rect.right - 10
            bh  = vis_bot - vis_top
            pygame.draw.rect(self.screen, (28, 22, 50), (bx, vis_top, 5, bh), border_radius=3)
            th  = max(24, int(bh * max_vis / total))
            ty2 = vis_top + int((bh - th) * (self.chat_scroll / max_scr))
            pygame.draw.rect(self.screen, CYAN_COOL, (bx, ty2, 5, th), border_radius=3)

        # Desactiver le chat si non autorise (nuit, non-loup)
        chat_allowed = self.can_chat
        if not chat_allowed:
            overlay = pygame.Surface((self.chat_rect.width - 4, 46), pygame.SRCALPHA)
            pygame.draw.rect(overlay, (10, 8, 22, 190), (0, 0, overlay.get_width(), 46), border_radius=12)
            self.screen.blit(overlay, (self.chat_rect.x + 2, self.chat_rect.bottom - 56))
            draw_text(self.screen, "Chat desactive la nuit (loups seulement)",
                      f["xs"], GREY_DIM,
                      center=(self.chat_rect.centerx, self.chat_rect.bottom - 34))
        else:
            self.chat_input.draw(self.screen, f["xs"])
            self.btn_send_chat.draw(self.screen, f["xs"], pygame.mouse.get_pos())

    # ── Draw principal ───────────────────────────────────────────────────────

    def draw(self):
        self._draw_bg()
        f = self.fonts()

        draw_glass_panel(self.screen, self.top_rect, radius=18)
        title = "LOUP-GAROU  -  " + self.server_name.upper()
        draw_text(self.screen, title, f["title"], MOON_SILVER,
                  center=(self.top_rect.centerx - 55, self.top_rect.centery), shadow=True)
        self.btn_sync.draw(self.screen, f["xs"], pygame.mouse.get_pos())

        if self.state == "connecting":
            draw_text(self.screen, "Connexion au serveur...", f["big"], MOON_SILVER,
                      center=self.screen.get_rect().center)
            return

        self.draw_player_list()
        if self.phase == "lobby":
            self.draw_lobby_panel()
        else:
            self.draw_game_panel()
        self.draw_chat_panel()

        draw_text(self.screen,
                  "Molette pour défiler  |  Clic sur un joueur pour cibler",
                  f["xs"], GREY_DIM,
                  center=self.bottom_rect.center)

    # ── Événements ───────────────────────────────────────────────────────────

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            pos = pygame.mouse.get_pos()
            if self.chat_rect.collidepoint(pos):
                # Molette haut (y>0) = messages plus anciens = scroll augmente
                self.chat_scroll = max(0, self.chat_scroll + event.y)
                return
            if self.phase == "lobby" and self.role_list_rect.collidepoint(pos):
                # Molette haut = remonter dans la liste = scroll diminue (offset depuis le haut)
                self.role_scroll = max(0, self.role_scroll - event.y * 24)
                self.show_role_info = False
                return

        if event.type == pygame.VIDEORESIZE:
            self.screen = pygame.display.set_mode(
                (max(MIN_W, event.w), max(MIN_H, event.h)), pygame.RESIZABLE)
            self.compute_layout()
            return

        if self.can_chat and self.chat_input.handle_event(event):
            self.send_chat()
            return

        if event.type != pygame.MOUSEBUTTONDOWN:
            return

        # Fermer popup rôle
        if self.show_role_info:
            if self.role_info_close_rect.collidepoint(event.pos):
                self.show_role_info = False
                return
            # Clic hors des lignes rôles => fermer
            on_row = any(r.collidepoint(event.pos) for r in self.role_row_rects.values())
            on_pm  = any(r.collidepoint(event.pos) for r in self.role_minus_rects.values())
            on_pp  = any(r.collidepoint(event.pos) for r in self.role_plus_rects.values())
            if not (on_row or on_pm or on_pp):
                self.show_role_info = False

        if self.btn_sync.is_clicked(event.pos):
            self.network.send({"type": "sync_request"})
            return
        if self.can_chat and self.btn_send_chat.is_clicked(event.pos):
            self.send_chat()
            return

        if self.phase == "lobby":
            if self.count_left_rect.collidepoint(event.pos):
                self._send_max_players_update(-1)
                return
            if self.count_right_rect.collidepoint(event.pos):
                self._send_max_players_update(+1)
                return
            for rn in list(self.role_row_rects.keys()):
                if self.role_minus_rects.get(rn, pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                    self.selected_role_name = rn
                    self.show_role_info = True
                    self._send_role_config_update(rn, -1)
                    return
                if self.role_plus_rects.get(rn, pygame.Rect(0,0,0,0)).collidepoint(event.pos):
                    self.selected_role_name = rn
                    self.show_role_info = True
                    self._send_role_config_update(rn, +1)
                    return
                if self.role_row_rects[rn].collidepoint(event.pos):
                    self.selected_role_name = rn
                    self.show_role_info = True
                    return
            if self.btn_start.is_clicked(event.pos):
                self.send_action()
            return

        # Bouton retour menu (ecran de fin)
        if self.phase == "end" and self.btn_end.is_clicked(event.pos):
            self.running = False
            return

        # Selection joueur en jeu
        for pid, rect in self.player_rects:
            if rect.collidepoint(event.pos):
                for p in self.players:
                    if p["id"] == pid and p["alive"] and pid != self.your_id:
                        self.selected_target = pid
                        return

        # Actions phase nuit/jour
        role = self.current_role() or ""
        is_witch = (role == "Sorcière") and self.phase == "night"

        if is_witch and self.can_act:
            if self.btn_save.is_clicked(event.pos):
                self.send_witch_save()
                return
            if self.btn_poison.is_clicked(event.pos):
                self.send_witch_poison()
                return
            if self.btn_skip.is_clicked(event.pos):
                self.send_witch_skip()
                return

        if self.phase in ("night", "day") and self.btn_vote.is_clicked(event.pos):
            self.send_action()

    # ── Boucle ───────────────────────────────────────────────────────────────

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS)
            self.t += dt * 0.001
            self.process_network()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                else:
                    self.handle_event(event)
            self.draw()
            pygame.display.flip()
        self.network.close()
        # NE PAS appeler pygame.quit() – géré par le Launcher
        pygame.display.quit()
