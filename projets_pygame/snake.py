import pygame
import random
import sys
import colorsys

# =========================
# INITIALISATION
# =========================
pygame.init()

# =========================
# CONSTANTES GÉNÉRALES
# =========================
WIDTH, HEIGHT = 800, 600
HUD_HEIGHT = 60
BLOCK_SIZE = 20

# Vitesse
SPEED_INCREMENT = 0.5

# Couleurs
BLACK = (0, 0, 0)
RED = (200, 0, 0)
WHITE = (255, 255, 255)


# =========================
# CLASSE SNAKE
# =========================
class Snake:
    def __init__(self, play_left, play_top, grid_cols, grid_rows):
        start_x = play_left + (grid_cols // 2) * BLOCK_SIZE
        start_y = play_top + (grid_rows // 2) * BLOCK_SIZE

        self.body = [(start_x, start_y)]

        self.dx = BLOCK_SIZE
        self.dy = 0
        self.next_dx = self.dx
        self.next_dy = self.dy

        self.grow_pending = 0

        # Couleur vive aléatoire
        h = random.random()
        r, g, b = colorsys.hsv_to_rgb(h, 0.8, 1)
        self.base_color = (
            int(r * 255),
            int(g * 255),
            int(b * 255)
        )

    # -------------------------
    # Déplacement / croissance
    # -------------------------
    def move(self):
        self.dx, self.dy = self.next_dx, self.next_dy

        head_x, head_y = self.body[0]
        new_head = (head_x + self.dx, head_y + self.dy)
        self.body.insert(0, new_head)

        if self.grow_pending > 0:
            self.grow_pending -= 1
        else:
            self.body.pop()

    def grow(self):
        self.grow_pending += 1

    def change_direction(self, key):
        if key == pygame.K_UP:
            ndx, ndy = 0, -BLOCK_SIZE
        elif key == pygame.K_DOWN:
            ndx, ndy = 0, BLOCK_SIZE
        elif key == pygame.K_LEFT:
            ndx, ndy = -BLOCK_SIZE, 0
        elif key == pygame.K_RIGHT:
            ndx, ndy = BLOCK_SIZE, 0
        else:
            return

        # Empêche le demi-tour direct
        if (ndx, ndy) == (-self.dx, -self.dy):
            return

        self.next_dx, self.next_dy = ndx, ndy

    # -------------------------
    # Collisions
    # -------------------------
    def check_collision(self, play_left, play_right, play_top, play_bottom):
        head = self.body[0]

        # Collision avec les murs
        if head[0] < play_left or head[0] >= play_right or head[1] < play_top or head[1] >= play_bottom:
            return True

        # Collision avec le corps
        if head in self.body[1:]:
            return True

        return False

    # -------------------------
    # Affichage
    # -------------------------
    def draw(self, window):
        r, g, b = self.base_color

        for i, block in enumerate(self.body):
            if i == 0:
                color = (
                    min(255, r + 40),
                    min(255, g + 40),
                    min(255, b + 40)
                )
            else:
                length = len(self.body)
                shade = max(0.35, 1 - i / length)
                color = (
                    int(r * shade),
                    int(g * shade),
                    int(b * shade)
                )

            pygame.draw.rect(
                window,
                color,
                (*block, BLOCK_SIZE, BLOCK_SIZE),
                border_radius=6
            )


# =========================
# CLASSE FOOD
# =========================
class Food:
    def __init__(self, snake, play_left, play_right, play_top, play_bottom):
        self.snake = snake
        self.play_left = play_left
        self.play_right = play_right
        self.play_top = play_top
        self.play_bottom = play_bottom
        self.position = self.random_position()

    # -------------------------
    # Positionnement
    # -------------------------
    def random_position(self):
        while True:
            pos = (
                random.randrange(self.play_left, self.play_right, BLOCK_SIZE),
                random.randrange(self.play_top, self.play_bottom, BLOCK_SIZE)
            )
            if pos not in self.snake.body:
                return pos

    def respawn(self):
        self.position = self.random_position()

    # -------------------------
    # Affichage
    # -------------------------
    def draw(self, window):
        center = (
            self.position[0] + BLOCK_SIZE // 2,
            self.position[1] + BLOCK_SIZE // 2
        )
        pygame.draw.circle(window, RED, center, BLOCK_SIZE // 2)


# =========================
# CLASSE GAME
# =========================
class Game:
    def __init__(self):
        self.window = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Snake POO")
        self.clock = pygame.time.Clock()

        # -------------------------
        # Modes de jeu
        # -------------------------
        self.mode_settings = {
            "CLASSIC": {
                "grid": (16, 16),
                "food_count": 1,
                "base_speed": 10,
                "max_speed": 14,
            },
            "DOUBLE": {
                "grid": (18, 18),
                "food_count": 2,
                "base_speed": 10,
                "max_speed": 16,
            },
            "TRIPLE": {
                "grid": (20, 20),
                "food_count": 3,
                "base_speed": 10,
                "max_speed": 18,
            }
        }

        self.game_mode = "CLASSIC"

        # -------------------------
        # IA
        # -------------------------
        self.ai_mode = False
        self.perfect_ai = False
        self.ai_test_speed = 80
        self.cycle_index = 0

        # -------------------------
        # Dimensions dynamiques
        # -------------------------
        self.update_playfield_dimensions()

        # -------------------------
        # Police / UI
        # -------------------------
        self.font = pygame.font.SysFont("arial", 20)
        self.big_font = pygame.font.SysFont("arial", 72)
        self.play_button = None

        # -------------------------
        # Etat du jeu
        # -------------------------
        self.state = "MENU"  # MENU | COUNTDOWN | PLAYING | PAUSE | GAME_OVER | WIN
        self.countdown_start = None
        self.pause_alpha = 0
        self.running = True

        # -------------------------
        # Gameplay / scores
        # -------------------------
        self.speed = self.get_current_base_speed()
        self.score = 0
        self.score_history = []

        # -------------------------
        # Objets de jeu
        # -------------------------
        self.snake = Snake(self.play_left, self.play_top, self.grid_cols, self.grid_rows)
        self.foods = self.create_foods()

    # ==========================================================
    # CONFIGURATION DU TERRAIN / MODE
    # ==========================================================
    def update_playfield_dimensions(self):
        settings = self.mode_settings[self.game_mode]

        self.grid_cols, self.grid_rows = settings["grid"]
        self.food_count = settings["food_count"]

        self.play_width = self.grid_cols * BLOCK_SIZE
        self.play_height = self.grid_rows * BLOCK_SIZE

        self.play_left = (WIDTH - self.play_width) // 2

        available_height = HEIGHT - HUD_HEIGHT
        self.play_top = HUD_HEIGHT + (available_height - self.play_height) // 2
        self.play_right = self.play_left + self.play_width
        self.play_bottom = self.play_top + self.play_height

        self.max_cells = self.grid_cols * self.grid_rows

        # Recalcule le cycle hamiltonien selon la grille actuelle
        self.hamiltonian_cycle = self.generate_hamiltonian_cycle()
        self.cycle_index = 0

    def create_foods(self):
        return [
            Food(self.snake, self.play_left, self.play_right, self.play_top, self.play_bottom)
            for _ in range(self.food_count)
        ]

    # ==========================================================
    # GESTION DES VITESSES
    # ==========================================================
    def get_current_base_speed(self):
        return self.mode_settings[self.game_mode]["base_speed"]

    def get_current_max_speed(self):
        return self.mode_settings[self.game_mode]["max_speed"]

    def get_tick_speed(self):
        if self.ai_mode or self.perfect_ai:
            return self.ai_test_speed
        return self.speed

    # ==========================================================
    # IA
    # ==========================================================
    def ai_choose_direction(self):
        if not self.foods:
            return

        head_x, head_y = self.snake.body[0]
        food_x, food_y = self.foods[0].position

        directions = [
            (BLOCK_SIZE, 0),
            (-BLOCK_SIZE, 0),
            (0, BLOCK_SIZE),
            (0, -BLOCK_SIZE)
        ]

        best_dir = None
        best_dist = float("inf")

        for dx, dy in directions:
            nx = head_x + dx
            ny = head_y + dy

            if nx < self.play_left or nx >= self.play_right or ny < self.play_top or ny >= self.play_bottom:
                continue

            if (nx, ny) in self.snake.body:
                continue

            dist = abs(nx - food_x) + abs(ny - food_y)

            if dist < best_dist:
                best_dist = dist
                best_dir = (dx, dy)

        if best_dir:
            self.snake.next_dx, self.snake.next_dy = best_dir

    def generate_hamiltonian_cycle(self):
        path = []

        for y in range(self.grid_rows):
            if y % 2 == 0:
                for x in range(self.grid_cols):
                    path.append((self.play_left + x * BLOCK_SIZE, self.play_top + y * BLOCK_SIZE))
            else:
                for x in reversed(range(self.grid_cols)):
                    path.append((self.play_left + x * BLOCK_SIZE, self.play_top + y * BLOCK_SIZE))

        return path

    def perfect_ai_move(self):
        head = self.snake.body[0]

        if head in self.hamiltonian_cycle:
            self.cycle_index = self.hamiltonian_cycle.index(head)

        next_index = (self.cycle_index + 1) % len(self.hamiltonian_cycle)
        next_cell = self.hamiltonian_cycle[next_index]

        dx = next_cell[0] - head[0]
        dy = next_cell[1] - head[1]

        self.snake.next_dx = dx
        self.snake.next_dy = dy

    # ==========================================================
    # AFFICHAGE : FONDS / TERRAIN / HUD
    # ==========================================================
    def draw_fullscreen_background(self):
        for y in range(HEIGHT):
            color = (8, 10 + y // 6, 18 + y // 8)
            pygame.draw.line(self.window, color, (0, y), (WIDTH, y))

        for x in range(0, WIDTH, BLOCK_SIZE):
            pygame.draw.line(self.window, (35, 35, 45), (x, 0), (x, HEIGHT))
        for y in range(0, HEIGHT, BLOCK_SIZE):
            pygame.draw.line(self.window, (35, 35, 45), (0, y), (WIDTH, y))

    def draw_gradient(self):
        for y in range(self.play_top, self.play_bottom):
            yy = y - self.play_top
            color = (10, 10 + yy // 4, 20 + yy // 6)
            pygame.draw.line(self.window, color, (self.play_left, y), (self.play_right, y))

    def draw_grid(self):
        for x in range(self.play_left, self.play_right + 1, BLOCK_SIZE):
            pygame.draw.line(self.window, (40, 40, 40), (x, self.play_top), (x, self.play_bottom))
        for y in range(self.play_top, self.play_bottom + 1, BLOCK_SIZE):
            pygame.draw.line(self.window, (40, 40, 40), (self.play_left, y), (self.play_right, y))

    def draw_playfield_frame(self):
        frame_rect = pygame.Rect(
            self.play_left - 4,
            self.play_top - 4,
            self.play_width + 8,
            self.play_height + 8
        )
        pygame.draw.rect(self.window, (70, 70, 90), frame_rect, border_radius=8)
        pygame.draw.rect(
            self.window,
            (20, 20, 30),
            (self.play_left, self.play_top, self.play_width, self.play_height),
            border_radius=6
        )

    def draw_hud_glass(self):
        hud = pygame.Surface((WIDTH, HUD_HEIGHT))
        hud.fill((15, 15, 20))

        # Shine
        shine_h = HUD_HEIGHT // 2
        for i in range(shine_h):
            intensity = max(0, 70 - i * 4)
            pygame.draw.line(
                hud,
                (15 + intensity, 15 + intensity, 20 + intensity),
                (12, 8 + i),
                (WIDTH - 12, 8 + i)
            )

        # Bordures
        pygame.draw.rect(hud, (40, 40, 55), (0, 0, WIDTH, HUD_HEIGHT), width=1)
        pygame.draw.line(hud, (60, 60, 80), (0, HUD_HEIGHT - 1), (WIDTH, HUD_HEIGHT - 1))

        # -------------------------
        # Bloc gauche : score / best
        # -------------------------
        score_text = self.font.render(f"Score : {self.score}", True, WHITE)
        best_text = self.font.render(f"Best : {self.best_score()}", True, WHITE)

        hud.blit(score_text, (18, 8))
        hud.blit(best_text, (18, 30))

        # -------------------------
        # Bloc centre : direction / IA
        # -------------------------
        cx, cy = WIDTH // 2, HUD_HEIGHT // 2
        pygame.draw.circle(hud, (25, 25, 35), (cx, cy), 18)
        pygame.draw.circle(hud, (70, 70, 95), (cx, cy), 18, 1)

        dir_x = cx - 12
        dir_y = cy - 12

        if self.snake.dx == BLOCK_SIZE:
            self._draw_arrow_on(hud, dir_x, dir_y, "right")
        elif self.snake.dx == -BLOCK_SIZE:
            self._draw_arrow_on(hud, dir_x, dir_y, "left")
        elif self.snake.dy == BLOCK_SIZE:
            self._draw_arrow_on(hud, dir_x, dir_y, "down")
        elif self.snake.dy == -BLOCK_SIZE:
            self._draw_arrow_on(hud, dir_x, dir_y, "up")

        if self.ai_mode or self.perfect_ai:
            ai_text = self.font.render("IA", True, (255, 200, 0))
            hud.blit(ai_text, (cx - ai_text.get_width() // 2, 6))

        # -------------------------
        # Bloc droite : mode / vitesse / pommes
        # -------------------------
        mode_text = self.font.render(f"Mode : {self.game_mode}", True, WHITE)
        speed_text = self.font.render(f"Vitesse : {self.speed:.1f}", True, WHITE)
        food_text = self.font.render(f"Pommes : {self.food_count}", True, WHITE)

        right_x = WIDTH - 220
        hud.blit(mode_text, (right_x, 4))
        hud.blit(speed_text, (right_x, 22))
        hud.blit(food_text, (right_x, 40))

        self.window.blit(hud, (0, 0))

    def _draw_arrow_on(self, surface, x, y, direction):
        color = (255, 255, 255)
        size = 12

        if direction == "up":
            points = [(x, y + size), (x + size, y), (x + 2 * size, y + size)]
        elif direction == "down":
            points = [(x, y), (x + size, y + size), (x + 2 * size, y)]
        elif direction == "left":
            points = [(x + size, y), (x, y + size), (x + size, y + 2 * size)]
        else:
            points = [(x, y), (x + size, y + size), (x, y + 2 * size)]

        pygame.draw.polygon(surface, color, points)

    # ==========================================================
    # AFFICHAGE : BOUTONS / MENUS
    # ==========================================================
    def draw_button(self, text, rect, hovered):
        color = (70, 70, 70) if not hovered else (100, 100, 100)
        pygame.draw.rect(self.window, color, rect, border_radius=10)

        label = self.font.render(text, True, WHITE)
        self.window.blit(
            label,
            (
                rect.centerx - label.get_width() // 2,
                rect.centery - label.get_height() // 2
            )
        )

    def draw_arrow(self, x, y, direction):
        color = WHITE
        size = 12

        if direction == "up":
            points = [(x, y + size), (x + size, y), (x + 2 * size, y + size)]
        elif direction == "down":
            points = [(x, y), (x + size, y + size), (x + 2 * size, y)]
        elif direction == "left":
            points = [(x + size, y), (x, y + size), (x + size, y + 2 * size)]
        else:
            points = [(x, y), (x + size, y + size), (x, y + 2 * size)]

        pygame.draw.polygon(self.window, color, points)

    def draw_menu(self):
        self.draw_fullscreen_background()

        center_x = WIDTH // 2

        panel_width = 460
        panel_height = 560
        panel_x = center_x - panel_width // 2
        panel_y = 30

        panel = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        pygame.draw.rect(panel, (12, 12, 18, 225), (0, 0, panel_width, panel_height), border_radius=24)

        shine_h = 120
        for i in range(shine_h):
            alpha = max(0, 55 - i // 2)
            pygame.draw.line(
                panel,
                (255, 255, 255, alpha),
                (20, 18 + i),
                (panel_width - 20, 18 + i)
            )

        pygame.draw.rect(panel, (255, 255, 255, 35), (0, 0, panel_width, panel_height), width=1, border_radius=24)
        self.window.blit(panel, (panel_x, panel_y))

        title = self.big_font.render("SNAKE", True, WHITE)
        self.window.blit(title, (center_x - title.get_width() // 2, panel_y + 30))

        button_y = panel_y + 155
        button_rect = pygame.Rect(center_x - 140, button_y, 280, 68)
        mouse_pos = pygame.mouse.get_pos()
        hovered = button_rect.collidepoint(mouse_pos)
        self.draw_button("JOUER", button_rect, hovered)

        mode_y = panel_y + 250
        mode_text = self.font.render(f"Mode : {self.game_mode}", True, WHITE)
        self.window.blit(mode_text, (center_x - mode_text.get_width() // 2, mode_y))

        arrow_y = panel_y + 315
        spacing = 55
        start_x = center_x - 95

        self.draw_arrow(start_x, arrow_y, "up")
        self.draw_arrow(start_x + spacing, arrow_y, "down")
        self.draw_arrow(start_x + 2 * spacing, arrow_y, "left")
        self.draw_arrow(start_x + 3 * spacing, arrow_y, "right")

        label = self.font.render("Déplacement", True, WHITE)
        self.window.blit(label, (center_x - label.get_width() // 2, arrow_y + 35))

        controls = [
            "1 : Classique (1 pomme)",
            "2 : Double (2 pommes)",
            "3 : Triple (3 pommes)",
            "P : Pause (en jeu)",
            "Q : Quitter"
        ]

        controls_y = panel_y + 385
        line_spacing = 34

        for i, ctrl in enumerate(controls):
            text = self.font.render(ctrl, True, WHITE)
            self.window.blit(
                text,
                (center_x - text.get_width() // 2, controls_y + i * line_spacing)
            )

        return button_rect

    def draw_countdown(self):
        self.draw_fullscreen_background()

        elapsed = (pygame.time.get_ticks() - self.countdown_start) // 1000
        number = 3 - elapsed

        if number <= 0:
            self.reset()
            self.state = "PLAYING"
            return

        panel_width = 320
        panel_height = 220
        panel_x = WIDTH // 2 - panel_width // 2
        panel_y = HEIGHT // 2 - panel_height // 2

        panel = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        pygame.draw.rect(panel, (12, 12, 18, 220), (0, 0, panel_width, panel_height), border_radius=24)
        pygame.draw.rect(panel, (255, 255, 255, 35), (0, 0, panel_width, panel_height), width=1, border_radius=24)
        self.window.blit(panel, (panel_x, panel_y))

        countdown_font = pygame.font.SysFont("arial", 120)
        text = countdown_font.render(str(number), True, WHITE)
        self.window.blit(
            text,
            (
                WIDTH // 2 - text.get_width() // 2,
                HEIGHT // 2 - text.get_height() // 2
            )
        )

        subtext = self.font.render("Prépare-toi...", True, WHITE)
        self.window.blit(
            subtext,
            (
                WIDTH // 2 - subtext.get_width() // 2,
                panel_y + panel_height - 55
            )
        )

    def draw_pause(self):
        self.window.fill(BLACK)
        self.draw_playfield_frame()
        self.draw_gradient()
        self.draw_grid()
        self.snake.draw(self.window)

        for food in self.foods:
            food.draw(self.window)

        self.draw_hud_glass()

        self.pause_alpha = min(160, self.pause_alpha + 8)

        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, self.pause_alpha))
        self.window.blit(overlay, (0, 0))

        title = self.big_font.render("PAUSE", True, WHITE)

        t = pygame.time.get_ticks() * 0.005
        pulse = int(200 + 55 * (1 + pygame.math.Vector2(1, 0).rotate(t).x) / 2)
        pulse_color = (pulse, pulse, pulse)

        p_text = self.font.render("P : Reprendre", True, pulse_color)
        m_text = self.font.render("M : Menu principal", True, WHITE)
        q_text = self.font.render("Q : Quitter", True, WHITE)

        center_x = WIDTH // 2
        start_y = HEIGHT // 2 - 110
        line = 40

        self.window.blit(title, (center_x - title.get_width() // 2, start_y))
        self.window.blit(p_text, (center_x - p_text.get_width() // 2, start_y + 2 * line))
        self.window.blit(m_text, (center_x - m_text.get_width() // 2, start_y + 3 * line))
        self.window.blit(q_text, (center_x - q_text.get_width() // 2, start_y + 4 * line))

    def draw_game_over(self):
        self.window.fill(BLACK)

        best = self.best_score()
        prog = self.progression()

        title = self.font.render("GAME OVER", True, RED)
        score_text = self.font.render(f"Score : {self.score}", True, WHITE)
        best_text = self.font.render(f"Meilleur score : {best}", True, WHITE)

        if prog > 0:
            prog_text = self.font.render(f"Nouveau record ! (+{prog})", True, (0, 220, 0))
        elif prog < 0:
            prog_text = self.font.render(f"-{abs(prog)} vs record", True, (200, 0, 0))
        else:
            prog_text = self.font.render("Égalité record", True, WHITE)

        replay_text = self.font.render("R : Rejouer", True, WHITE)
        menu_text = self.font.render("M : Menu principal", True, WHITE)
        quit_text = self.font.render("Q : Quitter", True, WHITE)

        center_x = WIDTH // 2
        start_y = HEIGHT // 2 - 120
        line = 35

        self.window.blit(title, (center_x - title.get_width() // 2, start_y))
        self.window.blit(score_text, (center_x - score_text.get_width() // 2, start_y + line))
        self.window.blit(best_text, (center_x - best_text.get_width() // 2, start_y + 2 * line))
        self.window.blit(prog_text, (center_x - prog_text.get_width() // 2, start_y + 3 * line))
        self.window.blit(replay_text, (center_x - replay_text.get_width() // 2, start_y + 4 * line))
        self.window.blit(menu_text, (center_x - menu_text.get_width() // 2, start_y + 5 * line))
        self.window.blit(quit_text, (center_x - quit_text.get_width() // 2, start_y + 6 * line))

    def draw_win(self):
        self.window.fill(BLACK)

        title = self.big_font.render("TU AS GAGNÉ !", True, (0, 220, 0))
        score_text = self.font.render(f"Score : {self.score}", True, WHITE)
        best_text = self.font.render(f"Meilleur score : {self.best_score()}", True, WHITE)

        replay_text = self.font.render("R : Rejouer", True, WHITE)
        menu_text = self.font.render("M : Menu principal", True, WHITE)
        quit_text = self.font.render("Q : Quitter", True, WHITE)

        center_x = WIDTH // 2
        start_y = HEIGHT // 2 - 140
        line = 40

        self.window.blit(title, (center_x - title.get_width() // 2, start_y))
        self.window.blit(score_text, (center_x - score_text.get_width() // 2, start_y + 2 * line))
        self.window.blit(best_text, (center_x - best_text.get_width() // 2, start_y + 3 * line))
        self.window.blit(replay_text, (center_x - replay_text.get_width() // 2, start_y + 5 * line))
        self.window.blit(menu_text, (center_x - menu_text.get_width() // 2, start_y + 6 * line))
        self.window.blit(quit_text, (center_x - quit_text.get_width() // 2, start_y + 7 * line))

    # ==========================================================
    # SCORES / PROGRESSION
    # ==========================================================
    def best_score(self):
        return max(self.score_history) if self.score_history else 0

    def progression(self):
        if not self.score_history:
            return 0
        if len(self.score_history) < 2:
            return self.score_history[-1]

        current_score = self.score_history[-1]
        previous_best = max(self.score_history[:-1])
        return current_score - previous_best

    # ==========================================================
    # GESTION DES ÉVÉNEMENTS
    # ==========================================================
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                # IA
                if event.key == pygame.K_i:
                    self.ai_mode = not self.ai_mode
                elif event.key == pygame.K_o:
                    self.perfect_ai = not self.perfect_ai

                # Menu principal
                if self.state == "MENU":
                    if event.key == pygame.K_q:
                        pygame.quit()
                        sys.exit()

                    elif event.key in (pygame.K_1, pygame.K_KP1) or event.unicode in ["1", "&"]:
                        self.game_mode = "CLASSIC"
                        self.update_playfield_dimensions()

                    elif event.key in (pygame.K_2, pygame.K_KP2) or event.unicode in ["2", "é"]:
                        self.game_mode = "DOUBLE"
                        self.update_playfield_dimensions()

                    elif event.key in (pygame.K_3, pygame.K_KP3) or event.unicode in ["3", '"']:
                        self.game_mode = "TRIPLE"
                        self.update_playfield_dimensions()

                # Pause
                elif self.state == "PLAYING" and event.key == pygame.K_p:
                    self.state = "PAUSE"
                    return

                elif self.state == "PAUSE" and event.key == pygame.K_p:
                    self.pause_alpha = 0
                    self.state = "PLAYING"
                    return

                elif self.state == "PAUSE":
                    if event.key == pygame.K_m:
                        self.state = "MENU"
                        return
                    elif event.key == pygame.K_q:
                        pygame.quit()
                        sys.exit()
                    return

                # Jeu
                elif self.state == "PLAYING":
                    self.snake.change_direction(event.key)

                # Game Over
                elif self.state == "GAME_OVER":
                    if event.key == pygame.K_r:
                        self.reset()
                        self.state = "COUNTDOWN"
                        self.countdown_start = pygame.time.get_ticks()
                    elif event.key == pygame.K_m:
                        self.reset()
                        self.state = "MENU"
                    elif event.key == pygame.K_q:
                        pygame.quit()
                        sys.exit()

                # Victoire
                elif self.state == "WIN":
                    if event.key == pygame.K_r:
                        self.reset()
                        self.state = "COUNTDOWN"
                        self.countdown_start = pygame.time.get_ticks()
                    elif event.key == pygame.K_m:
                        self.reset()
                        self.state = "MENU"
                    elif event.key == pygame.K_q:
                        pygame.quit()
                        sys.exit()

            # Bouton jouer
            if event.type == pygame.MOUSEBUTTONDOWN:
                if self.state == "MENU" and self.play_button and self.play_button.collidepoint(event.pos):
                    self.state = "COUNTDOWN"
                    self.countdown_start = pygame.time.get_ticks()

    # ==========================================================
    # GAMEPLAY / UPDATE / RESET
    # ==========================================================
    def update(self):
        if self.state != "PLAYING":
            return

        if self.perfect_ai:
            self.perfect_ai_move()

        if self.ai_mode:
            self.ai_choose_direction()

        self.snake.move()

        for food in self.foods:
            if self.snake.body[0] == food.position:
                self.snake.grow()
                self.score += 1

                self.speed = min(
                    self.get_current_max_speed(),
                    self.get_current_base_speed() + self.score * SPEED_INCREMENT
                )

                if len(self.snake.body) + self.snake.grow_pending >= self.max_cells:
                    self.score_history.append(self.score)
                    self.state = "WIN"
                    return

                food.respawn()
                break

        if self.snake.check_collision(self.play_left, self.play_right, self.play_top, self.play_bottom):
            self.score_history.append(self.score)
            self.state = "GAME_OVER"

    def reset(self):
        self.snake = Snake(self.play_left, self.play_top, self.grid_cols, self.grid_rows)
        self.score = 0
        self.speed = self.get_current_base_speed()
        self.foods = self.create_foods()

        # Réinitialise les IA après une partie
        self.ai_mode = False
        self.perfect_ai = False

    # ==========================================================
    # BOUCLE PRINCIPALE / RENDU
    # ==========================================================
    def draw(self):
        if self.state == "MENU":
            self.play_button = self.draw_menu()

        elif self.state == "COUNTDOWN":
            self.draw_countdown()

        elif self.state == "PAUSE":
            self.draw_pause()

        elif self.state == "PLAYING":
            self.window.fill((8, 8, 12))
            self.draw_playfield_frame()
            self.draw_gradient()
            self.draw_grid()

            self.snake.draw(self.window)
            for food in self.foods:
                food.draw(self.window)

            self.draw_hud_glass()

        elif self.state == "GAME_OVER":
            self.draw_game_over()

        elif self.state == "WIN":
            self.draw_win()

        pygame.display.update()

    def run(self):
        while self.running:
            self.clock.tick(self.get_tick_speed())
            self.handle_events()
            self.update()
            self.draw()


if __name__ == "__main__":
    game = Game()
    game.run()