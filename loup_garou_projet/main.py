
import threading
import time
import pygame

from loup_garou_online import WerewolfOnlineGame
from loup_garou_solo import WerewolfSoloGame
from loup_server import WerewolfServer
from server_discovery import ServerDiscovery
from loup_shared import ROLE_DEFS, CONFIGURABLE_ROLES, normalize_role_config, role_config_label

BASE_W, BASE_H = 1320, 860
MIN_W, MIN_H = 980, 700
BG_TOP = (18, 16, 36)
BG_BOTTOM = (56, 32, 70)
WHITE = (240, 240, 245)
CYAN = (135, 205, 235)
GOLD = (220, 190, 80)
PANEL_FILL = (12, 10, 26, 220)
PANEL_BORDER = (120, 110, 160, 110)
BUTTON_BORDER = (200, 190, 230)
GREEN = (80, 120, 90)
GREEN_H = (100, 145, 110)
BLUE = (70, 80, 125)
BLUE_H = (95, 100, 155)
RED = (125, 62, 80)
RED_H = (150, 82, 102)
PURPLE = (96, 74, 140)
PURPLE_H = (118, 96, 168)


class Button:
    def __init__(self, text, color, hover):
        self.text = text
        self.color = color
        self.hover = hover
        self.rect = pygame.Rect(0, 0, 0, 0)

    def set_rect(self, rect):
        self.rect = pygame.Rect(rect)

    def draw(self, surface, font, mouse_pos):
        color = self.hover if self.rect.collidepoint(mouse_pos) else self.color
        pygame.draw.rect(surface, color, self.rect, border_radius=14)
        pygame.draw.rect(surface, BUTTON_BORDER, self.rect, 2, border_radius=14)
        img = font.render(self.text, True, WHITE)
        surface.blit(img, img.get_rect(center=self.rect.center))

    def is_clicked(self, pos):
        return self.rect.collidepoint(pos)


class InputBox:
    def __init__(self, text="", placeholder=""):
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.text = text
        self.active = False
        self.placeholder = placeholder

    def set_rect(self, rect):
        self.rect = pygame.Rect(rect)

    def draw(self, surface, font):
        color = (40, 30, 62) if self.active else (26, 20, 46)
        pygame.draw.rect(surface, color, self.rect, border_radius=14)
        pygame.draw.rect(surface, CYAN if self.active else BUTTON_BORDER, self.rect, 2, border_radius=14)
        display = self.text or self.placeholder
        img = font.render(display, True, WHITE if self.text else (170, 180, 205))
        surface.blit(img, (self.rect.x + 14, self.rect.centery - img.get_height() // 2))

    def handle_event(self, event, max_len=20):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key != pygame.K_RETURN and len(self.text) < max_len and event.unicode.isprintable():
                self.text += event.unicode


class Stepper:
    def __init__(self, label, value, minimum, maximum):
        self.label = label
        self.value = value
        self.minimum = minimum
        self.maximum = maximum
        self.minus_btn = Button("-", RED, RED_H)
        self.plus_btn = Button("+", GREEN, GREEN_H)
        self.display_rect = pygame.Rect(0, 0, 0, 0)

    def set_layout(self, x, y, width):
        self.minus_btn.set_rect((x, y, 44, 42))
        self.display_rect = pygame.Rect(x + 54, y, width - 108, 42)
        self.plus_btn.set_rect((x + width - 44, y, 44, 42))

    def draw(self, surface, font, small_font, mouse_pos):
        self.minus_btn.draw(surface, font, mouse_pos)
        self.plus_btn.draw(surface, font, mouse_pos)
        pygame.draw.rect(surface, (26, 20, 46), self.display_rect, border_radius=12)
        pygame.draw.rect(surface, BUTTON_BORDER, self.display_rect, 2, border_radius=12)
        img = font.render(str(self.value), True, WHITE)
        surface.blit(img, img.get_rect(center=self.display_rect.center))
        draw_text(surface, self.label, small_font, CYAN, topleft=(self.display_rect.x, self.display_rect.y - 24))

    def handle_click(self, pos):
        if self.minus_btn.is_clicked(pos):
            self.value = max(self.minimum, self.value - 1)
            return True
        if self.plus_btn.is_clicked(pos):
            self.value = min(self.maximum, self.value + 1)
            return True
        return False


def draw_vertical_gradient(surface, top_color, bottom_color):
    width, height = surface.get_size()
    for y in range(height):
        ratio = y / max(1, height)
        color = tuple(int(top_color[i] * (1 - ratio) + bottom_color[i] * ratio) for i in range(3))
        pygame.draw.line(surface, color, (0, y), (width, y))


def draw_glass_panel(surface, rect, radius=24):
    panel = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(panel, PANEL_FILL, (0, 0, rect.width, rect.height), border_radius=radius)
    pygame.draw.rect(panel, PANEL_BORDER, (0, 0, rect.width, rect.height), width=1, border_radius=radius)
    surface.blit(panel, rect.topleft)


def wrap_text(text, font, width):
    words = text.split()
    if not words:
        return [""]
    lines, current = [], words[0]
    for word in words[1:]:
        test = current + " " + word
        if font.size(test)[0] <= width:
            current = test
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def draw_text(surface, text, font, color, center=None, topleft=None):
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center is not None:
        rect.center = center
    if topleft is not None:
        rect.topleft = topleft
    surface.blit(img, rect)
    return rect


class RoleRow:
    def __init__(self, role_name, value):
        self.role_name = role_name
        self.value = value
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.minus_btn = Button("-", RED, RED_H)
        self.plus_btn = Button("+", GREEN, GREEN_H)

    def set_rect(self, rect):
        self.rect = pygame.Rect(rect)
        self.minus_btn.set_rect((self.rect.right - 96, self.rect.y + 12, 36, self.rect.height - 24))
        self.plus_btn.set_rect((self.rect.right - 48, self.rect.y + 12, 36, self.rect.height - 24))

    def handle_click(self, pos):
        max_count = ROLE_DEFS[self.role_name]["max_count"]
        min_count = 1 if self.role_name == "Loup-garou" else 0
        if self.minus_btn.is_clicked(pos):
            self.value = max(min_count, self.value - 1)
            return True
        if self.plus_btn.is_clicked(pos):
            self.value = min(max_count, self.value + 1)
            return True
        return self.rect.collidepoint(pos)

    def draw(self, surface, fonts, mouse_pos, selected=False):
        base = (52, 38, 74) if not selected else (82, 60, 112)
        pygame.draw.rect(surface, base, self.rect, border_radius=14)
        pygame.draw.rect(surface, BUTTON_BORDER, self.rect, 1, border_radius=14)
        camp_color = CYAN if "Village" in ROLE_DEFS[self.role_name]["camp"] else GOLD
        draw_text(surface, self.role_name, fonts["medium"], WHITE, topleft=(self.rect.x + 14, self.rect.y + 8))
        draw_text(surface, ROLE_DEFS[self.role_name]["camp"], fonts["small"], camp_color, topleft=(self.rect.x + 14, self.rect.y + 34))
        value_rect = pygame.Rect(self.rect.right - 150, self.rect.y + 12, 48, self.rect.height - 24)
        pygame.draw.rect(surface, (26, 20, 46), value_rect, border_radius=10)
        pygame.draw.rect(surface, BUTTON_BORDER, value_rect, 2, border_radius=10)
        draw_text(surface, str(self.value), fonts["medium"], WHITE, center=value_rect.center)
        self.minus_btn.draw(surface, fonts["small"], mouse_pos)
        self.plus_btn.draw(surface, fonts["small"], mouse_pos)


class Launcher:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((BASE_W, BASE_H), pygame.RESIZABLE)
        pygame.display.set_caption("Loup-Garou - Menu")
        self.clock = pygame.time.Clock()
        self.running = True
        self.state = "main"

        self.input_name = InputBox(placeholder="Entre ton nom")
        self.main_solo_btn = Button("MODE SOLO", PURPLE, PURPLE_H)
        self.main_online_btn = Button("MODE EN LIGNE", BLUE, BLUE_H)
        self.quit_btn = Button("QUITTER", RED, RED_H)
        self.online_create_btn = Button("CRÉER UN SERVEUR", GREEN, GREEN_H)
        self.online_join_btn = Button("REJOINDRE UN SERVEUR", BLUE, BLUE_H)
        self.config_launch_btn = Button("LANCER LE SERVEUR", GREEN, GREEN_H)
        self.solo_launch_btn = Button("LANCER LE SOLO", GREEN, GREEN_H)
        self.back_btn = Button("RETOUR", RED, RED_H)

        self.max_players_stepper = Stepper("Joueurs max dans la room", 8, 4, 12)
        self.solo_players_stepper = Stepper("Nombre total de joueurs", 6, 4, 12)

        defaults = normalize_role_config()
        self.role_rows = {name: RoleRow(name, defaults.get(name, 0)) for name in CONFIGURABLE_ROLES}
        self.selected_role = CONFIGURABLE_ROLES[0]
        self.role_scroll = 0
        self.discovery = ServerDiscovery()
        self.discovery.start()

        self.message = "Choisis ton pseudo, puis solo ou en ligne."
        self.hosted_server = None
        self.host_thread = None
        self.selected_index = 0
        self.row_rects = []

    def fonts(self):
        w, h = self.screen.get_size()
        scale = min(w / BASE_W, h / BASE_H)
        return {
            "small": pygame.font.SysFont("arial", max(16, int(19 * scale))),
            "medium": pygame.font.SysFont("arial", max(24, int(28 * scale))),
            "big": pygame.font.SysFont("arial", max(34, int(48 * scale))),
        }

    def valid_name(self):
        name = self.input_name.text.strip()
        return name[:20] if name else "Joueur"

    def role_config(self):
        return {name: row.value for name, row in self.role_rows.items()}

    def reset_menu_state(self):
        self.state = "main"
        self.selected_index = 0
        self.row_rects = []
        self.message = "Retour au menu principal."

    def restore_window(self, size):
        if not pygame.get_init():
            pygame.init()
        if not pygame.display.get_init():
            pygame.display.init()
        self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
        pygame.display.set_caption("Loup-Garou - Menu")
        self.clock = pygame.time.Clock()
        pygame.event.clear()

    def launch_online_game(self, host, shutdown_server_after=False):
        current_size = self.screen.get_size()
        try:
            game = WerewolfOnlineGame(host, self.valid_name())
            game.run()
        except Exception as e:
            self.message = f"Erreur pendant la partie : {e}"
        self.restore_window(current_size)
        if shutdown_server_after and self.hosted_server is not None:
            try:
                self.hosted_server.shutdown()
            except Exception:
                pass
            self.hosted_server = None
            self.host_thread = None
        self.reset_menu_state()

    def launch_solo_game(self):
        current_size = self.screen.get_size()
        try:
            game = WerewolfSoloGame(self.valid_name(), self.solo_players_stepper.value, self.role_config())
            game.run()
        except Exception as e:
            self.message = f"Erreur en solo : {e}"
        self.restore_window(current_size)
        self.reset_menu_state()

    def create_server(self):
        if self.hosted_server is not None:
            try:
                self.hosted_server.shutdown()
            except Exception:
                pass
            self.hosted_server = None
            self.host_thread = None
        self.hosted_server = WerewolfServer(
            host_name=self.valid_name(),
            max_players=self.max_players_stepper.value,
            role_config=self.role_config(),
        )
        self.host_thread = threading.Thread(target=self.hosted_server.serve_forever, daemon=True)
        self.host_thread.start()
        time.sleep(0.4)
        self.launch_online_game("127.0.0.1", shutdown_server_after=True)

    def join_selected_server(self):
        servers = self.discovery.get_servers()
        if not servers:
            self.message = "Aucun serveur trouvé sur le réseau local."
            return
        self.selected_index = max(0, min(self.selected_index, len(servers) - 1))
        host = servers[self.selected_index]["host"]
        self.launch_online_game(host, shutdown_server_after=False)

    def main_layout(self):
        w, h = self.screen.get_size()
        panel = pygame.Rect(w // 2 - 330, h // 2 - 230, 660, 460)
        self.input_name.set_rect((panel.x + 120, panel.y + 110, 420, 50))
        self.main_solo_btn.set_rect((panel.x + 120, panel.y + 200, 420, 54))
        self.main_online_btn.set_rect((panel.x + 120, panel.y + 278, 420, 54))
        self.quit_btn.set_rect((panel.x + 120, panel.y + 356, 420, 50))
        return panel

    def online_layout(self):
        w, h = self.screen.get_size()
        panel = pygame.Rect(w // 2 - 330, h // 2 - 230, 660, 460)
        self.online_create_btn.set_rect((panel.x + 120, panel.y + 190, 420, 54))
        self.online_join_btn.set_rect((panel.x + 120, panel.y + 268, 420, 54))
        self.back_btn.set_rect((panel.x + 120, panel.y + 346, 420, 50))
        return panel

    def config_layout(self):
        w, h = self.screen.get_size()
        panel = pygame.Rect(42, 42, w - 84, h - 84)
        top_left = pygame.Rect(panel.x + 26, panel.y + 90, 360, 110)
        role_list = pygame.Rect(panel.x + 26, panel.y + 220, 460, panel.height - 300)
        desc_rect = pygame.Rect(role_list.right + 24, panel.y + 90, panel.width - role_list.width - 74, panel.height - 170)
        self.max_players_stepper.set_layout(top_left.x + 6, top_left.y + 48, top_left.width - 12)
        self.config_launch_btn.set_rect((desc_rect.x, panel.bottom - 58, 320, 42))
        self.back_btn.set_rect((desc_rect.right - 180, panel.bottom - 58, 180, 42))
        return panel, role_list, desc_rect

    def join_layout(self):
        w, h = self.screen.get_size()
        panel = pygame.Rect(60, 50, w - 120, h - 130)
        self.back_btn.set_rect((panel.x, panel.bottom + 14, 160, 42))
        return panel

    def solo_layout(self):
        w, h = self.screen.get_size()
        panel = pygame.Rect(w // 2 - 330, h // 2 - 230, 660, 460)
        self.solo_players_stepper.set_layout(panel.x + 100, panel.y + 180, 460)
        self.solo_launch_btn.set_rect((panel.x + 100, panel.y + 300, 460, 52))
        self.back_btn.set_rect((panel.x + 100, panel.y + 372, 460, 46))
        return panel

    def draw_main(self):
        f = self.fonts()
        panel = self.main_layout()
        draw_glass_panel(self.screen, panel)
        draw_text(self.screen, "LOUP-GAROU", f["big"], WHITE, center=(panel.centerx, panel.y + 56))
        draw_text(self.screen, "Choisis ton pseudo", f["medium"], CYAN, center=(panel.centerx, panel.y + 88))
        self.input_name.draw(self.screen, f["medium"])
        mouse = pygame.mouse.get_pos()
        self.main_solo_btn.draw(self.screen, f["medium"], mouse)
        self.main_online_btn.draw(self.screen, f["medium"], mouse)
        self.quit_btn.draw(self.screen, f["medium"], mouse)
        draw_text(self.screen, self.message, f["small"], WHITE, center=(panel.centerx, panel.bottom + 28))

    def draw_online(self):
        f = self.fonts()
        panel = self.online_layout()
        draw_glass_panel(self.screen, panel)
        draw_text(self.screen, "MODE EN LIGNE", f["big"], WHITE, center=(panel.centerx, panel.y + 70))
        draw_text(self.screen, "Créer une room ou rejoindre un serveur local", f["small"], CYAN, center=(panel.centerx, panel.y + 120))
        mouse = pygame.mouse.get_pos()
        self.online_create_btn.draw(self.screen, f["medium"], mouse)
        self.online_join_btn.draw(self.screen, f["medium"], mouse)
        self.back_btn.draw(self.screen, f["medium"], mouse)

    def draw_config(self):
        f = self.fonts()
        panel, role_list, desc_rect = self.config_layout()
        draw_glass_panel(self.screen, panel)
        draw_text(self.screen, "PANNEAU DE CONTRÔLE DU SERVEUR", f["big"], WHITE, center=(panel.centerx, panel.y + 42))
        draw_text(self.screen, "Choisis les rôles activés et découvre leur description", f["small"], CYAN, center=(panel.centerx, panel.y + 72))
        draw_glass_panel(self.screen, pygame.Rect(role_list.x, role_list.y, role_list.width, role_list.height), 20)
        draw_glass_panel(self.screen, pygame.Rect(desc_rect.x, desc_rect.y, desc_rect.width, desc_rect.height), 20)
        self.max_players_stepper.draw(self.screen, f["medium"], f["small"], pygame.mouse.get_pos())

        visible_count = max(1, role_list.height // 74)
        roles = CONFIGURABLE_ROLES
        max_scroll = max(0, len(roles) - visible_count)
        self.role_scroll = max(0, min(self.role_scroll, max_scroll))
        start = self.role_scroll
        visible_roles = roles[start:start + visible_count]
        y = role_list.y + 12
        for role_name in visible_roles:
            row = self.role_rows[role_name]
            row.set_rect((role_list.x + 12, y, role_list.width - 24, 62))
            row.draw(self.screen, f, pygame.mouse.get_pos(), selected=(role_name == self.selected_role))
            y += 72

        if len(roles) > visible_count:
            bar_x = role_list.right - 10
            bar_y = role_list.y + 12
            bar_h = role_list.height - 24
            pygame.draw.rect(self.screen, (40, 40, 70), (bar_x, bar_y, 6, bar_h), border_radius=3)
            thumb_h = max(30, int(bar_h * (visible_count / len(roles))))
            thumb_y = bar_y + int((bar_h - thumb_h) * (self.role_scroll / max_scroll if max_scroll else 0))
            pygame.draw.rect(self.screen, CYAN, (bar_x, thumb_y, 6, thumb_h), border_radius=3)

        role = ROLE_DEFS[self.selected_role]
        draw_text(self.screen, self.selected_role, f["big"], WHITE, topleft=(desc_rect.x + 20, desc_rect.y + 18))
        draw_text(self.screen, f"Camp : {role['camp']} | Aura : {role['aura']}", f["small"], GOLD, topleft=(desc_rect.x + 20, desc_rect.y + 60))
        y = desc_rect.y + 100
        for line in wrap_text(role["description"], f["small"], desc_rect.width - 40):
            draw_text(self.screen, line, f["small"], WHITE, topleft=(desc_rect.x + 20, y))
            y += 24

        y += 14
        summary = role_config_label(self.role_config())
        for line in wrap_text("Composition actuelle : " + summary, f["small"], desc_rect.width - 40):
            draw_text(self.screen, line, f["small"], CYAN, topleft=(desc_rect.x + 20, y))
            y += 24

        self.config_launch_btn.draw(self.screen, f["medium"], pygame.mouse.get_pos())
        self.back_btn.draw(self.screen, f["medium"], pygame.mouse.get_pos())

    def draw_solo(self):
        f = self.fonts()
        panel = self.solo_layout()
        draw_glass_panel(self.screen, panel)
        draw_text(self.screen, "MODE SOLO", f["big"], WHITE, center=(panel.centerx, panel.y + 70))
        draw_text(self.screen, "Tu joues contre des IA sur la même machine", f["small"], CYAN, center=(panel.centerx, panel.y + 120))
        self.solo_players_stepper.draw(self.screen, f["medium"], f["small"], pygame.mouse.get_pos())
        self.solo_launch_btn.draw(self.screen, f["medium"], pygame.mouse.get_pos())
        self.back_btn.draw(self.screen, f["medium"], pygame.mouse.get_pos())

    def draw_join(self):
        f = self.fonts()
        panel = self.join_layout()
        draw_glass_panel(self.screen, panel)
        draw_text(self.screen, "Serveurs disponibles", f["big"], WHITE, center=(panel.centerx, panel.y + 46))
        self.row_rects = []
        y = panel.y + 100
        servers = self.discovery.get_servers()
        if not servers:
            draw_text(self.screen, "Aucun serveur trouvé.", f["medium"], WHITE, center=panel.center)
        else:
            self.selected_index = max(0, min(self.selected_index, len(servers) - 1))
            for i, server in enumerate(servers):
                rect = pygame.Rect(panel.x + 24, y, panel.width - 48, 78)
                color = (80, 52, 100) if i == self.selected_index else (36, 28, 56)
                pygame.draw.rect(self.screen, color, rect, border_radius=14)
                pygame.draw.rect(self.screen, BUTTON_BORDER, rect, 1, border_radius=14)
                draw_text(self.screen, server["name"], f["medium"], WHITE, topleft=(rect.x + 18, rect.y + 8))
                draw_text(self.screen, f"{server['players']}/{server['max_players']} joueurs - {server['host']}", f["small"], CYAN, topleft=(rect.x + 18, rect.y + 36))
                draw_text(self.screen, f"Rôles : {server.get('roles', 'non précisés')}", f["small"], WHITE, topleft=(rect.x + 18, rect.y + 56))
                self.row_rects.append((i, rect))
                y += 88
        self.back_btn.draw(self.screen, f["small"], pygame.mouse.get_pos())

    def handle_main_event(self, event):
        self.input_name.handle_event(event)
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.main_solo_btn.is_clicked(event.pos):
                self.state = "solo"
            elif self.main_online_btn.is_clicked(event.pos):
                self.state = "online"
            elif self.quit_btn.is_clicked(event.pos):
                self.running = False

    def handle_online_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.online_create_btn.is_clicked(event.pos):
                self.state = "config"
            elif self.online_join_btn.is_clicked(event.pos):
                self.state = "join"
                self.selected_index = 0
            elif self.back_btn.is_clicked(event.pos):
                self.reset_menu_state()

    def handle_config_event(self, event):
        panel, role_list, desc_rect = self.config_layout()
        if event.type == pygame.MOUSEWHEEL:
            mouse_pos = pygame.mouse.get_pos()
            if role_list.collidepoint(mouse_pos):
                if event.y < 0:
                    self.role_scroll += 1
                elif event.y > 0:
                    self.role_scroll -= 1
            return
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.max_players_stepper.handle_click(event.pos)
            for role_name in CONFIGURABLE_ROLES:
                row = self.role_rows[role_name]
                if row.rect.collidepoint(event.pos) or row.minus_btn.is_clicked(event.pos) or row.plus_btn.is_clicked(event.pos):
                    row.handle_click(event.pos)
                    self.selected_role = role_name
                    break
            if self.config_launch_btn.is_clicked(event.pos):
                self.create_server()
            elif self.back_btn.is_clicked(event.pos):
                self.state = "online"

    def handle_solo_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.solo_players_stepper.handle_click(event.pos)
            if self.solo_launch_btn.is_clicked(event.pos):
                self.launch_solo_game()
            elif self.back_btn.is_clicked(event.pos):
                self.reset_menu_state()

    def handle_join_event(self, event):
        servers = self.discovery.get_servers()
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.back_btn.is_clicked(event.pos):
                self.state = "online"
                return
            for i, rect in self.row_rects:
                if rect.collidepoint(event.pos):
                    self.selected_index = i
                    self.join_selected_server()
                    return
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.state = "online"
            elif event.key == pygame.K_DOWN and servers:
                self.selected_index = min(self.selected_index + 1, len(servers) - 1)
            elif event.key == pygame.K_UP and servers:
                self.selected_index = max(self.selected_index - 1, 0)
            elif event.key == pygame.K_RETURN and servers:
                self.join_selected_server()

    def run(self):
        while self.running:
            self.clock.tick(60)
            draw_vertical_gradient(self.screen, BG_TOP, BG_BOTTOM)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.VIDEORESIZE:
                    self.screen = pygame.display.set_mode((max(MIN_W, event.w), max(MIN_H, event.h)), pygame.RESIZABLE)
                elif self.state == "main":
                    self.handle_main_event(event)
                elif self.state == "online":
                    self.handle_online_event(event)
                elif self.state == "config":
                    self.handle_config_event(event)
                elif self.state == "solo":
                    self.handle_solo_event(event)
                else:
                    self.handle_join_event(event)
            if self.state == "main":
                self.draw_main()
            elif self.state == "online":
                self.draw_online()
            elif self.state == "config":
                self.draw_config()
            elif self.state == "solo":
                self.draw_solo()
            else:
                self.draw_join()
            pygame.display.flip()
        if self.hosted_server is not None:
            try:
                self.hosted_server.shutdown()
            except Exception:
                pass
        self.discovery.stop()
        pygame.quit()


if __name__ == "__main__":
    Launcher().run()
