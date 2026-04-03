import json
import socket
import threading
import pygame
from naval_shared import (
    Board,
    Ship,
    SHIPS_CONFIG,
    SUBMARINE_ORIENTATIONS,
    GRID_SIZE,
    LETTERS,
    layout_from_board,
)

BASE_W, BASE_H = 1280, 900
MIN_W, MIN_H = 980, 760
FPS = 60

BG_TOP = (6, 18, 35)
BG_BOTTOM = (12, 52, 95)
WHITE = (235, 240, 245)
BLACK = (8, 10, 14)
NAVY = (18, 35, 60)
CYAN = (120, 190, 220)
LIGHT_BLUE = (150, 205, 235)
GRID_SOFT = (50, 80, 110)
GRID_DARK = (30, 55, 80)
GRID_LINE = (70, 105, 140)
BLUE = (24, 82, 135)
SHIP_COLOR = (95, 110, 125)
SHIP_BORDER = (60, 75, 90)
HIT_FILL = (220, 85, 85)
HIT_DARK = (120, 35, 35)
MISS = (190, 205, 220)
SUNK_FILL = (120, 45, 45)
SUNK_BORDER = (170, 70, 70)
GREEN = (60, 190, 110)
RED = (200, 70, 70)
GOLD = (220, 190, 80)
PANEL_FILL = (8, 14, 24, 220)
PANEL_BORDER = (90, 130, 170, 95)
BUTTON_BORDER = (180, 205, 230)


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
            messages = self.messages[:]
            self.messages.clear()
        return messages

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

    def draw(self, surface, font, mouse_pos, enabled=None):
        if enabled is not None:
            self.enabled = enabled
        base_color = self.color if self.enabled else (70, 80, 96)
        hover_color = self.hover if self.enabled else (70, 80, 96)
        color = hover_color if self.enabled and self.rect.collidepoint(mouse_pos) else base_color
        radius = max(12, self.rect.height // 4)
        pygame.draw.rect(surface, color, self.rect, border_radius=radius)
        pygame.draw.rect(surface, BUTTON_BORDER, self.rect, 2, border_radius=radius)
        txt_color = WHITE if self.enabled else (180, 190, 205)
        img = font.render(self.text, True, txt_color)
        surface.blit(img, img.get_rect(center=self.rect.center))

    def is_clicked(self, pos):
        return self.enabled and self.rect.collidepoint(pos)


def draw_vertical_gradient(surface, top_color, bottom_color):
    width, height = surface.get_size()
    for y in range(height):
        ratio = y / max(1, height)
        color = tuple(int(top_color[i] * (1 - ratio) + bottom_color[i] * ratio) for i in range(3))
        pygame.draw.line(surface, color, (0, y), (width, y))


def draw_ocean_overlay(surface):
    width, height = surface.get_size()
    step_y = max(36, height // 16)
    step_x = max(52, width // 16)
    for y in range(0, height, step_y):
        pygame.draw.line(surface, GRID_SOFT, (0, y), (width, y), 1)
    for x in range(0, width, step_x):
        pygame.draw.line(surface, GRID_DARK, (x, 0), (x, height), 1)


def draw_glass_panel(surface, rect, radius=18):
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


def draw_wrapped_text(surface, text, font, color, rect, line_spacing=8):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = word if not current else current + " " + word
        if font.size(test)[0] <= rect.width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    y = rect.top
    for line in lines:
        img = font.render(line, True, color)
        surface.blit(img, (rect.left, y))
        y += img.get_height() + line_spacing


def ship_label(name):
    return "Sous-marin" if name == "Sous-marin T" else name


class NavalStrikeOnlineGame:
    def __init__(self, host, player_name):
        pygame.init()
        self.screen = pygame.display.set_mode((BASE_W, BASE_H), pygame.RESIZABLE)
        pygame.display.set_caption("Naval Strike Online")
        self.clock = pygame.time.Clock()
        self.network = NetworkClient(host, player_name)
        self.local_name = player_name
        self.enemy_name = "Adversaire"
        self.player_id = None
        self.player_board = Board()
        self.enemy_board = Board()
        self.state = "connecting"
        self.turn = False
        self.winner = None
        self.message = "Connexion au serveur..."
        self.current_orientation = "H"
        self.selected_ship_name = None
        self.hover_cell = None
        self.placement_locked = False
        self.rematch_requests = set()
        self.place_auto_btn = Button("PLACEMENT AUTO", (70, 120, 90), (90, 160, 110))
        self.place_send_btn = Button("VALIDER LE PLACEMENT", (52, 76, 116), (72, 104, 150))
        self.sync_btn = Button("RESYNCHRONISER", (70, 90, 130), (100, 130, 180))
        self.rematch_btn = Button("REJOUER", (130, 96, 54), (170, 126, 72))
        self.running = True
        self.compute_layout()

    def fonts(self):
        w, h = self.screen.get_size()
        scale = min(w / BASE_W, h / BASE_H)
        return {
            "small": pygame.font.SysFont("arial", max(16, int(20 * scale))),
            "medium": pygame.font.SysFont("arial", max(22, int(28 * scale))),
            "big": pygame.font.SysFont("arial", max(34, int(44 * scale))),
            "title": pygame.font.SysFont("arial", max(40, int(56 * scale))),
            "panel_title": pygame.font.SysFont("arial", max(24, int(34 * scale))),
            "panel_row": pygame.font.SysFont("arial", max(17, int(20 * scale))),
            "panel_status": pygame.font.SysFont("arial", max(18, int(22 * scale)), bold=True),
        }

    def compute_layout(self):
        w, h = self.screen.get_size()
        self.top_bar_h = max(92, int(h * 0.12))
        self.message_h = max(38, int(h * 0.05))
        margin_x = max(26, int(w * 0.04))
        gap = max(26, int(w * 0.035))
        panel_gap_y = max(18, int(h * 0.02))
        status_h = max(190, int(h * 0.24))
        available_w = w - margin_x * 2 - gap
        available_h = h - self.top_bar_h - self.message_h - status_h - panel_gap_y * 3
        self.cell_size = max(26, min(56, int(min(available_w / (2 * GRID_SIZE), available_h / GRID_SIZE))))
        board_px = self.cell_size * GRID_SIZE
        total_boards_w = board_px * 2 + gap
        self.left_grid_x = (w - total_boards_w) // 2
        self.right_grid_x = self.left_grid_x + board_px + gap
        self.grid_y = self.top_bar_h + self.message_h + panel_gap_y * 2
        self.board_px = board_px
        status_y = self.grid_y + board_px + panel_gap_y
        self.left_status_rect = pygame.Rect(self.left_grid_x, status_y, board_px, status_h)
        self.right_status_rect = pygame.Rect(self.right_grid_x, status_y, board_px, status_h)
        btn_h = max(42, int(h * 0.055))
        auto_w = max(180, int(board_px * 0.42))
        send_w = max(250, int(board_px * 0.54))
        placement_btn_y = min(h - btn_h - 12, self.grid_y + board_px + 12)
        self.place_auto_btn.set_rect((self.left_grid_x, placement_btn_y, auto_w, btn_h))
        self.place_send_btn.set_rect((self.left_grid_x + auto_w + 14, placement_btn_y, send_w, btn_h))
        sync_w = max(180, int(w * 0.18))
        self.sync_btn.set_rect((w - sync_w - margin_x, max(18, self.top_bar_h // 2 - btn_h // 2), sync_w, btn_h))
        info_w = max(300, int(board_px * 0.95))
        panel_h = min(max(290, int(h * 0.38)), max(300, board_px - 10))
        self.placement_panel_rect = pygame.Rect(self.right_grid_x, self.grid_y, info_w, panel_h)
        self.message_rect = pygame.Rect((w - min(760, int(w * 0.62))) // 2, self.top_bar_h + 6, min(760, int(w * 0.62)), self.message_h)
        rematch_w = max(220, int(w * 0.22))
        rematch_h = max(50, int(h * 0.07))
        self.rematch_btn.set_rect((w // 2 - rematch_w // 2, h // 2 + 10, rematch_w, rematch_h))

    def board_to_pixel(self, board_x, board_y, row, col):
        return board_x + col * self.cell_size, board_y + row * self.cell_size

    def pixel_to_board(self, mouse_x, mouse_y, board_x, board_y):
        rel_x = mouse_x - board_x
        rel_y = mouse_y - board_y
        if rel_x < 0 or rel_y < 0:
            return None
        col = rel_x // self.cell_size
        row = rel_y // self.cell_size
        if 0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE:
            return int(row), int(col)
        return None

    def placed_ship_names(self):
        return {ship.name for ship in self.player_board.ships}

    def current_ship_config(self):
        target_name = self.selected_ship_name
        if target_name is None:
            placed = self.placed_ship_names()
            for name, size in SHIPS_CONFIG:
                if name not in placed:
                    target_name = name
                    break
        if target_name is None:
            return None
        for name, size in SHIPS_CONFIG:
            if name == target_name:
                return name, size
        return None

    def set_orientation_from_ship(self, ship):
        if ship.name == "Sous-marin T":
            positions = set(ship.positions)
            for row, col in positions:
                if {(row, col - 1), (row, col), (row, col + 1), (row - 1, col)} == positions:
                    self.current_orientation = "haut"
                    return
                if {(row, col - 1), (row, col), (row, col + 1), (row + 1, col)} == positions:
                    self.current_orientation = "bas"
                    return
                if {(row - 1, col), (row, col), (row + 1, col), (row, col - 1)} == positions:
                    self.current_orientation = "gauche"
                    return
                if {(row - 1, col), (row, col), (row + 1, col), (row, col + 1)} == positions:
                    self.current_orientation = "droite"
                    return
            self.current_orientation = "haut"
        else:
            rows = {row for row, _ in ship.positions}
            self.current_orientation = "H" if len(rows) == 1 else "V"

    def process_network(self):
        for msg in self.network.pop_messages():
            msg_type = msg.get("type")
            names = msg.get("player_names")

            if names and self.player_id is not None:
                self.local_name = names[self.player_id]
                self.enemy_name = names[1 - self.player_id]

            if "rematch_requests" in msg:
                self.rematch_requests = set(msg.get("rematch_requests", []))

            if msg_type == "welcome":
                self.player_id = msg["player_id"]
                self.state = "placement"
                self.placement_locked = False
                self.selected_ship_name = None
                self.message = f"Connecté. Place tes bateaux, {self.local_name}."

            elif msg_type in ("state_sync", "shot_result"):
                previous_state = self.state

                self.player_board = Board.from_state(msg["your_board"])
                self.enemy_board = Board.from_state(msg["enemy_board"])
                self.turn = msg.get("your_turn", False)
                self.winner = msg.get("winner")

                if msg.get("player_names") and self.player_id is not None:
                    self.local_name = msg["player_names"][self.player_id]
                    self.enemy_name = msg["player_names"][1 - self.player_id]

                phase = msg.get("phase")

                if phase == "end" and self.winner is not None:
                    self.state = "end"
                    self.placement_locked = True
                    self.selected_ship_name = None

                    if msg_type == "shot_result":
                        self.message = msg.get("message", "Match terminé.")
                    else:
                        self.message = "Victoire !" if self.winner == self.player_id else "Défaite..."

                elif phase == "battle":
                    self.state = "battle"
                    self.placement_locked = True
                    self.selected_ship_name = None
                    self.message = msg.get("message", "Bataille en cours.")

                else:
                    self.state = "placement"
                    self.winner = None

                    # Si on revient depuis la bataille ou la fin, c'est une nouvelle manche
                    if previous_state in ("battle", "end"):
                        self.placement_locked = False
                        self.selected_ship_name = None
                        self.rematch_requests = set()

                    if len(self.player_board.ships) == len(SHIPS_CONFIG):
                        self.message = "En attente de l'autre joueur..."
                    else:
                        self.message = "Place tes bateaux."

            elif msg_type == "info":
                self.message = msg.get("message", self.message)

            elif msg_type == "error":
                self.message = "Erreur : " + msg.get("message", "")

    def place_current_ship(self, row, col):
        current = self.current_ship_config()
        if current is None:
            return
        name, size = current
        ship = Ship(name, size)
        if name == "Sous-marin T" and self.current_orientation not in SUBMARINE_ORIENTATIONS:
            self.current_orientation = "haut"
        if name != "Sous-marin T" and self.current_orientation not in ("H", "V"):
            self.current_orientation = "H"
        if self.player_board.place_ship(ship, row, col, self.current_orientation):
            self.selected_ship_name = None
            nxt = self.current_ship_config()
            if nxt is None:
                self.message = "Tous les bateaux sont prêts. Clique sur un bateau pour le déplacer si besoin."
            else:
                self.message = f"{ship_label(name)} placé."
        else:
            self.message = "Placement invalide."

    def pick_ship_to_move(self, row, col):
        ship = self.player_board.remove_ship_at(row, col)
        if ship is None:
            return False
        self.selected_ship_name = ship.name
        self.set_orientation_from_ship(ship)
        self.message = f"Déplacement de {ship_label(ship.name)} : clique une nouvelle case."
        return True

    def send_layout(self):
        if self.placement_locked:
            self.message = "Placement déjà validé."
            return

        if len(self.player_board.ships) != len(SHIPS_CONFIG):
            self.message = "Il faut placer les 5 bateaux avant validation."
            return

        self.network.send({"type": "place_ships", "layout": layout_from_board(self.player_board)})
        self.placement_locked = True
        self.selected_ship_name = None
        self.message = "En attente de l'autre joueur..."

    def auto_place(self):
        self.player_board.auto_place_all()
        self.selected_ship_name = None
        self.message = "Placement auto généré. Tu peux déplacer n'importe quel bateau avant validation."

    def shoot(self, row, col):
        self.network.send({"type": "shoot", "row": row, "col": col})

    def request_rematch(self):
        if self.player_id in self.rematch_requests:
            return
        self.network.send({"type": "rematch_request"})
        self.rematch_requests.add(self.player_id)
        self.message = "Proposition de revanche envoyée."

    def get_status_rows(self, board):
        rows = []
        ships_by_name = {ship.name: ship for ship in board.ships}
        for ship_name, _ in SHIPS_CONFIG:
            ship = ships_by_name.get(ship_name)
            status = "COULÉ" if ship is not None and ship.is_sunk() else "OK"
            color = RED if status == "COULÉ" else GREEN
            rows.append((ship_label(ship_name), status, color))
        return rows

    def draw_status_panel(self, rect, title, board):
        f = self.fonts()
        draw_glass_panel(self.screen, rect, radius=22)
        draw_text(self.screen, title, f["panel_title"], WHITE, topleft=(rect.x + 18, rect.y + 12))
        header_y = rect.y + 58
        pygame.draw.line(self.screen, (40, 70, 110), (rect.x + 14, header_y), (rect.right - 14, header_y), 1)
        body_top = header_y + 8
        body_h = rect.bottom - body_top - 10
        row_h = max(22, body_h // len(SHIPS_CONFIG))
        y = body_top
        for i, (name, status, color) in enumerate(self.get_status_rows(board)):
            if i % 2 == 0:
                stripe = pygame.Rect(rect.x + 10, y - 1, rect.width - 20, row_h)
                pygame.draw.rect(self.screen, (12, 24, 40), stripe, border_radius=8)
            draw_text(self.screen, name, f["panel_row"], WHITE, topleft=(rect.x + 18, y + 2))
            status_img = f["panel_status"].render(status, True, color)
            self.screen.blit(status_img, status_img.get_rect(topright=(rect.right - 18, y + 1)))
            y += row_h

    def draw_board(self, board, x, y, reveal_ships=False):
        label_font = self.fonts()["small"]
        grid_rect = pygame.Rect(x - 8, y - 8, self.board_px + 16, self.board_px + 16)
        pygame.draw.rect(self.screen, NAVY, grid_rect, border_radius=14)
        pygame.draw.rect(self.screen, WHITE, grid_rect, 2, border_radius=14)
        for c in range(GRID_SIZE):
            draw_text(self.screen, LETTERS[c], label_font, WHITE, center=(x + c * self.cell_size + self.cell_size // 2, y - max(20, self.cell_size // 2)))
        for r in range(GRID_SIZE):
            draw_text(self.screen, str(r + 1), label_font, WHITE, center=(x - max(18, self.cell_size // 2), y + r * self.cell_size + self.cell_size // 2))
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                px, py = self.board_to_pixel(x, y, r, c)
                rect = pygame.Rect(px, py, self.cell_size, self.cell_size)
                pygame.draw.rect(self.screen, BLUE, rect)
                pygame.draw.rect(self.screen, GRID_LINE, rect, 1)
                ship = board.ship_at(r, c)
                if reveal_ships and ship is not None:
                    inner = rect.inflate(-max(4, self.cell_size // 8), -max(4, self.cell_size // 8))
                    fill = SHIP_COLOR
                    border = SHIP_BORDER
                    if self.state == "placement" and ship.name == self.selected_ship_name:
                        fill = (145, 130, 85)
                        border = GOLD
                    pygame.draw.rect(self.screen, fill, inner, border_radius=max(6, self.cell_size // 6))
                    pygame.draw.rect(self.screen, border, inner, 2, border_radius=max(6, self.cell_size // 6))
                if (r, c) in board.shots:
                    if board.shots[(r, c)] == "miss":
                        pygame.draw.circle(self.screen, MISS, rect.center, max(5, self.cell_size // 7), 2)
                    else:
                        pygame.draw.circle(self.screen, HIT_FILL, rect.center, max(8, self.cell_size // 4))
                        pygame.draw.circle(self.screen, HIT_DARK, rect.center, max(8, self.cell_size // 4), 2)
        for ship in board.ships:
            if ship.is_sunk() and ship.positions:
                centers = {
                    (r, c): (
                        self.board_to_pixel(x, y, r, c)[0] + self.cell_size // 2,
                        self.board_to_pixel(x, y, r, c)[1] + self.cell_size // 2,
                    )
                    for (r, c) in ship.positions
                }
                for (r, c), center in centers.items():
                    for dr, dc in ((1, 0), (0, 1)):
                        neighbor = (r + dr, c + dc)
                        if neighbor in centers:
                            pygame.draw.line(self.screen, SUNK_FILL, center, centers[neighbor], max(12, self.cell_size // 2))
                            pygame.draw.line(self.screen, SUNK_BORDER, center, centers[neighbor], max(3, self.cell_size // 10))
                for r, c in ship.positions:
                    px, py = self.board_to_pixel(x, y, r, c)
                    m = max(4, self.cell_size // 8)
                    sunk_rect = pygame.Rect(px + m, py + m, self.cell_size - 2 * m, self.cell_size - 2 * m)
                    pygame.draw.rect(self.screen, SUNK_FILL, sunk_rect, border_radius=max(6, self.cell_size // 6))
                    pygame.draw.rect(self.screen, SUNK_BORDER, sunk_rect, 2, border_radius=max(6, self.cell_size // 6))

    def draw_ship_preview(self):
        if self.hover_cell is None:
            return
        current = self.current_ship_config()
        if current is None:
            return
        name, size = current
        row, col = self.hover_cell
        if name == "Sous-marin T":
            valid, positions = self.player_board.can_place_submarine(row, col, self.current_orientation if self.current_orientation in SUBMARINE_ORIENTATIONS else "haut")
        else:
            valid, positions = self.player_board.can_place_ship(row, col, size, self.current_orientation if self.current_orientation in ("H", "V") else "H")
        color = (120, 220, 160) if valid else (255, 160, 160)
        for r, c in positions:
            px, py = self.board_to_pixel(self.left_grid_x, self.grid_y, r, c)
            rect = pygame.Rect(px + 3, py + 3, self.cell_size - 6, self.cell_size - 6)
            pygame.draw.rect(self.screen, color, rect, border_radius=max(6, self.cell_size // 6))
            pygame.draw.rect(self.screen, BLACK, rect, 1, border_radius=max(6, self.cell_size // 6))

    def draw_title_bar(self, subtitle):
        f = self.fonts()
        w, _ = self.screen.get_size()
        panel = pygame.Surface((w, self.top_bar_h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (6, 12, 22, 220), (0, 0, w, self.top_bar_h))
        self.screen.blit(panel, (0, 0))
        draw_text(self.screen, "NAVAL STRIKE ONLINE", f["title"], WHITE, center=(w // 2, int(self.top_bar_h * 0.34)))
        draw_text(self.screen, subtitle, f["medium"], CYAN, center=(w // 2, int(self.top_bar_h * 0.76)))
        self.sync_btn.draw(self.screen, f["small"], pygame.mouse.get_pos())

    def draw_message_bar(self):
        f = self.fonts()
        draw_glass_panel(self.screen, self.message_rect, radius=12)
        draw_text(self.screen, self.message, f["small"], WHITE, center=self.message_rect.center)

    def draw_connecting(self):
        f = self.fonts()
        self.draw_title_bar("Connexion")
        self.draw_message_bar()
        w, h = self.screen.get_size()
        panel = pygame.Rect(w // 2 - max(220, int(w * 0.22)), h // 2 - 110, max(440, int(w * 0.44)), 220)
        draw_glass_panel(self.screen, panel, radius=24)
        draw_text(self.screen, "Connexion au serveur...", f["big"], WHITE, center=panel.center)

    def draw_placement(self):
        f = self.fonts()
        self.draw_title_bar(f"Placement - {self.local_name}")
        self.draw_message_bar()
        self.draw_board(self.player_board, self.left_grid_x, self.grid_y, reveal_ships=True)
        panel = self.placement_panel_rect
        draw_glass_panel(self.screen, panel, radius=22)
        current = self.current_ship_config()
        draw_text(self.screen, "Placement", f["small"], LIGHT_BLUE, topleft=(panel.x + 24, panel.y + 18))
        if current is not None:
            if self.selected_ship_name is not None:
                title = f"Déplacer : {ship_label(current[0])}"
            else:
                title = f"Bateau à placer : {ship_label(current[0])}"
            draw_wrapped_text(self.screen, title, f["big"], WHITE, pygame.Rect(panel.x + 24, panel.y + 54, panel.width - 48, 96))
            draw_text(self.screen, f"Taille : {current[1]} case(s)", f["medium"], WHITE, topleft=(panel.x + 24, panel.y + 146))
            draw_text(self.screen, f"Orientation : {self.current_orientation}", f["medium"], WHITE, topleft=(panel.x + 24, panel.y + 188))
        else:
            draw_wrapped_text(self.screen, "Tous les bateaux sont prêts.", f["big"], WHITE, pygame.Rect(panel.x + 24, panel.y + 60, panel.width - 48, 110))
            draw_wrapped_text(self.screen, "Tu peux cliquer sur n'importe quel navire pour le déplacer avant validation.", f["medium"], CYAN, pygame.Rect(panel.x + 24, panel.y + 180, panel.width - 48, 92))
        draw_text(self.screen, "R : tourner le bateau", f["small"], WHITE, topleft=(panel.x + 24, panel.bottom - 60))
        draw_text(self.screen, "Clique un bateau déjà placé pour le déplacer", f["small"], WHITE, topleft=(panel.x + 24, panel.bottom - 34))
        editable = not self.placement_locked
        self.place_auto_btn.draw(self.screen, f["small"], pygame.mouse.get_pos(), enabled=editable)
        self.place_send_btn.draw(self.screen, f["small"], pygame.mouse.get_pos(), enabled=editable)
        self.draw_ship_preview()

    def draw_battle(self):
        f = self.fonts()
        subtitle = "À toi de jouer" if self.turn else f"Tour de {self.enemy_name}"
        self.draw_title_bar(subtitle)
        self.draw_message_bar()
        draw_text(self.screen, self.local_name, f["medium"], WHITE, center=(self.left_grid_x + self.board_px // 2, self.grid_y - max(34, self.cell_size)))
        draw_text(self.screen, self.enemy_name, f["medium"], WHITE, center=(self.right_grid_x + self.board_px // 2, self.grid_y - max(34, self.cell_size)))
        self.draw_board(self.player_board, self.left_grid_x, self.grid_y, reveal_ships=True)
        self.draw_board(self.enemy_board, self.right_grid_x, self.grid_y, reveal_ships=False)
        self.draw_status_panel(self.left_status_rect, "Bateaux restants", self.player_board)
        self.draw_status_panel(self.right_status_rect, "Flotte ennemie", self.enemy_board)

    def draw_end(self):
        f = self.fonts()
        self.draw_battle()
        w, h = self.screen.get_size()
        panel = pygame.Rect(w // 2 - max(240, int(w * 0.24)), h // 2 - 130, max(480, int(w * 0.48)), 270)
        draw_glass_panel(self.screen, panel, radius=24)
        text = "VICTOIRE" if self.winner == self.player_id else "DÉFAITE"
        color = GREEN if self.winner == self.player_id else RED
        draw_text(self.screen, text, f["big"], color, center=(panel.centerx, panel.y + 74))
        other_requested = any(pid != self.player_id for pid in self.rematch_requests)
        if self.player_id in self.rematch_requests and other_requested:
            info = "Relance acceptée. Retour au placement..."
        elif self.player_id in self.rematch_requests:
            info = "Proposition envoyée. En attente de l'autre joueur..."
        elif other_requested:
            info = f"{self.enemy_name} propose une revanche."
        else:
            info = "Tu peux proposer une revanche."
        draw_text(self.screen, info, f["small"], WHITE, center=(panel.centerx, panel.y + 126))
        button_text = "EN ATTENTE..." if self.player_id in self.rematch_requests else ("ACCEPTER REJOUER" if other_requested else "PROPOSER REJOUER")
        self.rematch_btn.text = button_text
        self.rematch_btn.draw(self.screen, f["small"], pygame.mouse.get_pos(), enabled=self.player_id not in self.rematch_requests)
        draw_text(self.screen, "Ferme la fenêtre pour revenir au menu.", f["small"], WHITE, center=(panel.centerx, panel.y + 210))

    def draw(self):
        draw_vertical_gradient(self.screen, BG_TOP, BG_BOTTOM)
        draw_ocean_overlay(self.screen)
        if self.state == "connecting":
            self.draw_connecting()
        elif self.state == "placement":
            self.draw_placement()
        elif self.state == "battle":
            self.draw_battle()
        elif self.state == "end":
            self.draw_end()

    def handle_event(self, event):
        if event.type == pygame.VIDEORESIZE:
            self.screen = pygame.display.set_mode((max(MIN_W, event.w), max(MIN_H, event.h)), pygame.RESIZABLE)
            self.compute_layout()
            return
        if event.type not in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN, pygame.MOUSEMOTION):
            return
        if event.type == pygame.MOUSEMOTION and self.state == "placement":
            self.hover_cell = self.pixel_to_board(event.pos[0], event.pos[1], self.left_grid_x, self.grid_y)
            return
        if event.type == pygame.KEYDOWN and self.state == "placement":
            current = self.current_ship_config()
            if current is None:
                return
            if event.key == pygame.K_r:
                if current[0] == "Sous-marin T":
                    idx = SUBMARINE_ORIENTATIONS.index(self.current_orientation) if self.current_orientation in SUBMARINE_ORIENTATIONS else 0
                    self.current_orientation = SUBMARINE_ORIENTATIONS[(idx + 1) % len(SUBMARINE_ORIENTATIONS)]
                else:
                    self.current_orientation = "V" if self.current_orientation == "H" else "H"
            return
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.sync_btn.is_clicked(event.pos):
                self.network.send({"type": "sync_request"})
                self.message = "Synchronisation demandée..."
                return
            if self.state == "placement":
                if self.placement_locked:
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self.sync_btn.is_clicked(event.pos):
                            self.network.send({"type": "sync_request"})
                        else:
                            self.message = "Placement déjà validé. En attente de l'autre joueur..."
                    return
                if self.place_auto_btn.is_clicked(event.pos):
                    self.auto_place()
                    return
                if self.place_send_btn.is_clicked(event.pos):
                    self.send_layout()
                    return
                cell = self.pixel_to_board(event.pos[0], event.pos[1], self.left_grid_x, self.grid_y)
                if cell is not None:
                    ship = self.player_board.ship_at(*cell)
                    if ship is not None:
                        self.pick_ship_to_move(*cell)
                    else:
                        self.place_current_ship(*cell)
            elif self.state == "battle" and self.turn:
                cell = self.pixel_to_board(event.pos[0], event.pos[1], self.right_grid_x, self.grid_y)
                if cell is not None:
                    self.shoot(*cell)
            elif self.state == "end":
                if self.rematch_btn.is_clicked(event.pos):
                    self.request_rematch()

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
