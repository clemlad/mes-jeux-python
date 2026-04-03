import threading
import time
import pygame
from naval_server import NavalServer
from naval_strike_online import NavalStrikeOnlineGame
from server_discovery import ServerDiscovery

BASE_W, BASE_H = 1000, 700
MIN_W, MIN_H = 820, 620
BG_TOP = (6, 18, 35)
BG_BOTTOM = (12, 52, 95)
WHITE = (235, 240, 245)
CYAN = (120, 190, 220)
PANEL_FILL = (8, 14, 24, 220)
PANEL_BORDER = (90, 130, 170, 95)
GRID_SOFT = (50, 80, 110)
GRID_DARK = (30, 55, 80)
BUTTON_BORDER = (180, 205, 230)
GREEN = (70, 120, 90)
GREEN_H = (90, 160, 110)
BLUE = (52, 76, 116)
BLUE_H = (72, 104, 150)
RED = (115, 62, 70)
RED_H = (145, 82, 92)
SCROLL_TRACK = (20, 34, 54)
SCROLL_THUMB = (90, 130, 180)
SCROLL_THUMB_H = (120, 165, 220)


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
        pygame.draw.rect(surface, color, self.rect, border_radius=max(12, self.rect.height // 4))
        pygame.draw.rect(surface, BUTTON_BORDER, self.rect, 2, border_radius=max(12, self.rect.height // 4))
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
        color = (26, 46, 76) if self.active else (16, 30, 52)
        radius = max(12, self.rect.height // 4)
        pygame.draw.rect(surface, color, self.rect, border_radius=radius)
        pygame.draw.rect(surface, CYAN if self.active else BUTTON_BORDER, self.rect, 2, border_radius=radius)
        display = self.text or "Entre ton nom"
        img = font.render(display, True, WHITE if self.text else (170, 185, 205))
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


def draw_ocean_overlay(surface):
    width, height = surface.get_size()
    step_y = max(36, height // 14)
    step_x = max(52, width // 14)
    for y in range(0, height, step_y):
        pygame.draw.line(surface, GRID_SOFT, (0, y), (width, y), 1)
    for x in range(0, width, step_x):
        pygame.draw.line(surface, GRID_DARK, (x, 0), (x, height), 1)


def draw_glass_panel(surface, rect, radius=22):
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


class MainApp:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((BASE_W, BASE_H), pygame.RESIZABLE)
        pygame.display.set_caption("Naval Strike - Menu")
        self.clock = pygame.time.Clock()
        self.input_name = InputBox("")
        self.create_btn = Button("CRÉER UN SERVEUR", GREEN, GREEN_H)
        self.join_btn = Button("REJOINDRE UN SERVEUR", BLUE, BLUE_H)
        self.back_btn = Button("RETOUR", RED, RED_H)
        self.refresh_btn = Button("ACTUALISER", BLUE, BLUE_H)
        self.discovery = ServerDiscovery()
        self.discovery.start()
        self.state = "menu"
        self.message = "Choisis ton nom puis crée ou rejoins une partie."
        self.running = True
        self.hosted_server = None
        self.host_thread = None
        self.selected_index = 0
        self.scroll_offset = 0
        self.row_rects = []
        self.scrollbar_rect = pygame.Rect(0, 0, 0, 0)
        self.scroll_thumb_rect = pygame.Rect(0, 0, 0, 0)
        self.dragging_scrollbar = False
        self.drag_scroll_start_y = 0
        self.drag_scroll_start_offset = 0

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
        current_size = self.screen.get_size()
        game = NavalStrikeOnlineGame(host, self.valid_name())
        game.run()

        if not pygame.get_init():
            pygame.init()
        if not pygame.display.get_init():
            pygame.display.init()

        self.screen = pygame.display.set_mode(current_size, pygame.RESIZABLE)
        pygame.display.set_caption("Naval Strike - Menu")
        self.message = "Retour au menu."

    def create_server(self):
        if self.hosted_server is not None:
            try:
                self.hosted_server.shutdown()
            except Exception:
                pass
        self.hosted_server = NavalServer(host_name=self.valid_name())
        self.host_thread = threading.Thread(target=self.hosted_server.serve_forever, daemon=True)
        self.host_thread.start()
        time.sleep(0.4)
        self.launch_game("127.0.0.1")

    def join_selected_server(self):
        servers = self.discovery.get_servers()
        if not servers:
            self.message = "Aucun serveur trouvé sur le réseau local."
            return
        self.selected_index = max(0, min(self.selected_index, len(servers) - 1))
        self.ensure_selected_visible(servers)
        host = servers[self.selected_index]["host"]
        self.launch_game(host)

    def menu_layout(self):
        w, h = self.screen.get_size()
        panel_w = min(int(w * 0.64), 680)
        panel_h = min(int(h * 0.62), 460)
        panel_x = (w - panel_w) // 2
        panel_y = max(50, int(h * 0.14))
        input_w = int(panel_w * 0.56)
        btn_w = int(panel_w * 0.66)
        input_h = max(48, int(h * 0.075))
        btn_h = max(54, int(h * 0.09))
        self.input_name.set_rect((w // 2 - input_w // 2, panel_y + int(panel_h * 0.30), input_w, input_h))
        self.create_btn.set_rect((w // 2 - btn_w // 2, panel_y + int(panel_h * 0.50), btn_w, btn_h))
        self.join_btn.set_rect((w // 2 - btn_w // 2, panel_y + int(panel_h * 0.68), btn_w, btn_h))
        return pygame.Rect(panel_x, panel_y, panel_w, panel_h)

    def join_layout(self):
        w, h = self.screen.get_size()
        panel = pygame.Rect(max(32, int(w * 0.09)), max(32, int(h * 0.08)), w - max(64, int(w * 0.18)), h - max(110, int(h * 0.16)))
        btn_h = max(46, int(h * 0.07))
        self.back_btn.set_rect((panel.x, panel.bottom + 14, max(160, int(panel.width * 0.20)), btn_h))
        self.refresh_btn.set_rect((panel.right - max(180, int(panel.width * 0.22)), panel.bottom + 14, max(180, int(panel.width * 0.22)), btn_h))
        return panel

    def get_join_list_geometry(self, servers_count):
        panel = self.join_layout()
        list_top = panel.y + 130
        list_bottom = panel.bottom - 20
        list_left = panel.x + 28
        scrollbar_w = 12
        list_right = panel.right - 28 - scrollbar_w - 10
        row_h = max(52, min(72, (list_bottom - list_top) // max(1, min(7, max(1, servers_count or 5)))))
        visible = max(1, (list_bottom - list_top) // row_h)
        return {
            "panel": panel,
            "list_top": list_top,
            "list_bottom": list_bottom,
            "list_left": list_left,
            "list_right": list_right,
            "row_h": row_h,
            "visible": visible,
            "scrollbar": pygame.Rect(list_right + 10, list_top, scrollbar_w, max(20, list_bottom - list_top)),
        }

    def clamp_scroll(self, servers):
        geometry = self.get_join_list_geometry(len(servers))
        max_offset = max(0, len(servers) - geometry["visible"])
        self.scroll_offset = max(0, min(self.scroll_offset, max_offset))
        self.selected_index = max(0, min(self.selected_index, max(0, len(servers) - 1)))

    def ensure_selected_visible(self, servers):
        if not servers:
            self.selected_index = 0
            self.scroll_offset = 0
            return
        geometry = self.get_join_list_geometry(len(servers))
        visible = geometry["visible"]
        self.selected_index = max(0, min(self.selected_index, len(servers) - 1))
        if self.selected_index < self.scroll_offset:
            self.scroll_offset = self.selected_index
        elif self.selected_index >= self.scroll_offset + visible:
            self.scroll_offset = self.selected_index - visible + 1
        self.clamp_scroll(servers)

    def scroll_servers(self, delta, servers):
        if not servers:
            return
        self.scroll_offset += delta
        self.clamp_scroll(servers)

    def update_scroll_from_thumb(self, mouse_y, servers):
        if not servers:
            return
        geometry = self.get_join_list_geometry(len(servers))
        visible = geometry["visible"]
        max_offset = max(0, len(servers) - visible)
        if max_offset <= 0:
            self.scroll_offset = 0
            return
        track = geometry["scrollbar"]
        thumb_h = max(36, int(track.height * visible / len(servers)))
        movable = max(1, track.height - thumb_h)
        delta_y = mouse_y - self.drag_scroll_start_y
        new_thumb_y = (self.drag_scroll_start_offset / max_offset) * movable + delta_y
        new_thumb_y = max(0, min(movable, new_thumb_y))
        self.scroll_offset = int(round((new_thumb_y / movable) * max_offset))
        self.clamp_scroll(servers)

    def draw_menu(self):
        f = self.fonts()
        w, h = self.screen.get_size()
        panel = self.menu_layout()
        draw_glass_panel(self.screen, panel, radius=26)
        draw_text(self.screen, "NAVAL STRIKE", f["big"], WHITE, center=(w // 2, panel.y + int(panel.height * 0.12)))
        draw_text(self.screen, "Nom du joueur", f["medium"], CYAN, center=(w // 2, panel.y + int(panel.height * 0.23)))
        self.input_name.draw(self.screen, f["medium"])
        mouse = pygame.mouse.get_pos()
        self.create_btn.draw(self.screen, f["medium"], mouse)
        self.join_btn.draw(self.screen, f["medium"], mouse)
        draw_text(self.screen, self.message, f["small"], WHITE, center=(w // 2, min(h - 28, panel.bottom + 34)))

    def draw_join(self):
        f = self.fonts()
        w, h = self.screen.get_size()
        panel = self.join_layout()
        draw_glass_panel(self.screen, panel, radius=26)
        draw_text(self.screen, "Serveurs disponibles", f["big"], WHITE, center=(w // 2, panel.y + 56))
        draw_text(self.screen, f"Nom : {self.valid_name()}", f["small"], CYAN, center=(w // 2, panel.y + 102))

        servers = self.discovery.get_servers()
        self.clamp_scroll(servers)
        self.ensure_selected_visible(servers)
        geometry = self.get_join_list_geometry(len(servers))
        list_top = geometry["list_top"]
        row_h = geometry["row_h"]
        visible = geometry["visible"]
        self.row_rects = []
        self.scrollbar_rect = geometry["scrollbar"]
        self.scroll_thumb_rect = pygame.Rect(0, 0, 0, 0)

        if not servers:
            draw_text(self.screen, "Aucun serveur trouvé pour l'instant.", f["medium"], WHITE, center=(w // 2, panel.centery))
        else:
            mouse = pygame.mouse.get_pos()
            start = self.scroll_offset
            end = min(len(servers), start + visible)
            y = list_top

            for absolute_i in range(start, end):
                server = servers[absolute_i]
                rect = pygame.Rect(geometry["list_left"], y, geometry["list_right"] - geometry["list_left"], row_h - 8)
                self.row_rects.append((absolute_i, rect))
                if absolute_i == self.selected_index:
                    color = (36, 70, 115)
                elif rect.collidepoint(mouse):
                    color = (22, 44, 74)
                else:
                    color = (12, 24, 40)
                pygame.draw.rect(self.screen, color, rect, border_radius=14)
                pygame.draw.rect(self.screen, BUTTON_BORDER, rect, 1, border_radius=14)
                left = server.get("name", "Partie")
                right = f"{server.get('players', 0)}/{server.get('max_players', 2)} joueurs - {server.get('host', '')}"
                draw_text(self.screen, left, f["medium"], WHITE, topleft=(rect.x + 18, rect.y + 10))
                draw_text(self.screen, right, f["small"], CYAN, topleft=(rect.x + 18, rect.y + row_h // 2 - 2))
                y += row_h

            if len(servers) > visible:
                pygame.draw.rect(self.screen, SCROLL_TRACK, self.scrollbar_rect, border_radius=8)
                thumb_h = max(36, int(self.scrollbar_rect.height * visible / len(servers)))
                movable = max(1, self.scrollbar_rect.height - thumb_h)
                max_offset = max(1, len(servers) - visible)
                thumb_y = self.scrollbar_rect.y + int((self.scroll_offset / max_offset) * movable)
                self.scroll_thumb_rect = pygame.Rect(self.scrollbar_rect.x, thumb_y, self.scrollbar_rect.width, thumb_h)
                thumb_color = SCROLL_THUMB_H if self.dragging_scrollbar or self.scroll_thumb_rect.collidepoint(mouse) else SCROLL_THUMB
                pygame.draw.rect(self.screen, thumb_color, self.scroll_thumb_rect, border_radius=8)

        mouse = pygame.mouse.get_pos()
        self.back_btn.draw(self.screen, f["small"], mouse)
        self.refresh_btn.draw(self.screen, f["small"], mouse)
        draw_text(self.screen, "Entrée pour rejoindre, molette/flèches pour défiler, Échap pour revenir.", f["small"], WHITE, center=(w // 2, h - 16 - self.back_btn.rect.height // 2))

    def handle_menu_event(self, event):
        self.input_name.handle_event(event)
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.create_btn.is_clicked(event.pos):
                self.create_server()
            elif self.join_btn.is_clicked(event.pos):
                self.state = "join"
                self.selected_index = 0
                self.scroll_offset = 0
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self.create_server()

    def handle_join_event(self, event):
        servers = self.discovery.get_servers()
        self.clamp_scroll(servers)

        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.back_btn.is_clicked(event.pos):
                self.state = "menu"
                self.dragging_scrollbar = False
                return
            if self.refresh_btn.is_clicked(event.pos):
                self.message = "Recherche des serveurs..."
                return
            if self.scroll_thumb_rect.collidepoint(event.pos):
                self.dragging_scrollbar = True
                self.drag_scroll_start_y = event.pos[1]
                self.drag_scroll_start_offset = self.scroll_offset
                return
            if self.scrollbar_rect.collidepoint(event.pos) and len(servers) > self.get_join_list_geometry(len(servers))["visible"]:
                clicked_above = event.pos[1] < self.scroll_thumb_rect.y
                clicked_below = event.pos[1] > self.scroll_thumb_rect.bottom
                if clicked_above:
                    self.scroll_servers(-1, servers)
                elif clicked_below:
                    self.scroll_servers(1, servers)
                return
            for absolute_i, rect in self.row_rects:
                if rect.collidepoint(event.pos):
                    self.selected_index = absolute_i
                    self.ensure_selected_visible(servers)
                    self.join_selected_server()
                    return

        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging_scrollbar = False

        elif event.type == pygame.MOUSEMOTION and self.dragging_scrollbar:
            self.update_scroll_from_thumb(event.pos[1], servers)

        elif event.type == pygame.MOUSEWHEEL:
            self.scroll_servers(-event.y, servers)

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.state = "menu"
                self.dragging_scrollbar = False
            elif event.key == pygame.K_DOWN and servers:
                self.selected_index = min(self.selected_index + 1, len(servers) - 1)
                self.ensure_selected_visible(servers)
            elif event.key == pygame.K_UP and servers:
                self.selected_index = max(self.selected_index - 1, 0)
                self.ensure_selected_visible(servers)
            elif event.key == pygame.K_PAGEDOWN and servers:
                self.selected_index = min(self.selected_index + self.get_join_list_geometry(len(servers))["visible"], len(servers) - 1)
                self.ensure_selected_visible(servers)
            elif event.key == pygame.K_PAGEUP and servers:
                self.selected_index = max(self.selected_index - self.get_join_list_geometry(len(servers))["visible"], 0)
                self.ensure_selected_visible(servers)
            elif event.key == pygame.K_RETURN and servers:
                self.join_selected_server()

    def run(self):
        while self.running:
            self.clock.tick(60)
            draw_vertical_gradient(self.screen, BG_TOP, BG_BOTTOM)
            draw_ocean_overlay(self.screen)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.VIDEORESIZE:
                    new_size = (max(MIN_W, event.w), max(MIN_H, event.h))
                    self.screen = pygame.display.set_mode(new_size, pygame.RESIZABLE)
                elif self.state == "menu":
                    self.handle_menu_event(event)
                else:
                    self.handle_join_event(event)
            if self.state == "menu":
                self.draw_menu()
            else:
                self.draw_join()
            pygame.display.flip()
        self.discovery.stop()
        if self.hosted_server is not None:
            try:
                self.hosted_server.shutdown()
            except Exception:
                pass
        pygame.quit()


if __name__ == "__main__":
    MainApp().run()
