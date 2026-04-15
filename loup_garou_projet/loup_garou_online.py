import json
import socket
import threading
import pygame

from loup_shared import MIN_PLAYERS, ROLE_CATALOG, ROLES_ORDER, normalize_role_config, role_config_label

BASE_W, BASE_H = 1320, 860
MIN_W, MIN_H = 1020, 700
FPS = 60
BG_TOP = (18, 16, 36)
BG_BOTTOM = (56, 32, 70)
WHITE = (240, 240, 245)
GOLD = (220, 190, 80)
RED = (190, 80, 90)
GREEN = (90, 180, 120)
CYAN = (135, 205, 235)
PANEL_FILL = (12, 10, 26, 220)
PANEL_BORDER = (120, 110, 160, 110)
BUTTON_BORDER = (200, 190, 230)
PURPLE = (86, 66, 128)
PURPLE_2 = (64, 46, 96)


class NetworkClient:
    def __init__(self, host, player_name, port=5555):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(8)
        self.sock.connect((host, port))
        self.sock.settimeout(None)
        self.messages = []
        self.lock = threading.Lock()
        self.running = True
        threading.Thread(target=self.listen, daemon=True).start()
        self.send({"type": "join", "name": player_name})

    def listen(self):
        buffer = ""
        try:
            while self.running:
                data = self.sock.recv(4096)
                if not data:
                    break
                buffer += data.decode("utf-8")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        with self.lock:
                            self.messages.append(json.loads(line))
        except (OSError, json.JSONDecodeError):
            pass
        finally:
            self.running = False

    def send(self, payload):
        try:
            self.sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        except OSError:
            self.running = False

    def pop_messages(self):
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


class Button:
    def __init__(self, text, color, hover):
        self.text = text
        self.color = color
        self.hover = hover
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.enabled = True

    def set_rect(self, rect):
        self.rect = pygame.Rect(rect)

    def draw(self, surface, font, mouse_pos, enabled=True):
        self.enabled = enabled
        active_color = self.hover if enabled and self.rect.collidepoint(mouse_pos) else self.color
        pygame.draw.rect(surface, active_color, self.rect, border_radius=14)
        pygame.draw.rect(surface, BUTTON_BORDER, self.rect, 2, border_radius=14)
        text_color = WHITE if enabled else (150, 150, 160)
        img = font.render(self.text, True, text_color)
        surface.blit(img, img.get_rect(center=self.rect.center))

    def is_clicked(self, pos):
        return self.enabled and self.rect.collidepoint(pos)


class InputBox:
    def __init__(self, placeholder="Écris un message..."):
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.text = ""
        self.active = False
        self.placeholder = placeholder
        self.max_len = 220

    def set_rect(self, rect):
        self.rect = pygame.Rect(rect)

    def draw(self, surface, font):
        color = (40, 30, 62) if self.active else (26, 20, 46)
        pygame.draw.rect(surface, color, self.rect, border_radius=14)
        pygame.draw.rect(surface, CYAN if self.active else BUTTON_BORDER, self.rect, 2, border_radius=14)
        display = self.text or self.placeholder
        img = font.render(display, True, WHITE if self.text else (170, 180, 205))
        clipped = img
        if img.get_width() > self.rect.width - 20:
            display = display[-max(1, len(display) // 2):]
            clipped = font.render(display, True, WHITE if self.text else (170, 180, 205))
        surface.blit(clipped, (self.rect.x + 10, self.rect.centery - clipped.get_height() // 2))

    def handle_event(self, event):
        submit = False
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_RETURN:
                submit = True
            elif len(self.text) < self.max_len and event.unicode.isprintable():
                self.text += event.unicode
        return submit

    def consume(self):
        text = self.text.strip()
        self.text = ""
        return text


def draw_vertical_gradient(surface, top_color, bottom_color):
    width, height = surface.get_size()
    for y in range(height):
        ratio = y / max(1, height)
        color = tuple(int(top_color[i] * (1 - ratio) + bottom_color[i] * ratio) for i in range(3))
        pygame.draw.line(surface, color, (0, y), (width, y))


def draw_glass_panel(surface, rect, radius=20):
    panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(panel, PANEL_FILL, (0, 0, rect.width, rect.height), border_radius=radius)
    pygame.draw.rect(panel, PANEL_BORDER, (0, 0, rect.width, rect.height), width=1, border_radius=radius)
    surface.blit(panel, rect.topleft)


def draw_text(surface, text, font, color, center=None, topleft=None):
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center is not None:
        rect.center = center
    if topleft is not None:
        rect.topleft = topleft
    surface.blit(img, rect)
    return rect


class WerewolfOnlineGame:
    def __init__(self, host, player_name):
        pygame.init()
        self.screen = pygame.display.set_mode((BASE_W, BASE_H), pygame.RESIZABLE)
        pygame.display.set_caption("Loup-Garou Online")
        self.clock = pygame.time.Clock()
        self.network = NetworkClient(host, player_name)
        self.running = True
        self.state = "connecting"
        self.server_name = "Salon"
        self.message = "Connexion au serveur..."
        self.action_hint = ""
        self.players = []
        self.your_id = None
        self.host_id = None
        self.phase = "lobby"
        self.day_count = 0
        self.winner = None
        self.selected_target = None
        self.last_deaths = []
        self.night_target_name = None
        self.seer_result = None
        self.can_act = False
        self.max_players = 12
        self.role_config = normalize_role_config({})
        self.chat_history = []
        self.chat_scroll = 0
        self.role_scroll = 0
        self.selected_role_name = "Loup-garou"
        self.start_btn = Button("LANCER LA PARTIE", (90, 120, 80), (110, 145, 95))
        self.vote_btn = Button("VALIDER L'ACTION", (55, 85, 125), (75, 105, 155))
        self.sync_btn = Button("SYNCHRONISER", (70, 70, 110), (90, 90, 140))
        self.skip_btn = Button("PASSER", (120, 85, 60), (150, 105, 75))
        self.chat_send_btn = Button("ENVOYER", (55, 85, 125), (75, 105, 155))
        self.chat_input = InputBox()
        self.player_rects = []
        self.role_row_rects = []
        self.role_minus_rects = {}
        self.role_plus_rects = {}
        self.compute_layout()

    def fonts(self):
        w, h = self.screen.get_size()
        scale = min(w / BASE_W, h / BASE_H)
        return {
            "small": pygame.font.SysFont("arial", max(16, int(19 * scale))),
            "medium": pygame.font.SysFont("arial", max(22, int(26 * scale))),
            "big": pygame.font.SysFont("arial", max(30, int(38 * scale))),
            "title": pygame.font.SysFont("arial", max(40, int(52 * scale)), bold=True),
        }

    def compute_layout(self):
        w, h = self.screen.get_size()
        self.top_rect = pygame.Rect(20, 20, w - 40, 90)
        self.left_rect = pygame.Rect(20, 130, int(w * 0.30), h - 200)
        self.center_rect = pygame.Rect(self.left_rect.right + 20, 130, int(w * 0.35), h - 200)
        self.chat_rect = pygame.Rect(self.center_rect.right + 20, 130, w - self.left_rect.width - self.center_rect.width - 80, h - 200)
        self.bottom_rect = pygame.Rect(20, h - 60, w - 40, 40)
        btn_w = min(260, self.center_rect.width - 40)
        self.start_btn.set_rect((self.center_rect.x + 20, self.center_rect.bottom - 60, self.center_rect.width - 40, 44))
        self.vote_btn.set_rect((self.center_rect.x + 20, self.center_rect.bottom - 60, btn_w, 44))
        self.skip_btn.set_rect((self.center_rect.x + 20 + btn_w + 14, self.center_rect.bottom - 60, max(140, self.center_rect.width - btn_w - 54), 44))
        self.sync_btn.set_rect((self.top_rect.right - 220, self.top_rect.y + 22, 200, 42))
        self.chat_input.set_rect((self.chat_rect.x + 18, self.chat_rect.bottom - 58, self.chat_rect.width - 136, 42))
        self.chat_send_btn.set_rect((self.chat_rect.right - 104, self.chat_rect.bottom - 58, 86, 42))
        self.role_list_rect = pygame.Rect(self.center_rect.x + 14, self.center_rect.y + 112, self.center_rect.width - 28, self.center_rect.height - 290)
        self.role_desc_rect = pygame.Rect(self.center_rect.x + 14, self.center_rect.bottom - 170, self.center_rect.width - 28, 94)

    def current_role(self):
        if self.your_id is None:
            return None
        for p in self.players:
            if p["id"] == self.your_id:
                return p.get("role")
        return None

    def is_host(self):
        return self.your_id == self.host_id

    def selected_role_details(self):
        return ROLE_CATALOG.get(self.selected_role_name, ROLE_CATALOG["Villageois"])

    def process_network(self):
        for msg in self.network.pop_messages():
            msg_type = msg.get("type")
            if msg_type == "state_sync":
                self.state = "game"
                self.server_name = msg.get("server_name", self.server_name)
                self.phase = msg.get("phase", "lobby")
                self.day_count = msg.get("day_count", 0)
                self.players = msg.get("players", [])
                self.your_id = msg.get("your_id", self.your_id)
                self.host_id = msg.get("host_id", self.host_id)
                self.message = msg.get("message", self.message)
                self.last_deaths = msg.get("last_deaths", [])
                self.night_target_name = msg.get("night_target_name")
                self.winner = msg.get("winner")
                self.can_act = msg.get("can_act", False)
                self.action_hint = msg.get("action_hint", "")
                self.seer_result = msg.get("seer_result")
                self.max_players = msg.get("max_players", self.max_players)
                self.role_config = normalize_role_config(msg.get("role_config", self.role_config))
                if self.selected_role_name not in self.role_config:
                    self.selected_role_name = next(iter(self.role_config))
                old_len = len(self.chat_history)
                self.chat_history = msg.get("chat_history", self.chat_history)
                if len(self.chat_history) > old_len:
                    self.chat_scroll = 0
                if self.selected_target is not None and all(p["id"] != self.selected_target or not p["alive"] for p in self.players):
                    self.selected_target = None
            elif msg_type == "error":
                self.message = "Erreur : " + msg.get("message", "")
            elif msg_type == "info":
                self.message = msg.get("message", self.message)

    def send_role_config_update(self, role_name, delta):
        if not self.is_host() or self.phase != "lobby":
            return
        new_config = dict(self.role_config)
        current = new_config.get(role_name, 0)
        max_count = ROLE_CATALOG[role_name]["max"]
        if role_name == "Loup-garou":
            new_config[role_name] = max(1, min(max_count, current + delta))
        else:
            new_config[role_name] = max(0, min(max_count, current + delta))
        if new_config != self.role_config:
            self.network.send({"type": "update_role_config", "role_config": new_config})

    def send_action(self):
        role = self.current_role()
        if self.phase == "lobby":
            self.network.send({"type": "start_game"})
            return
        if self.phase == "day" and self.selected_target is not None:
            self.network.send({"type": "vote_action", "target": self.selected_target})
            return
        if self.phase == "night" and self.selected_target is not None:
            if role in ("Loup-garou", "Infect Père des Loups"):
                self.network.send({"type": "night_action", "action": "wolf_kill", "target": self.selected_target})
            elif role == "Voyante":
                self.network.send({"type": "night_action", "action": "seer_peek", "target": self.selected_target})
            elif role == "Sorcière":
                self.network.send({"type": "night_action", "action": "witch_poison", "target": self.selected_target})

    def send_skip(self):
        if self.phase == "night" and self.current_role() == "Sorcière":
            self.network.send({"type": "night_action", "action": "witch_skip"})

    def send_save(self):
        if self.phase == "night" and self.current_role() == "Sorcière":
            self.network.send({"type": "night_action", "action": "witch_save"})

    def send_chat(self):
        text = self.chat_input.consume()
        if text:
            self.network.send({"type": "chat_message", "message": text})

    def draw_player_list(self):
        f = self.fonts()
        draw_glass_panel(self.screen, self.left_rect, radius=22)
        draw_text(self.screen, "Joueurs", f["big"], WHITE, topleft=(self.left_rect.x + 18, self.left_rect.y + 14))
        self.player_rects = []
        y = self.left_rect.y + 72
        for p in self.players:
            rect = pygame.Rect(self.left_rect.x + 16, y, self.left_rect.width - 32, 48)
            selected = p["id"] == self.selected_target
            base = (42, 30, 60) if not selected else (80, 52, 100)
            pygame.draw.rect(self.screen, base, rect, border_radius=12)
            pygame.draw.rect(self.screen, BUTTON_BORDER, rect, 1, border_radius=12)
            status = "vivant" if p["alive"] else "mort"
            role = p.get("revealed_role") or p.get("role", "?") if (not p["alive"] or p["id"] == self.your_id or p.get("role") in ("Loup-garou", "Infect Père des Loups")) else "?"
            draw_text(self.screen, p["name"], f["medium"], WHITE, topleft=(rect.x + 14, rect.y + 8))
            draw_text(self.screen, f"{status} - {role}", f["small"], CYAN if p["alive"] else RED, topleft=(rect.x + 14, rect.y + 25))
            self.player_rects.append((p["id"], rect))
            y += 56

    def draw_role_lobby_panel(self):
        f = self.fonts()
        draw_glass_panel(self.screen, self.center_rect, radius=22)
        draw_text(self.screen, self.server_name, f["big"], WHITE, topleft=(self.center_rect.x + 18, self.center_rect.y + 14))
        draw_text(self.screen, "Lobby", f["medium"], GOLD, topleft=(self.center_rect.x + 20, self.center_rect.y + 68))
        role = self.current_role() or "Non attribué"
        draw_text(self.screen, f"Ton rôle : {role}", f["medium"], CYAN, topleft=(self.center_rect.x + 20, self.center_rect.y + 104))
        draw_text(self.screen, f"Joueurs : {len(self.players)}/{self.max_players}", f["small"], WHITE, topleft=(self.center_rect.x + 20, self.center_rect.y + 138))
        draw_text(self.screen, f"Configuration : {role_config_label(self.role_config)}", f["small"], WHITE, topleft=(self.center_rect.x + 20, self.center_rect.y + 162))
        notice = "Seul l'hôte peut modifier la composition." if not self.is_host() else "Tu es l'hôte : ajuste les rôles puis lance la partie."
        draw_text(self.screen, notice, f["small"], GOLD if self.is_host() else WHITE, topleft=(self.center_rect.x + 20, self.center_rect.y + 186))

        pygame.draw.rect(self.screen, PURPLE_2, self.role_list_rect, border_radius=16)
        pygame.draw.rect(self.screen, PANEL_BORDER, self.role_list_rect, 1, border_radius=16)

        row_h = 66
        visible_count = max(1, self.role_list_rect.height // row_h)
        role_names = [role for role in ROLES_ORDER if role != "Villageois"]
        max_scroll = max(0, len(role_names) - visible_count)
        self.role_scroll = max(0, min(self.role_scroll, max_scroll))
        visible_roles = role_names[self.role_scroll:self.role_scroll + visible_count]

        self.role_row_rects = []
        self.role_minus_rects = {}
        self.role_plus_rects = {}
        y = self.role_list_rect.y + 8
        mouse = pygame.mouse.get_pos()
        for role_name in visible_roles:
            row = pygame.Rect(self.role_list_rect.x + 8, y, self.role_list_rect.width - 24, 56)
            selected = role_name == self.selected_role_name
            bg = (100, 76, 138) if selected else (58, 42, 88)
            pygame.draw.rect(self.screen, bg, row, border_radius=12)
            pygame.draw.rect(self.screen, BUTTON_BORDER, row, 1, border_radius=12)
            draw_text(self.screen, role_name, f["medium"], WHITE, topleft=(row.x + 14, row.y + 6))
            draw_text(self.screen, ROLE_CATALOG[role_name]["camp"], f["small"], GOLD if ROLE_CATALOG[role_name]["camp"] == "Loups" else CYAN, topleft=(row.x + 14, row.y + 30))
            val_rect = pygame.Rect(row.right - 148, row.y + 8, 42, 40)
            minus_rect = pygame.Rect(row.right - 98, row.y + 8, 40, 40)
            plus_rect = pygame.Rect(row.right - 48, row.y + 8, 40, 40)
            pygame.draw.rect(self.screen, (24, 18, 42), val_rect, border_radius=10)
            pygame.draw.rect(self.screen, BUTTON_BORDER, val_rect, 2, border_radius=10)
            pygame.draw.rect(self.screen, (120, 70, 82) if self.is_host() else (88, 70, 82), minus_rect, border_radius=12)
            pygame.draw.rect(self.screen, (86, 126, 92) if self.is_host() else (72, 92, 72), plus_rect, border_radius=12)
            pygame.draw.rect(self.screen, BUTTON_BORDER, minus_rect, 2, border_radius=12)
            pygame.draw.rect(self.screen, BUTTON_BORDER, plus_rect, 2, border_radius=12)
            draw_text(self.screen, str(self.role_config.get(role_name, 0)), f["medium"], WHITE, center=val_rect.center)
            draw_text(self.screen, "-", f["medium"], WHITE if self.is_host() else (160, 160, 160), center=minus_rect.center)
            draw_text(self.screen, "+", f["medium"], WHITE if self.is_host() else (160, 160, 160), center=plus_rect.center)
            self.role_row_rects.append((role_name, row))
            self.role_minus_rects[role_name] = minus_rect
            self.role_plus_rects[role_name] = plus_rect
            y += row_h

        if len(role_names) > visible_count:
            bar_x = self.role_list_rect.right - 10
            bar_y = self.role_list_rect.y + 8
            bar_h = self.role_list_rect.height - 16
            pygame.draw.rect(self.screen, (40, 40, 70), (bar_x, bar_y, 6, bar_h), border_radius=3)
            thumb_h = max(28, int(bar_h * (visible_count / len(role_names))))
            scroll_ratio = 0 if max_scroll == 0 else self.role_scroll / max_scroll
            thumb_y = bar_y + int((bar_h - thumb_h) * scroll_ratio)
            pygame.draw.rect(self.screen, CYAN, (bar_x, thumb_y, 6, thumb_h), border_radius=3)

        pygame.draw.rect(self.screen, PURPLE, self.role_desc_rect, border_radius=16)
        pygame.draw.rect(self.screen, BUTTON_BORDER, self.role_desc_rect, 1, border_radius=16)
        details = self.selected_role_details()
        draw_text(self.screen, self.selected_role_name, f["medium"], WHITE, topleft=(self.role_desc_rect.x + 12, self.role_desc_rect.y + 10))
        draw_text(self.screen, f"Camp : {details['camp']}  |  Aura : {details['aura']}", f["small"], CYAN, topleft=(self.role_desc_rect.x + 12, self.role_desc_rect.y + 36))
        desc = details["description"]
        max_chars = max(40, (self.role_desc_rect.width - 24) // 9)
        lines = []
        current = ""
        for word in desc.split():
            test = word if not current else current + " " + word
            if len(test) <= max_chars:
                current = test
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        for i, line in enumerate(lines[:2]):
            draw_text(self.screen, line, f["small"], WHITE, topleft=(self.role_desc_rect.x + 12, self.role_desc_rect.y + 58 + i * 20))

        can_start = self.is_host() and len(self.players) >= MIN_PLAYERS
        self.start_btn.draw(self.screen, f["small"], mouse, enabled=can_start)

    def draw_info_panel(self):
        f = self.fonts()
        draw_glass_panel(self.screen, self.center_rect, radius=22)
        draw_text(self.screen, self.server_name, f["big"], WHITE, topleft=(self.center_rect.x + 18, self.center_rect.y + 14))
        phase_label = {
            "lobby": "Lobby",
            "night": f"Nuit {self.day_count}",
            "day": f"Jour {self.day_count}",
            "end": "Fin de partie",
        }.get(self.phase, self.phase)
        draw_text(self.screen, phase_label, f["medium"], GOLD, topleft=(self.center_rect.x + 20, self.center_rect.y + 68))
        role = self.current_role() or "Non attribué"
        draw_text(self.screen, f"Ton rôle : {role}", f["medium"], CYAN, topleft=(self.center_rect.x + 20, self.center_rect.y + 104))
        draw_text(self.screen, f"Places : {len(self.players)}/{self.max_players}", f["small"], WHITE, topleft=(self.center_rect.x + 20, self.center_rect.y + 138))
        draw_text(self.screen, f"Config : {role_config_label(self.role_config)}", f["small"], WHITE, topleft=(self.center_rect.x + 20, self.center_rect.y + 164))
        draw_text(self.screen, self.message, f["small"], WHITE, topleft=(self.center_rect.x + 20, self.center_rect.y + 198))
        if self.action_hint:
            draw_text(self.screen, self.action_hint, f["small"], GOLD, topleft=(self.center_rect.x + 20, self.center_rect.y + 228))
        if self.night_target_name:
            draw_text(self.screen, f"Victime visée : {self.night_target_name}", f["small"], RED, topleft=(self.center_rect.x + 20, self.center_rect.y + 258))
        if self.seer_result:
            draw_text(self.screen, self.seer_result, f["small"], GREEN, topleft=(self.center_rect.x + 20, self.center_rect.y + 288))
        if self.last_deaths:
            draw_text(self.screen, "Derniers éliminés : " + ", ".join(self.last_deaths), f["small"], RED, topleft=(self.center_rect.x + 20, self.center_rect.y + 318))
        details = ROLE_CATALOG.get(role, ROLE_CATALOG["Villageois"])
        draw_text(self.screen, f"Aura : {details['aura']}  |  Camp : {details['camp']}", f["small"], CYAN, topleft=(self.center_rect.x + 20, self.center_rect.y + 350))
        desc = details["description"]
        max_chars = max(40, (self.center_rect.width - 40) // 9)
        lines = []
        current = ""
        for word in desc.split():
            test = word if not current else current + " " + word
            if len(test) <= max_chars:
                current = test
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        y = self.center_rect.y + 382
        for line in lines[:4]:
            draw_text(self.screen, line, self.fonts()["small"], WHITE, topleft=(self.center_rect.x + 20, y))
            y += 24

        mouse = pygame.mouse.get_pos()
        if self.phase in ("night", "day"):
            self.vote_btn.text = "VALIDER LE VOTE" if self.phase == "day" else "VALIDER L'ACTION"
            self.vote_btn.draw(self.screen, f["small"], mouse, enabled=self.can_act and self.selected_target is not None)
            if self.phase == "night" and role == "Sorcière":
                self.skip_btn.text = "PASSER" if not self.night_target_name else "SAUVER"
                self.skip_btn.draw(self.screen, f["small"], mouse, enabled=self.can_act)

    def draw_chat_panel(self):
        f = self.fonts()
        draw_glass_panel(self.screen, self.chat_rect, radius=22)
        draw_text(self.screen, "Chat", f["big"], WHITE, topleft=(self.chat_rect.x + 18, self.chat_rect.y + 14))

        visible_top = self.chat_rect.y + 62
        visible_bottom = self.chat_rect.bottom - 70
        line_height = 48
        max_visible = max(1, (visible_bottom - visible_top) // line_height)

        total_messages = len(self.chat_history)
        max_scroll = max(0, total_messages - max_visible)
        self.chat_scroll = max(0, min(self.chat_scroll, max_scroll))

        start_index = max(0, total_messages - max_visible - self.chat_scroll)
        end_index = start_index + max_visible
        visible = self.chat_history[start_index:end_index]

        y = visible_top
        for entry in visible:
            color = GOLD if entry.get("system") else CYAN
            prefix = "[Système]" if entry.get("system") else entry.get("author", "?")
            draw_text(self.screen, f"{prefix} :", f["small"], color, topleft=(self.chat_rect.x + 18, y))
            y += 20
            draw_text(self.screen, entry.get("message", ""), f["small"], WHITE, topleft=(self.chat_rect.x + 26, y))
            y += 28

        if total_messages > max_visible:
            bar_x = self.chat_rect.right - 12
            bar_y = visible_top
            bar_h = visible_bottom - visible_top
            pygame.draw.rect(self.screen, (40, 40, 70), (bar_x, bar_y, 6, bar_h), border_radius=3)

            thumb_h = max(30, int(bar_h * (max_visible / total_messages)))
            scroll_ratio = 0 if max_scroll == 0 else self.chat_scroll / max_scroll
            thumb_y = bar_y + int((bar_h - thumb_h) * scroll_ratio)
            pygame.draw.rect(self.screen, CYAN, (bar_x, thumb_y, 6, thumb_h), border_radius=3)

        self.chat_input.draw(self.screen, f["small"])
        self.chat_send_btn.draw(self.screen, f["small"], pygame.mouse.get_pos(), enabled=True)

    def draw(self):
        draw_vertical_gradient(self.screen, BG_TOP, BG_BOTTOM)
        f = self.fonts()
        draw_glass_panel(self.screen, self.top_rect, radius=22)
        draw_text(self.screen, "LOUP-GAROU ONLINE", f["title"], WHITE, center=(self.top_rect.centerx, self.top_rect.y + 32))
        draw_text(self.screen, "Le lobby affiche la composition de la partie pour tout le monde.", f["small"], CYAN, center=(self.top_rect.centerx, self.top_rect.y + 68))
        self.sync_btn.draw(self.screen, f["small"], pygame.mouse.get_pos(), enabled=True)
        if self.state == "connecting":
            draw_text(self.screen, "Connexion au serveur...", f["big"], WHITE, center=self.screen.get_rect().center)
            return
        self.draw_player_list()
        if self.phase == "lobby":
            self.draw_role_lobby_panel()
        else:
            self.draw_info_panel()
        self.draw_chat_panel()
        draw_text(self.screen, "Clique sur des joueurs vivants pour les sélectionner. Molette sur chat ou rôles.", f["small"], WHITE, center=self.bottom_rect.center)

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            if self.chat_rect.collidepoint((mouse_x, mouse_y)):
                if event.y > 0:
                    self.chat_scroll = min(self.chat_scroll + 1, max(0, len(self.chat_history) - 1))
                elif event.y < 0:
                    self.chat_scroll = max(self.chat_scroll - 1, 0)
                return
            if self.phase == "lobby" and self.role_list_rect.collidepoint((mouse_x, mouse_y)):
                role_count = len([r for r in ROLES_ORDER if r != "Villageois"])
                visible_count = max(1, self.role_list_rect.height // 66)
                max_scroll = max(0, role_count - visible_count)
                if event.y > 0:
                    self.role_scroll = max(self.role_scroll - 1, 0)
                elif event.y < 0:
                    self.role_scroll = min(self.role_scroll + 1, max_scroll)
                return
        if event.type == pygame.VIDEORESIZE:
            self.screen = pygame.display.set_mode((max(MIN_W, event.w), max(MIN_H, event.h)), pygame.RESIZABLE)
            self.compute_layout()
            return
        if self.chat_input.handle_event(event):
            self.send_chat()
            return
        if event.type != pygame.MOUSEBUTTONDOWN:
            return
        if self.sync_btn.is_clicked(event.pos):
            self.network.send({"type": "sync_request"})
            return
        if self.chat_send_btn.is_clicked(event.pos):
            self.send_chat()
            return
        if self.phase == "lobby":
            for role_name, row in self.role_row_rects:
                if row.collidepoint(event.pos):
                    self.selected_role_name = role_name
                if self.role_minus_rects.get(role_name) and self.role_minus_rects[role_name].collidepoint(event.pos):
                    self.selected_role_name = role_name
                    self.send_role_config_update(role_name, -1)
                    return
                if self.role_plus_rects.get(role_name) and self.role_plus_rects[role_name].collidepoint(event.pos):
                    self.selected_role_name = role_name
                    self.send_role_config_update(role_name, +1)
                    return
            if self.start_btn.is_clicked(event.pos):
                self.send_action()
            return
        for pid, rect in self.player_rects:
            if rect.collidepoint(event.pos):
                for p in self.players:
                    if p["id"] == pid and p["alive"] and pid != self.your_id:
                        self.selected_target = pid
                        return
        if self.phase in ("night", "day") and self.vote_btn.is_clicked(event.pos):
            self.send_action()
        elif self.phase == "night" and self.current_role() == "Sorcière" and self.skip_btn.is_clicked(event.pos):
            if self.night_target_name:
                self.send_save()
            else:
                self.send_skip()

    def run(self):
        while self.running:
            self.clock.tick(FPS)
            self.process_network()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                else:
                    self.handle_event(event)
            self.draw()
            pygame.display.flip()
        self.network.close()
        pygame.quit()
