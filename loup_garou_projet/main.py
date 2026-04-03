import threading
import time
import pygame

from loup_server import WerewolfServer
from loup_garou_online import WerewolfOnlineGame
from server_discovery import ServerDiscovery

BASE_W, BASE_H = 1000, 700
MIN_W, MIN_H = 820, 620
BG_TOP = (18, 16, 36)
BG_BOTTOM = (56, 32, 70)
WHITE = (240, 240, 245)
CYAN = (135, 205, 235)
PANEL_FILL = (12, 10, 26, 220)
PANEL_BORDER = (120, 110, 160, 110)
BUTTON_BORDER = (200, 190, 230)
GREEN = (80, 120, 90)
GREEN_H = (100, 145, 110)
BLUE = (70, 80, 125)
BLUE_H = (95, 100, 155)
RED = (125, 62, 80)
RED_H = (150, 82, 102)


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
    def __init__(self, text=""):
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.text = text
        self.active = False

    def set_rect(self, rect):
        self.rect = pygame.Rect(rect)

    def draw(self, surface, font):
        color = (40, 30, 62) if self.active else (26, 20, 46)
        pygame.draw.rect(surface, color, self.rect, border_radius=14)
        pygame.draw.rect(surface, CYAN if self.active else BUTTON_BORDER, self.rect, 2, border_radius=14)
        display = self.text or "Entre ton nom"
        img = font.render(display, True, WHITE if self.text else (170, 180, 205))
        surface.blit(img, (self.rect.x + 14, self.rect.centery - img.get_height() // 2))

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_RETURN:
                pass
            elif len(self.text) < 20 and event.unicode.isprintable():
                self.text += event.unicode


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


def draw_text(surface, text, font, color, center=None, topleft=None):
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center is not None:
        rect.center = center
    if topleft is not None:
        rect.topleft = topleft
    surface.blit(img, rect)
    return rect


class Launcher:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((BASE_W, BASE_H), pygame.RESIZABLE)
        pygame.display.set_caption("Loup-Garou - Menu")
        self.clock = pygame.time.Clock()
        self.running = True
        self.state = "menu"
        self.input_name = InputBox()
        self.create_btn = Button("CRÉER UNE PARTIE", GREEN, GREEN_H)
        self.join_btn = Button("REJOINDRE UNE PARTIE", BLUE, BLUE_H)
        self.back_btn = Button("RETOUR", RED, RED_H)
        self.discovery = ServerDiscovery()
        self.discovery.start()
        self.message = "Choisis ton nom puis crée ou rejoins une partie."
        self.hosted_server = None
        self.host_thread = None
        self.selected_index = 0
        self.row_rects = []

    def fonts(self):
        w, h = self.screen.get_size()
        scale = min(w / BASE_W, h / BASE_H)
        return {
            "small": pygame.font.SysFont("arial", max(18, int(22 * scale))),
            "medium": pygame.font.SysFont("arial", max(24, int(30 * scale))),
            "big": pygame.font.SysFont("arial", max(36, int(52 * scale))),
        }

    def valid_name(self):
        name = self.input_name.text.strip()
        return name[:20] if name else "Joueur"

    def launch_game(self, host):
        size = self.screen.get_size()
        game = WerewolfOnlineGame(host, self.valid_name())
        game.run()
        if not pygame.get_init():
            pygame.init()
        self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
        pygame.display.set_caption("Loup-Garou - Menu")
        self.message = "Retour au menu."

    def create_server(self):
        if self.hosted_server is not None:
            try:
                self.hosted_server.shutdown()
            except Exception:
                pass
        self.hosted_server = WerewolfServer(host_name=self.valid_name())
        self.host_thread = threading.Thread(target=self.hosted_server.serve_forever, daemon=True)
        self.host_thread.start()
        time.sleep(0.4)
        self.launch_game("127.0.0.1")

    def join_selected_server(self):
        servers = self.discovery.get_servers()
        if not servers:
            self.message = "Aucun serveur trouvé sur le réseau local."
            return
        host = servers[self.selected_index]["host"]
        self.launch_game(host)

    def menu_layout(self):
        w, h = self.screen.get_size()
        panel = pygame.Rect(w // 2 - 320, h // 2 - 210, 640, 420)
        self.input_name.set_rect((panel.x + 120, panel.y + 110, 400, 50))
        self.create_btn.set_rect((panel.x + 110, panel.y + 210, 420, 54))
        self.join_btn.set_rect((panel.x + 110, panel.y + 288, 420, 54))
        return panel

    def join_layout(self):
        w, h = self.screen.get_size()
        panel = pygame.Rect(70, 60, w - 140, h - 150)
        self.back_btn.set_rect((panel.x, panel.bottom + 16, 160, 44))
        return panel

    def draw_menu(self):
        f = self.fonts()
        panel = self.menu_layout()
        draw_glass_panel(self.screen, panel)
        draw_text(self.screen, "LOUP-GAROU ONLINE", f["big"], WHITE, center=(panel.centerx, panel.y + 56))
        draw_text(self.screen, "Nom du joueur", f["medium"], CYAN, center=(panel.centerx, panel.y + 88))
        self.input_name.draw(self.screen, f["medium"])
        mouse = pygame.mouse.get_pos()
        self.create_btn.draw(self.screen, f["medium"], mouse)
        self.join_btn.draw(self.screen, f["medium"], mouse)
        draw_text(self.screen, self.message, f["small"], WHITE, center=(panel.centerx, panel.bottom + 30))

    def draw_join(self):
        f = self.fonts()
        panel = self.join_layout()
        draw_glass_panel(self.screen, panel)
        draw_text(self.screen, "Serveurs disponibles", f["big"], WHITE, center=(panel.centerx, panel.y + 50))
        self.row_rects = []
        y = panel.y + 110
        servers = self.discovery.get_servers()
        if not servers:
            draw_text(self.screen, "Aucun serveur trouvé.", f["medium"], WHITE, center=panel.center)
        else:
            for i, server in enumerate(servers):
                rect = pygame.Rect(panel.x + 30, y, panel.width - 60, 58)
                color = (80, 52, 100) if i == self.selected_index else (36, 28, 56)
                pygame.draw.rect(self.screen, color, rect, border_radius=14)
                pygame.draw.rect(self.screen, BUTTON_BORDER, rect, 1, border_radius=14)
                draw_text(self.screen, server["name"], f["medium"], WHITE, topleft=(rect.x + 18, rect.y + 8))
                draw_text(self.screen, f"{server['players']}/{server['max_players']} joueurs - {server['host']}", f["small"], CYAN, topleft=(rect.x + 18, rect.y + 30))
                self.row_rects.append((i, rect))
                y += 68
        self.back_btn.draw(self.screen, f["small"], pygame.mouse.get_pos())

    def handle_menu_event(self, event):
        self.input_name.handle_event(event)
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.create_btn.is_clicked(event.pos):
                self.create_server()
            elif self.join_btn.is_clicked(event.pos):
                self.state = "join"
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self.create_server()

    def handle_join_event(self, event):
        servers = self.discovery.get_servers()
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.back_btn.is_clicked(event.pos):
                self.state = "menu"
                return
            for i, rect in self.row_rects:
                if rect.collidepoint(event.pos):
                    self.selected_index = i
                    self.join_selected_server()
                    return
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.state = "menu"
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
                elif self.state == "menu":
                    self.handle_menu_event(event)
                else:
                    self.handle_join_event(event)
            if self.state == "menu":
                self.draw_menu()
            else:
                self.draw_join()
            pygame.display.flip()
        if self.hosted_server is not None:
            self.hosted_server.shutdown()
        self.discovery.stop()
        pygame.quit()


if __name__ == "__main__":
    Launcher().run()
