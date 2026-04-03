import pygame
import random
import sys

# ==========================================================
# CONFIGURATION
# ==========================================================
pygame.init()

WIDTH, HEIGHT = 1200, 860
FPS = 60

GRID_SIZE = 10
CELL_SIZE = 42

LEFT_GRID_X = 90
RIGHT_GRID_X = 650
GRID_Y = 200

HUD_HEIGHT = 110

# =========================
# PALETTE VISUELLE
# =========================
BG_TOP = (6, 18, 35)
BG_BOTTOM = (12, 52, 95)

WHITE = (235, 240, 245)
BLACK = (8, 10, 14)

NAVY_DARK = (10, 20, 35)
NAVY = (18, 35, 60)
NAVY_LIGHT = (40, 78, 125)

CYAN = (120, 190, 220)
CYAN_SOFT = (90, 150, 190)
LIGHT_BLUE = (150, 205, 235)

GRID_DARK = (30, 55, 80)
GRID_SOFT = (50, 80, 110)
GRID_LINE = (70, 105, 140)

BLUE = (24, 82, 135)

SHIP_COLOR = (95, 110, 125)
SHIP_BORDER = (60, 75, 90)

HIT = (215, 70, 70)
MISS = (190, 205, 220)
HIT_FILL = (220, 85, 85)
HIT_DARK = (120, 35, 35)
SUNK_FILL = (120, 45, 45)
SUNK_BORDER = (170, 70, 70)

GREEN = (60, 190, 110)
RED = (200, 70, 70)

PANEL_FILL = (8, 14, 24, 210)
PANEL_BORDER = (90, 130, 170, 70)

BUTTON_IDLE = (52, 76, 116)
BUTTON_HOVER = (72, 104, 150)
BUTTON_BORDER = (180, 205, 230)

# Bateaux classiques
SHIPS_CONFIG = [
    ("Porte-avion", 5),
    ("Cuirassé", 4),
    ("Croiseur", 3),
    ("Sous-marin T", 4),
    ("Torpilleur", 2),
]

LETTERS = "ABCDEFGHIJ"
SUBMARINE_ORIENTATIONS = ["haut", "bas", "gauche", "droite"]

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Naval Strike")
clock = pygame.time.Clock()

FONT_SMALL = pygame.font.SysFont("arial", 20)
FONT_MEDIUM = pygame.font.SysFont("arial", 28)
FONT_BIG = pygame.font.SysFont("arial", 44)
FONT_TITLE = pygame.font.SysFont("arial", 64)


# ==========================================================
# UTILITAIRES
# ==========================================================
def draw_vertical_gradient(surface, top_color, bottom_color):
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        r = int(top_color[0] * (1 - ratio) + bottom_color[0] * ratio)
        g = int(top_color[1] * (1 - ratio) + bottom_color[1] * ratio)
        b = int(top_color[2] * (1 - ratio) + bottom_color[2] * ratio)
        pygame.draw.line(surface, (r, g, b), (0, y), (WIDTH, y))

    # léger glow en haut
    for i in range(120):
        alpha = max(0, 40 - i // 3)
        line_color = (255, 255, 255, alpha)
        overlay = pygame.Surface((WIDTH, 1), pygame.SRCALPHA)
        overlay.fill(line_color)
        surface.blit(overlay, (0, i))

def draw_ocean_overlay(surface):
    # lignes horizontales très discrètes
    for y in range(0, HEIGHT, 48):
        pygame.draw.line(surface, GRID_SOFT, (0, y), (WIDTH, y), 1)

    # lignes verticales très discrètes
    for x in range(0, WIDTH, 80):
        pygame.draw.line(surface, GRID_DARK, (x, 0), (x, HEIGHT), 1)


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


def board_to_pixel(board_x, board_y, row, col):
    x = board_x + col * CELL_SIZE
    y = board_y + row * CELL_SIZE
    return x, y


def pixel_to_board(mouse_x, mouse_y, board_x, board_y):
    rel_x = mouse_x - board_x
    rel_y = mouse_y - board_y

    if rel_x < 0 or rel_y < 0:
        return None

    col = rel_x // CELL_SIZE
    row = rel_y // CELL_SIZE

    if 0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE:
        return int(row), int(col)
    return None


# ==========================================================
# BOUTON
# ==========================================================
class Button:
    def __init__(self, text, rect, color_idle=(70, 90, 130), color_hover=(100, 130, 180)):
        self.text = text
        self.rect = pygame.Rect(rect)
        self.color_idle = color_idle
        self.color_hover = color_hover

    def draw(self, surface):
        mouse = pygame.mouse.get_pos()
        hovered = self.rect.collidepoint(mouse)
        color = self.color_hover if hovered else self.color_idle

        # ombre
        shadow = self.rect.move(0, 4)
        pygame.draw.rect(surface, (10, 15, 25), shadow, border_radius=14)

        # fond bouton
        pygame.draw.rect(surface, color, self.rect, border_radius=14)
        pygame.draw.rect(surface, BUTTON_BORDER, self.rect, 2, border_radius=14)

        # reflet léger et propre
        shine = pygame.Rect(self.rect.x + 12, self.rect.y + 8, self.rect.width - 24, 8)
        shine_surface = pygame.Surface((shine.width, shine.height), pygame.SRCALPHA)
        pygame.draw.rect(shine_surface, (255, 255, 255, 35), (0, 0, shine.width, shine.height), border_radius=6)
        surface.blit(shine_surface, shine.topleft)

        draw_text(surface, self.text, FONT_MEDIUM, WHITE, center=self.rect.center)

    def is_clicked(self, pos):
        return self.rect.collidepoint(pos)

# ==========================================================
# SHIP
# ==========================================================
class Ship:
    def __init__(self, name, size):
        self.name = name
        self.size = size
        self.positions = []
        self.hits = set()

    def place(self, positions):
        self.positions = positions
        self.hits = set()

    def is_sunk(self):
        return len(self.hits) == len(self.positions)

    def register_hit(self, pos):
        if pos in self.positions:
            self.hits.add(pos)


# ==========================================================
# BOARD
# ==========================================================
class Board:
    def __init__(self):
        self.ships = []
        self.shots = {}  # (r,c) -> "hit" / "miss"

    def reset(self):
        self.ships = []
        self.shots = {}

    def inside(self, row, col):
        return 0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE

    def ship_at(self, row, col):
        for ship in self.ships:
            if (row, col) in ship.positions:
                return ship
        return None

    def can_place_ship(self, row, col, size, orientation):
        positions = []

        for i in range(size):
            r = row + i if orientation == "V" else row
            c = col + i if orientation == "H" else col

            if not self.inside(r, c):
                return False, []

            if self.ship_at(r, c) is not None:
                return False, []

            positions.append((r, c))

        return True, positions
    
    def can_place_submarine(self, row, col, orientation):
        if orientation == "haut":
            positions = [(row, col-1), (row, col), (row, col+1), (row-1, col)]
        elif orientation == "bas":
            positions = [(row, col-1), (row, col), (row, col+1), (row+1, col)]
        elif orientation == "gauche":
            positions = [(row-1, col), (row, col), (row+1, col), (row, col-1)]
        elif orientation == "droite":
            positions = [(row-1, col), (row, col), (row+1, col), (row, col+1)]
        else:
            return False, []

        for r, c in positions:
            if not self.inside(r, c):
                return False, []
            if self.ship_at(r, c) is not None:
                return False, []

        return True, positions
    
    def place_ship(self, ship, row, col, orientation):
        if ship.name == "Sous-marin T":
            valid, positions = self.can_place_submarine(row, col, orientation)
        else:
            valid, positions = self.can_place_ship(row, col, ship.size, orientation)

        if not valid:
            return False

        if len(positions) != len(set(positions)):
            return False  # sécurité anti-bug

        ship.place(positions)
        self.ships.append(ship)
        return True
    
    def auto_place_all(self):
        self.reset()

        for name, size in SHIPS_CONFIG:
            placed = False
            while not placed:
                ship = Ship(name, size)
                row = random.randint(0, GRID_SIZE - 1)
                col = random.randint(0, GRID_SIZE - 1)

                if name == "Sous-marin T":
                    orientation = random.choice(SUBMARINE_ORIENTATIONS)
                else:
                    orientation = random.choice(["H", "V"])

                placed = self.place_ship(ship, row, col, orientation)

    def receive_shot(self, row, col):
        if (row, col) in self.shots:
            return "already", None

        ship = self.ship_at(row, col)
        if ship is not None:
            self.shots[(row, col)] = "hit"
            ship.register_hit((row, col))
            if ship.is_sunk():
                return "sunk", ship
            return "hit", ship

        self.shots[(row, col)] = "miss"
        return "miss", None

    def all_sunk(self):
        return len(self.ships) > 0 and all(ship.is_sunk() for ship in self.ships)


# ==========================================================
# BOT IA
# ==========================================================
class BotAI:
    def __init__(self):
        self.reset()

    def reset(self):
        self.parity_cells = [(r, c) for r in range(GRID_SIZE) for c in range(GRID_SIZE) if (r + c) % 2 == 0]
        random.shuffle(self.parity_cells)

        self.fallback_cells = [(r, c) for r in range(GRID_SIZE) for c in range(GRID_SIZE) if (r + c) % 2 == 1]
        random.shuffle(self.fallback_cells)

    def valid_unknown(self, board, row, col):
        return board.inside(row, col) and (row, col) not in board.shots

    def neighbors4(self, row, col):
        return [(row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)]

    def get_unsunk_hit_cells(self, board):
        """
        Retourne toutes les cases touchées qui appartiennent à un bateau non coulé.
        On relit directement l'état réel du plateau.
        """
        hits = []

        for ship in board.ships:
            if not ship.is_sunk():
                for pos in ship.hits:
                    hits.append(pos)

        return hits

    def grouped_hits(self, hit_cells):
        """
        Regroupe les touches adjacentes en composantes connexes.
        """
        remaining = set(hit_cells)
        groups = []

        while remaining:
            start = remaining.pop()
            stack = [start]
            group = [start]

            while stack:
                r, c = stack.pop()
                for nr, nc in self.neighbors4(r, c):
                    if (nr, nc) in remaining:
                        remaining.remove((nr, nc))
                        stack.append((nr, nc))
                        group.append((nr, nc))

            groups.append(group)

        return groups

    def infer_axis(self, group):
        if len(group) < 2:
            return None

        rows = {r for r, c in group}
        cols = {c for r, c in group}

        if len(rows) == 1:
            return "H"
        if len(cols) == 1:
            return "V"
        return "MIXED"

    def candidate_shots_for_group(self, board, group):
        axis = self.infer_axis(group)

        # fonction locale : explorer tout autour du groupe
        def around_group():
            candidates = []
            for r, c in group:
                for nr, nc in self.neighbors4(r, c):
                    if self.valid_unknown(board, nr, nc) and (nr, nc) not in candidates:
                        candidates.append((nr, nc))
            return candidates

        # une seule touche : on teste les 4 voisins
        if axis is None:
            return around_group()

        # bateau horizontal
        if axis == "H":
            row = group[0][0]
            cols = sorted(c for r, c in group)

            candidates = []
            left = (row, cols[0] - 1)
            right = (row, cols[-1] + 1)

            if self.valid_unknown(board, left[0], left[1]):
                candidates.append(left)
            if self.valid_unknown(board, right[0], right[1]):
                candidates.append(right)

            # si l'axe semble bloqué, on explore autour du groupe
            if candidates:
                return candidates
            return around_group()

        # bateau vertical
        if axis == "V":
            col = group[0][1]
            rows = sorted(r for r, c in group)

            candidates = []
            up = (rows[0] - 1, col)
            down = (rows[-1] + 1, col)

            if self.valid_unknown(board, up[0], up[1]):
                candidates.append(up)
            if self.valid_unknown(board, down[0], down[1]):
                candidates.append(down)

            # si l'axe semble bloqué, on explore autour du groupe
            if candidates:
                return candidates
            return around_group()

        # cas mixte : sous-marin T ou plusieurs bateaux collés
        return around_group()

    def choose_shot(self, board):
        unsunk_hits = self.get_unsunk_hit_cells(board)

        # priorité absolue : finir les bateaux déjà touchés
        if unsunk_hits:
            groups = self.grouped_hits(unsunk_hits)

            # on traite d'abord le plus gros groupe
            groups.sort(key=lambda g: len(g), reverse=True)

            for group in groups:
                candidates = self.candidate_shots_for_group(board, group)
                if candidates:
                    return candidates[0]

        # sinon recherche classique
        while self.parity_cells:
            pos = self.parity_cells.pop()
            if pos not in board.shots:
                return pos

        while self.fallback_cells:
            pos = self.fallback_cells.pop()
            if pos not in board.shots:
                return pos

        return None

    def process_result(self, board, row, col, result, sunk_ship):
        # plus besoin de mémoire interne spéciale :
        # l'IA relit directement le board à chaque tour
        pass

# ==========================================================
# GAME
# ==========================================================
class NavalStrikeGame:
    def __init__(self):
        self.player_board = Board()
        self.bot_board = Board()
        self.bot_ai = BotAI()

        self.state = "menu"  # menu / mode_select / rules / placement / battle / end
        self.message = "Bienvenue dans Naval Strike."
        self.turn = "player"
        self.winner = None

        self.game_mode = "vs_ai"   # "vs_ai" ou "vs_local"
        self.current_placer = 1
        self.turn = "player"
        self.transition_reason = None   # "placement_p2" ou "next_turn"

        self.current_ship_index = 0
        self.current_orientation = "H"
        self.hover_cell = None

        self.bot_action_time = 0
        self.bot_delay = 700  # ms
        self.pending_transition = False
        self.pending_transition_time = 0
        self.pending_next_turn = None

        self.menu_play = Button("JOUER", (WIDTH // 2 - 140, 260, 280, 60))
        self.menu_rules = Button("RÈGLES", (WIDTH // 2 - 140, 340, 280, 60))
        self.menu_quit = Button("QUITTER", (WIDTH // 2 - 140, 420, 280, 60))
        self.mode_ai = Button("1 VS IA", (WIDTH // 2 - 160, 320, 320, 60))
        self.mode_local = Button("1 VS 1 LOCAL", (WIDTH // 2 - 160, 400, 320, 60))
        self.mode_back = Button("RETOUR", (WIDTH // 2 - 160, 480, 320, 60))

        self.place_auto_btn = Button("PLACEMENT AUTO", (LEFT_GRID_X, 645, 240, 46), (70, 120, 90), (90, 160, 110))
        self.place_reset_btn = Button("RÉINITIALISER", (LEFT_GRID_X + 260, 645, 220, 46), (130, 70, 70), (170, 90, 90))

        self.end_replay = Button("REJOUER", (WIDTH // 2 - 150, 430, 300, 58))
        self.end_menu = Button("MENU", (WIDTH // 2 - 150, 505, 300, 58))

        self.reset_full_game()

    # ======================================================
    # RESET / CONFIG
    # ======================================================
    def reset_full_game(self):
        self.player_board.reset()
        self.bot_board.reset()

        if self.game_mode == "vs_ai":
            self.bot_board.auto_place_all()

        self.bot_ai.reset()

        self.current_ship_index = 0
        self.current_orientation = "H"
        self.hover_cell = None

        self.turn = "player"
        self.winner = None
        self.bot_action_time = 0
        self.pending_transition = False
        self.pending_transition_time = 0
        self.pending_next_turn = None
        self.current_placer = 1
        self.transition_reason = None

        self.message = "Place ton Porte-avion (5 cases)."
    
    def start_vs_ai(self):
        self.game_mode = "vs_ai"
        self.reset_full_game()
        self.state = "placement"
        self.message = "Place ton Porte-avion (5 cases)."

    def start_vs_local(self):
        self.game_mode = "vs_local"
        self.reset_full_game()
        self.state = "placement"
        self.message = "Joueur 1 : place ton Porte-avion (5 cases)."

    def start_placement(self):
        self.reset_full_game()
        self.state = "placement"

    def start_battle(self):
        self.state = "battle"
        self.message = "La bataille commence ! À toi de tirer."

    # ======================================================
    # SHIPS / PLACEMENT
    # ======================================================
    def current_ship_config(self):
        if self.current_ship_index >= len(SHIPS_CONFIG):
            return None
        return SHIPS_CONFIG[self.current_ship_index]

    def place_current_ship(self, row, col):
        config = self.current_ship_config()
        if config is None:
            return

        name, size = config
        ship = Ship(name, size)

        if name == "Sous-marin T":
            if self.current_orientation not in SUBMARINE_ORIENTATIONS:
                self.current_orientation = "haut"
        else:
            if self.current_orientation not in ("H", "V"):
                self.current_orientation = "H"

        active_board = self.player_board if self.current_placer == 1 else self.bot_board

        if active_board.place_ship(ship, row, col, self.current_orientation):
            self.current_ship_index += 1

            next_cfg = self.current_ship_config()
            if next_cfg is None:
                if self.game_mode == "vs_ai":
                    self.start_battle()
                else:
                    if self.current_placer == 1:
                        self.current_placer = 2
                        self.current_ship_index = 0
                        self.current_orientation = "H"
                        self.hover_cell = None
                        self.transition_reason = "placement_p2"
                        self.state = "transition"
                        self.message = "Joueur 2, prépare-toi."
                    else:
                        self.turn = "player1"
                        self.transition_reason = "next_turn"
                        self.state = "transition"
                        self.message = "Placement terminé. Joueur 1, prépare-toi."
            else:
                if self.game_mode == "vs_local":
                    self.message = f"Joueur {self.current_placer} : place maintenant {next_cfg[0]} ({next_cfg[1]} cases)."
                else:
                    self.message = f"{name} placé. Place maintenant {next_cfg[0]} ({next_cfg[1]} cases)."
        else:
            self.message = "Placement invalide : hors grille ou chevauchement."

    def auto_place_player(self):
        active_board = self.player_board if self.current_placer == 1 else self.bot_board
        active_board.auto_place_all()
        self.current_ship_index = len(SHIPS_CONFIG)

        if self.game_mode == "vs_ai":
            self.start_battle()
        else:
            if self.current_placer == 1:
                self.current_placer = 2
                self.current_ship_index = 0
                self.current_orientation = "H"
                self.hover_cell = None
                self.transition_reason = "placement_p2"
                self.state = "transition"
                self.message = "Joueur 2, prépare-toi."
            else:
                self.turn = "player1"
                self.transition_reason = "next_turn"
                self.state = "transition"
                self.message = "Placement terminé. Joueur 1, prépare-toi."

    def reset_player_placement(self):
        active_board = self.player_board if self.current_placer == 1 else self.bot_board
        active_board.reset()
        self.current_ship_index = 0
        self.current_orientation = "H"

        if self.game_mode == "vs_local":
            self.message = f"Placement réinitialisé. Joueur {self.current_placer}, place ton Porte-avion."
        else:
            self.message = "Placement réinitialisé. Place ton Porte-avion."

    # ======================================================
    # TIRS
    # ======================================================
    def player_shoot(self, row, col):
        result, ship = self.bot_board.receive_shot(row, col)

        if result == "already":
            self.message = "Tu as déjà tiré ici."
            return

        if result == "miss":
            self.message = f"Tir en {LETTERS[col]}{row+1} : raté."
            self.turn = "bot"
            self.bot_action_time = pygame.time.get_ticks()

        elif result == "hit":
            self.message = f"Tir en {LETTERS[col]}{row+1} : touché ! Tu rejoues."
            self.turn = "player"

        elif result == "sunk":
            self.message = f"Tir en {LETTERS[col]}{row+1} : {ship.name} coulé ! Tu rejoues."
            self.turn = "player"

        if self.bot_board.all_sunk():
            self.winner = "player"
            self.state = "end"
            self.message = "Victoire ! Toute la flotte ennemie a été détruite."
    
    def player1_shoot(self, row, col):
        result, ship = self.bot_board.receive_shot(row, col)

        if result == "already":
            self.message = "Joueur 1 : case déjà visée."
            return

        if result == "miss":
            self.message = f"Joueur 1 tire en {LETTERS[col]}{row+1} : raté."
            self.pending_next_turn = "player2"
            self.transition_reason = "next_turn"
            self.pending_transition = True
            self.pending_transition_time = pygame.time.get_ticks()
        elif result == "hit":
            self.message = f"Joueur 1 tire en {LETTERS[col]}{row+1} : touché ! Rejoue."
        elif result == "sunk":
            self.message = f"Joueur 1 tire en {LETTERS[col]}{row+1} : {ship.name} coulé ! Rejoue."

        if self.bot_board.all_sunk():
            self.winner = "player1"
            self.state = "end"
            self.message = "Victoire du Joueur 1 !"

    def player2_shoot(self, row, col):
        result, ship = self.player_board.receive_shot(row, col)

        if result == "already":
            self.message = "Joueur 2 : case déjà visée."
            return

        if result == "miss":
            self.message = f"Joueur 2 tire en {LETTERS[col]}{row+1} : raté."
            self.pending_next_turn = "player1"
            self.transition_reason = "next_turn"
            self.pending_transition = True
            self.pending_transition_time = pygame.time.get_ticks()
        elif result == "hit":
            self.message = f"Joueur 2 tire en {LETTERS[col]}{row+1} : touché ! Rejoue."
        elif result == "sunk":
            self.message = f"Joueur 2 tire en {LETTERS[col]}{row+1} : {ship.name} coulé ! Rejoue."

        if self.player_board.all_sunk():
            self.winner = "player2"
            self.state = "end"
            self.message = "Victoire du Joueur 2 !"

    def bot_shoot(self):
        choice = self.bot_ai.choose_shot(self.player_board)
        if choice is None:
            return

        row, col = choice
        result, ship = self.player_board.receive_shot(row, col)
        self.bot_ai.process_result(self.player_board, row, col, result, ship)

        if result == "miss":
            self.message = f"L'ordinateur tire en {LETTERS[col]}{row+1} : raté. À toi."
            self.turn = "player"

        elif result == "hit":
            self.message = f"L'ordinateur tire en {LETTERS[col]}{row+1} : touché !"
            self.turn = "bot"
            self.bot_action_time = pygame.time.get_ticks()

        elif result == "sunk":
            self.message = f"L'ordinateur tire en {LETTERS[col]}{row+1} : {ship.name} coulé !"
            self.turn = "bot"
            self.bot_action_time = pygame.time.get_ticks()

        if self.player_board.all_sunk():
            self.winner = "bot"
            self.state = "end"
            self.message = "Défaite... Ta flotte a été détruite."

    # ======================================================
    # UPDATE
    # ======================================================
    def update(self):
        now = pygame.time.get_ticks()

        if self.state == "battle" and self.game_mode == "vs_ai" and self.turn == "bot":
            if now - self.bot_action_time >= self.bot_delay:
                self.bot_shoot()

        if self.state == "battle" and self.game_mode == "vs_local" and self.pending_transition:
            if now - self.pending_transition_time >= 1000:
                self.pending_transition = False
                if self.pending_next_turn is not None:
                    self.turn = self.pending_next_turn
                    self.pending_next_turn = None
                self.state = "transition"

    # ======================================================
    # INPUT
    # ======================================================
    def handle_event(self, event):
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        if self.state == "menu":
            self.handle_menu_event(event)
        elif self.state == "mode_select":
            self.handle_mode_select_event(event)
        elif self.state == "rules":
            self.handle_rules_event(event)
        elif self.state == "placement":
            self.handle_placement_event(event)
        elif self.state == "battle":
            self.handle_battle_event(event)
        elif self.state == "transition":
            self.handle_transition_event(event)
        elif self.state == "end":
            self.handle_end_event(event)

    def handle_menu_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.menu_play.is_clicked(event.pos):
                self.state = "mode_select"
            elif self.menu_rules.is_clicked(event.pos):
                self.state = "rules"
            elif self.menu_quit.is_clicked(event.pos):
                pygame.quit()
                sys.exit()

    def handle_mode_select_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.state = "menu"

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.mode_ai.is_clicked(event.pos):
                self.start_vs_ai()

            elif self.mode_local.is_clicked(event.pos):
                self.start_vs_local()

            elif self.mode_back.is_clicked(event.pos):
                self.state = "menu"

    def handle_rules_event(self, event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
            self.state = "menu"

        if event.type == pygame.MOUSEBUTTONDOWN:
            self.state = "menu"

    def handle_placement_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.state = "menu"
            elif event.key == pygame.K_r:
                current = self.current_ship_config()
                if current is not None:
                    ship_name, _ = current
                    if ship_name == "Sous-marin T":
                        if self.current_orientation not in SUBMARINE_ORIENTATIONS:
                            self.current_orientation = "haut"
                        else:
                            i = SUBMARINE_ORIENTATIONS.index(self.current_orientation)
                            self.current_orientation = SUBMARINE_ORIENTATIONS[(i + 1) % 4]
                    else:
                        self.current_orientation = "V" if self.current_orientation == "H" else "H"

        elif event.type == pygame.MOUSEMOTION:
            self.hover_cell = pixel_to_board(event.pos[0], event.pos[1], LEFT_GRID_X, GRID_Y)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.place_auto_btn.is_clicked(event.pos):
                self.auto_place_player()
                return

            if self.place_reset_btn.is_clicked(event.pos):
                self.reset_player_placement()
                return

            cell = pixel_to_board(event.pos[0], event.pos[1], LEFT_GRID_X, GRID_Y)
            if cell is not None and self.current_ship_index < len(SHIPS_CONFIG):
                self.place_current_ship(cell[0], cell[1])

    def handle_battle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.state = "menu"
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.game_mode == "vs_ai":
                if self.turn == "player":
                    cell = pixel_to_board(event.pos[0], event.pos[1], RIGHT_GRID_X, GRID_Y)
                    if cell is not None:
                        self.player_shoot(cell[0], cell[1])

            else:
                cell = pixel_to_board(event.pos[0], event.pos[1], RIGHT_GRID_X, GRID_Y)
                if cell is not None:
                    if self.turn == "player1":
                        self.player1_shoot(cell[0], cell[1])
                    elif self.turn == "player2":
                        self.player2_shoot(cell[0], cell[1])
    
    def handle_transition_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.state = "menu"
            elif event.key == pygame.K_RETURN:
                if self.transition_reason == "placement_p2":
                    self.state = "placement"
                    self.message = "Joueur 2 : place ton Porte-avion (5 cases)."
                elif self.transition_reason == "next_turn":
                    self.state = "battle"

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.transition_reason == "placement_p2":
                self.state = "placement"
                self.message = "Joueur 2 : place ton Porte-avion (5 cases)."
            elif self.transition_reason == "next_turn":
                self.state = "battle"

    def handle_end_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.end_replay.is_clicked(event.pos):
                self.start_placement()
            elif self.end_menu.is_clicked(event.pos):
                self.state = "menu"

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self.start_placement()
            elif event.key == pygame.K_ESCAPE:
                self.state = "menu"

    # ======================================================
    # DRAW HELPERS
    # ======================================================
    def draw_board(self, surface, board, x, y, reveal_ships=False):
        # fond grille
        grid_rect = pygame.Rect(x - 8, y - 8, GRID_SIZE * CELL_SIZE + 16, GRID_SIZE * CELL_SIZE + 16)
        pygame.draw.rect(surface, NAVY, grid_rect, border_radius=14)
        pygame.draw.rect(surface, WHITE, grid_rect, 2, border_radius=14)

        # coordonnées colonnes
        for c in range(GRID_SIZE):
            draw_text(surface, LETTERS[c], FONT_SMALL, WHITE, center=(x + c * CELL_SIZE + CELL_SIZE // 2, y - 28))

        # coordonnées lignes
        for r in range(GRID_SIZE):
            draw_text(surface, str(r + 1), FONT_SMALL, WHITE, center=(x - 22, y + r * CELL_SIZE + CELL_SIZE // 2))

        # cases
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                px, py = board_to_pixel(x, y, r, c)
                rect = pygame.Rect(px, py, CELL_SIZE, CELL_SIZE)

                pygame.draw.rect(surface, BLUE, rect)
                pygame.draw.rect(surface, GRID_LINE, rect, 1)

                if reveal_ships:
                    ship = board.ship_at(r, c)
                    if ship is not None:
                        inner = rect.inflate(-6, -6)
                        pygame.draw.rect(surface, SHIP_COLOR, inner, border_radius=8)
                        pygame.draw.rect(surface, SHIP_BORDER, inner, 2, border_radius=8)

                if (r, c) in board.shots:
                    if board.shots[(r, c)] == "miss":
                        pygame.draw.circle(surface, MISS, rect.center, 7, 2)

                    elif board.shots[(r, c)] == "hit":
                        pygame.draw.circle(surface, HIT_FILL, rect.center, 10)
                        pygame.draw.circle(surface, HIT_DARK, rect.center, 10, 2)

        # bateaux coulés : cases remplies en rouge sombre
        for ship in board.ships:
            if ship.is_sunk():
                for (r, c) in ship.positions:
                    px, py = board_to_pixel(x, y, r, c)
                    sunk_rect = pygame.Rect(px + 5, py + 5, CELL_SIZE - 10, CELL_SIZE - 10)
                    pygame.draw.rect(surface, SUNK_FILL, sunk_rect, border_radius=8)
                    pygame.draw.rect(surface, SUNK_BORDER, sunk_rect, 2, border_radius=8)

    def draw_ship_preview(self, surface):
        if self.state != "placement" or self.hover_cell is None:
            return
        if self.current_ship_index >= len(SHIPS_CONFIG):
            return

        name, size = SHIPS_CONFIG[self.current_ship_index]
        row, col = self.hover_cell

        if name == "Sous-marin T":
            if self.current_orientation not in SUBMARINE_ORIENTATIONS:
                self.current_orientation = "haut"
            active_board = self.player_board if self.current_placer == 1 else self.bot_board
            valid, positions = active_board.can_place_submarine(row, col, self.current_orientation)
        else:
            if self.current_orientation not in ("H", "V"):
                self.current_orientation = "H"
            active_board = self.player_board if self.current_placer == 1 else self.bot_board
            valid, positions = active_board.can_place_ship(row, col, size, self.current_orientation)

        color = (120, 220, 160) if valid else (255, 160, 160)

        for (r, c) in positions:
            px, py = board_to_pixel(LEFT_GRID_X, GRID_Y, r, c)
            rect = pygame.Rect(px + 3, py + 3, CELL_SIZE - 6, CELL_SIZE - 6)
            pygame.draw.rect(surface, color, rect, border_radius=8)
            pygame.draw.rect(surface, BLACK, rect, 1, border_radius=8)

    # ======================================================
    # DRAW STATES
    # ======================================================
    def draw_title_bar(self, subtitle):
        header = pygame.Rect(0, 0, WIDTH, 120)

        panel = pygame.Surface((WIDTH, 120), pygame.SRCALPHA)
        pygame.draw.rect(panel, (6, 12, 22, 220), (0, 0, WIDTH, 120))
        pygame.draw.line(panel, (70, 100, 130), (0, 118), (WIDTH, 118), 2)

        # glow léger en haut
        for i in range(35):
            alpha = max(0, 20 - i // 2)
            pygame.draw.line(panel, (255, 255, 255, alpha), (0, i), (WIDTH, i))

        screen.blit(panel, (0, 0))

        draw_text(screen, "NAVAL STRIKE", FONT_TITLE, WHITE, center=(WIDTH // 2, 40))
        draw_text(screen, subtitle, FONT_MEDIUM, CYAN, center=(WIDTH // 2, 90))

    def draw_menu(self):
        self.draw_title_bar("Choisis une action")

        center_x = WIDTH // 2

        panel = pygame.Rect(WIDTH // 2 - 250, 180, 500, 400)
        draw_glass_panel(screen, panel, radius=28)

        draw_text(screen, "Commande la flotte", FONT_BIG, WHITE, center=(center_x, 235))
        draw_text(
            screen,
            "Prépare tes navires et détruis la flotte ennemie.",
            FONT_SMALL,
            CYAN,
            center=(center_x, 278)
        )

        # Placement des boutons
        self.menu_play.rect = pygame.Rect(WIDTH // 2 - 160, 315, 320, 60)
        self.menu_rules.rect = pygame.Rect(WIDTH // 2 - 160, 395, 320, 60)
        self.menu_quit.rect = pygame.Rect(WIDTH // 2 - 160, 475, 320, 60)

        self.menu_play.draw(screen)
        self.menu_rules.draw(screen)
        self.menu_quit.draw(screen)
    
    def draw_mode_select(self):
        self.draw_title_bar("Choisis un mode de jeu")

        center_x = WIDTH // 2

        panel = pygame.Rect(WIDTH // 2 - 250, 220, 500, 360)
        draw_glass_panel(screen, panel, radius=28)

        draw_text(screen, "Mode de jeu", FONT_BIG, WHITE, center=(center_x, 280))
        draw_text(
            screen,
            "Sélectionne la façon de jouer.",
            FONT_SMALL,
            CYAN,
            center=(center_x, 320)
        )

        self.mode_ai.rect = pygame.Rect(WIDTH // 2 - 160, 360, 320, 60)
        self.mode_local.rect = pygame.Rect(WIDTH // 2 - 160, 440, 320, 60)
        self.mode_back.rect = pygame.Rect(WIDTH // 2 - 160, 520, 320, 60)

        self.mode_ai.draw(screen)
        self.mode_local.draw(screen)
        self.mode_back.draw(screen)

    def draw_rules(self):
        self.draw_title_bar("Règles du jeu")

        panel = pygame.Rect(120, 150, WIDTH - 240, 470)
        draw_glass_panel(screen, panel, radius=24)

        lines = [
            "• Place tes 5 navires sur la grille de gauche.",
            "• Touche R pour changer l'orientation du bateau à placer.",
            "• Tu peux aussi utiliser le placement automatique.",
            "• Ensuite, tire sur la grille ennemie à droite.",
            "• Si tu touches, tu rejoues.",
            "• Si tu rates, l'ordinateur joue.",
            "• Le premier à détruire toute la flotte adverse gagne.",
            "",
            "Appuie sur Entrée, Espace ou Échap pour revenir au menu."
        ]

        y = 210
        for line in lines:
            draw_text(screen, line, FONT_MEDIUM, WHITE, topleft=(170, y))
            y += 42

    def draw_placement(self):
        if self.game_mode == "vs_local":
            self.draw_title_bar(f"Placement Joueur {self.current_placer}")
        else:
            self.draw_title_bar("Phase de placement")

        active_board = self.player_board if self.current_placer == 1 else self.bot_board
        self.draw_board(screen, active_board, LEFT_GRID_X, GRID_Y, reveal_ships=True)

        # panneau d'instructions
        panel = pygame.Rect(RIGHT_GRID_X - 20, GRID_Y - 10, 410, 300)
        draw_glass_panel(screen, panel, radius=20)

        current = self.current_ship_config()
        if current is not None:
            ship_name, ship_size = current
            draw_text(screen, f"Bateau à placer :", FONT_SMALL, LIGHT_BLUE, topleft=(RIGHT_GRID_X + 20, GRID_Y + 20))
            draw_text(screen, f"{ship_name} ({ship_size} cases)", FONT_BIG, WHITE, topleft=(RIGHT_GRID_X + 20, GRID_Y + 48))
            draw_text(screen, f"Orientation : {self.current_orientation}", FONT_MEDIUM, WHITE, topleft=(RIGHT_GRID_X + 20, GRID_Y + 110))

        draw_text(screen, "R : tourner le bateau", FONT_SMALL, WHITE, topleft=(RIGHT_GRID_X + 20, GRID_Y + 170))
        draw_text(screen, "ESC : retour menu", FONT_SMALL, WHITE, topleft=(RIGHT_GRID_X + 20, GRID_Y + 205))

        self.draw_ship_preview(screen)

        self.place_auto_btn.draw(screen)
        self.place_reset_btn.draw(screen)
    
    def draw_fleet_status(self, surface, board, x, y, title):
        panel_width = 270
        panel_height = 155
        panel = pygame.Rect(x, y, panel_width, panel_height)
        draw_glass_panel(surface, panel, radius=18)

        draw_text(surface, title, FONT_MEDIUM, WHITE, topleft=(x + 14, y + 10))

        line_y = y + 46
        for ship in board.ships:
            status_text = "KO" if ship.is_sunk() else "OK"
            status_color = RED if ship.is_sunk() else GREEN

            display_name = ship.name
            if display_name == "Sous-marin T":
                display_name = "Sous-marin"

            draw_text(surface, display_name, FONT_SMALL, WHITE, topleft=(x + 14, line_y))
            draw_text(surface, status_text, FONT_SMALL, status_color, topleft=(x + 205, line_y))

            line_y += 21

    def draw_battle(self):
        if self.game_mode == "vs_ai":
            subtitle = "À toi de jouer" if self.turn == "player" else "L'ordinateur réfléchit..."
            left_board = self.player_board
            right_board = self.bot_board
            left_title = "Ta flotte"
            right_title = "Flotte ennemie"

        else:
            if self.turn == "player1":
                subtitle = "Tour du Joueur 1"
                left_board = self.player_board
                right_board = self.bot_board
                left_title = "Flotte Joueur 1"
                right_title = "Cibles Joueur 2"
            else:
                subtitle = "Tour du Joueur 2"
                left_board = self.bot_board
                right_board = self.player_board
                left_title = "Flotte Joueur 2"
                right_title = "Cibles Joueur 1"

        self.draw_title_bar(subtitle)

        draw_text(screen, left_title, FONT_MEDIUM, WHITE, center=(LEFT_GRID_X + GRID_SIZE * CELL_SIZE // 2, 150))
        draw_text(screen, right_title, FONT_MEDIUM, WHITE, center=(RIGHT_GRID_X + GRID_SIZE * CELL_SIZE // 2, 150))

        self.draw_board(screen, left_board, LEFT_GRID_X, GRID_Y, reveal_ships=True)
        self.draw_board(screen, right_board, RIGHT_GRID_X, GRID_Y, reveal_ships=False)

        status_y = GRID_Y + GRID_SIZE * CELL_SIZE + 8

        if self.game_mode == "vs_ai":
            self.draw_fleet_status(screen, self.player_board, LEFT_GRID_X + 10, status_y, "Bateaux restants")
            self.draw_fleet_status(screen, self.bot_board, RIGHT_GRID_X + 10, status_y, "Flotte ennemie")
        else:
            if self.turn == "player1":
                self.draw_fleet_status(screen, self.player_board, LEFT_GRID_X + 10, status_y, "Flotte Joueur 1")
                self.draw_fleet_status(screen, self.bot_board, RIGHT_GRID_X + 10, status_y, "Flotte Joueur 2")
            else:
                self.draw_fleet_status(screen, self.bot_board, LEFT_GRID_X + 10, status_y, "Flotte Joueur 2")
                self.draw_fleet_status(screen, self.player_board, RIGHT_GRID_X + 10, status_y, "Flotte Joueur 1")

    def draw_transition(self):
        self.draw_title_bar("Passage de relais")

        panel = pygame.Rect(WIDTH // 2 - 260, 220, 520, 250)
        draw_glass_panel(screen, panel, radius=24)

        if self.transition_reason == "placement_p2":
            title = "Joueur 2"
            subtitle = "Appuie sur ENTRÉE pour placer ta flotte."
        else:
            next_player = "Joueur 1" if self.turn == "player1" else "Joueur 2"
            title = next_player
            subtitle = "Appuie sur ENTRÉE pour jouer ton tour."

        draw_text(screen, title, FONT_BIG, WHITE, center=(WIDTH // 2, 290))
        draw_text(screen, subtitle, FONT_MEDIUM, CYAN, center=(WIDTH // 2, 350))
        draw_text(screen, "L'autre joueur ne doit pas regarder l'écran.", FONT_SMALL, WHITE, center=(WIDTH // 2, 400))

    def draw_end(self):
        if self.game_mode == "vs_ai":
            title = "VICTOIRE !" if self.winner == "player" else "DÉFAITE"
            color = GREEN if self.winner == "player" else RED
        else:
            if self.winner == "player1":
                title = "JOUEUR 1 GAGNE !"
            else:
                title = "JOUEUR 2 GAGNE !"
            color = GREEN

        self.draw_title_bar("Fin de partie")

        panel = pygame.Rect(WIDTH // 2 - 250, 220, 500, 380)
        draw_glass_panel(screen, panel, radius=24)

        draw_text(screen, title, FONT_TITLE, color, center=(WIDTH // 2, 285))
        draw_text(screen, self.message, FONT_MEDIUM, WHITE, center=(WIDTH // 2, 350))

        self.end_replay.draw(screen)
        self.end_menu.draw(screen)

    def draw_message_bar(self):
        bar = pygame.Rect(60, HEIGHT - 58, WIDTH - 120, 36)
        pygame.draw.rect(screen, (255, 255, 255), bar, border_radius=10)
        draw_text(screen, self.message, FONT_SMALL, BLACK, center=bar.center)

    def draw(self):
        draw_vertical_gradient(screen, BG_TOP, BG_BOTTOM)
        draw_ocean_overlay(screen)

        if self.state == "menu":
            self.draw_menu()
        elif self.state == "mode_select":
            self.draw_mode_select()
        elif self.state == "rules":
            self.draw_rules()
        elif self.state == "placement":
            self.draw_placement()
        elif self.state == "battle":
            self.draw_battle()
        elif self.state == "transition":
            self.draw_transition()
        elif self.state == "end":
            self.draw_end()

        pygame.display.flip()

    # ======================================================
    # LOOP
    # ======================================================
    def run(self):
        while True:
            clock.tick(FPS)

            for event in pygame.event.get():
                self.handle_event(event)

            self.update()
            self.draw()


# ==========================================================
# LANCEMENT
# ==========================================================
if __name__ == "__main__":
    game = NavalStrikeGame()
    game.run()