import json
import socket
import threading
import pygame

BASE_W, BASE_H = 1220, 820
MIN_W, MIN_H = 960, 680
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
        self.start_btn = Button("LANCER LA PARTIE", (90, 120, 80), (110, 145, 95))
        self.vote_btn = Button("VALIDER L'ACTION", (55, 85, 125), (75, 105, 155))
        self.sync_btn = Button("SYNCHRONISER", (70, 70, 110), (90, 90, 140))
        self.skip_btn = Button("PASSER", (120, 85, 60), (150, 105, 75))
        self.player_rects = []
        self.compute_layout()

    def fonts(self):
        w, h = self.screen.get_size()
        scale = min(w / BASE_W, h / BASE_H)
        return {
            "small": pygame.font.SysFont("arial", max(18, int(21 * scale))),
            "medium": pygame.font.SysFont("arial", max(24, int(28 * scale))),
            "big": pygame.font.SysFont("arial", max(34, int(42 * scale))),
            "title": pygame.font.SysFont("arial", max(42, int(54 * scale)), bold=True),
        }

    def compute_layout(self):
        w, h = self.screen.get_size()
        self.top_rect = pygame.Rect(20, 20, w - 40, 90)
        self.left_rect = pygame.Rect(20, 130, int(w * 0.42), h - 200)
        self.right_rect = pygame.Rect(self.left_rect.right + 20, 130, w - self.left_rect.width - 60, h - 200)
        self.bottom_rect = pygame.Rect(20, h - 60, w - 40, 40)
        btn_w = min(260, self.right_rect.width - 40)
        self.start_btn.set_rect((self.right_rect.x + 20, self.right_rect.bottom - 60, btn_w, 44))
        self.vote_btn.set_rect((self.right_rect.x + 20, self.right_rect.bottom - 60, btn_w, 44))
        self.skip_btn.set_rect((self.right_rect.x + 20 + btn_w + 14, self.right_rect.bottom - 60, max(150, self.right_rect.width - btn_w - 54), 44))
        self.sync_btn.set_rect((self.top_rect.right - 220, self.top_rect.y + 22, 200, 42))

    def living_targets(self):
        return [p for p in self.players if p["alive"] and p["id"] != self.your_id]

    def current_role(self):
        if self.your_id is None:
            return None
        for p in self.players:
            if p["id"] == self.your_id:
                return p.get("role")
        return None

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
                if self.selected_target is not None and all(p["id"] != self.selected_target or not p["alive"] for p in self.players):
                    self.selected_target = None
            elif msg_type == "error":
                self.message = "Erreur : " + msg.get("message", "")
            elif msg_type == "info":
                self.message = msg.get("message", self.message)

    def send_action(self):
        role = self.current_role()
        if self.phase == "lobby":
            self.network.send({"type": "start_game"})
            return
        if self.phase == "day" and self.selected_target is not None:
            self.network.send({"type": "vote_action", "target": self.selected_target})
            return
        if self.phase == "night" and self.selected_target is not None:
            if role == "Loup-garou":
                self.network.send({"type": "night_action", "action": "wolf_kill", "target": self.selected_target})
            elif role == "Voyante":
                self.network.send({"type": "night_action", "action": "seer_peek", "target": self.selected_target})
            elif role == "Sorciere":
                self.network.send({"type": "night_action", "action": "witch_poison", "target": self.selected_target})

    def send_skip(self):
        if self.phase == "night" and self.current_role() == "Sorciere":
            self.network.send({"type": "night_action", "action": "witch_skip"})

    def send_save(self):
        if self.phase == "night" and self.current_role() == "Sorciere":
            self.network.send({"type": "night_action", "action": "witch_save"})

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
            role = p.get("revealed_role") or p.get("role", "?") if (not p["alive"] or p["id"] == self.your_id or p.get("role") == "Loup-garou") else "?"
            draw_text(self.screen, p["name"], f["medium"], WHITE, topleft=(rect.x + 14, rect.y + 8))
            draw_text(self.screen, f"{status} - {role}", f["small"], CYAN if p["alive"] else RED, topleft=(rect.x + 14, rect.y + 25))
            self.player_rects.append((p["id"], rect))
            y += 56

    def draw_info_panel(self):
        f = self.fonts()
        draw_glass_panel(self.screen, self.right_rect, radius=22)
        title = f"{self.server_name}"
        draw_text(self.screen, title, f["big"], WHITE, topleft=(self.right_rect.x + 18, self.right_rect.y + 14))
        phase_label = {
            "lobby": "Lobby",
            "night": f"Nuit {self.day_count}",
            "day": f"Jour {self.day_count}",
            "end": "Fin de partie",
        }.get(self.phase, self.phase)
        draw_text(self.screen, phase_label, f["medium"], GOLD, topleft=(self.right_rect.x + 20, self.right_rect.y + 68))
        role = self.current_role() or "Non attribué"
        draw_text(self.screen, f"Ton rôle : {role}", f["medium"], CYAN, topleft=(self.right_rect.x + 20, self.right_rect.y + 104))
        draw_text(self.screen, self.message, f["small"], WHITE, topleft=(self.right_rect.x + 20, self.right_rect.y + 148))
        if self.action_hint:
            draw_text(self.screen, self.action_hint, f["small"], GOLD, topleft=(self.right_rect.x + 20, self.right_rect.y + 180))
        if self.night_target_name:
            draw_text(self.screen, f"Victime visée : {self.night_target_name}", f["small"], RED, topleft=(self.right_rect.x + 20, self.right_rect.y + 214))
        if self.seer_result:
            draw_text(self.screen, self.seer_result, f["small"], GREEN, topleft=(self.right_rect.x + 20, self.right_rect.y + 248))
        if self.last_deaths:
            draw_text(self.screen, "Derniers éliminés : " + ", ".join(self.last_deaths), f["small"], RED, topleft=(self.right_rect.x + 20, self.right_rect.y + 282))
        y = self.right_rect.y + 330
        for line in [
            "Règles de cette version :",
            "- minimum 4 joueurs",
            "- rôles : loup, voyante, sorcière, villageois",
            "- pas de chat intégré pour l'instant",
            "- la sorcière a une potion de soin et une de mort",
        ]:
            draw_text(self.screen, line, f["small"], WHITE, topleft=(self.right_rect.x + 20, y))
            y += 30

        mouse = pygame.mouse.get_pos()
        is_host = self.your_id == self.host_id
        if self.phase == "lobby":
            self.start_btn.draw(self.screen, f["small"], mouse, enabled=is_host and len(self.players) >= 4)
        elif self.phase in ("night", "day"):
            self.vote_btn.text = "VALIDER LE VOTE" if self.phase == "day" else "VALIDER L'ACTION"
            self.vote_btn.draw(self.screen, f["small"], mouse, enabled=self.can_act and self.selected_target is not None)
            if self.phase == "night" and role == "Sorciere":
                skip_text = "PASSER" if not self.night_target_name else "SAUVER"
                self.skip_btn.text = skip_text
                self.skip_btn.draw(self.screen, f["small"], mouse, enabled=self.can_act)

    def draw(self):
        draw_vertical_gradient(self.screen, BG_TOP, BG_BOTTOM)
        f = self.fonts()
        draw_glass_panel(self.screen, self.top_rect, radius=22)
        draw_text(self.screen, "LOUP-GAROU ONLINE", f["title"], WHITE, center=(self.top_rect.centerx, self.top_rect.y + 32))
        draw_text(self.screen, "Jeu réseau local à partir de ta structure Bataille Navale", f["small"], CYAN, center=(self.top_rect.centerx, self.top_rect.y + 68))
        self.sync_btn.draw(self.screen, f["small"], pygame.mouse.get_pos(), enabled=True)
        if self.state == "connecting":
            draw_text(self.screen, "Connexion au serveur...", f["big"], WHITE, center=self.screen.get_rect().center)
            return
        self.draw_player_list()
        self.draw_info_panel()
        draw_text(self.screen, "Clique sur un joueur vivant pour le cibler.", f["small"], WHITE, center=self.bottom_rect.center)

    def handle_event(self, event):
        if event.type == pygame.VIDEORESIZE:
            self.screen = pygame.display.set_mode((max(MIN_W, event.w), max(MIN_H, event.h)), pygame.RESIZABLE)
            self.compute_layout()
            return
        if event.type != pygame.MOUSEBUTTONDOWN:
            return
        if self.sync_btn.is_clicked(event.pos):
            self.network.send({"type": "sync_request"})
            return
        for pid, rect in self.player_rects:
            if rect.collidepoint(event.pos):
                for p in self.players:
                    if p["id"] == pid and p["alive"] and pid != self.your_id:
                        self.selected_target = pid
                        return
        if self.phase == "lobby" and self.start_btn.is_clicked(event.pos):
            self.send_action()
        elif self.phase in ("night", "day") and self.vote_btn.is_clicked(event.pos):
            self.send_action()
        elif self.phase == "night" and self.current_role() == "Sorciere" and self.skip_btn.is_clicked(event.pos):
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
