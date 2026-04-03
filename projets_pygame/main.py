import pygame
import subprocess
import sys
import os

# =========================
# CONFIGURATION
# =========================

WIDTH, HEIGHT = 800, 600
FPS = 60

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (60, 60, 60)
LIGHT_GRAY = (120, 120, 120)

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Launcher de jeux")

font_title = pygame.font.SysFont("arial", 50)
font_button = pygame.font.SysFont("arial", 30)

clock = pygame.time.Clock()

# =========================
# LISTE DES JEUX
# =========================

games = [
    ("Snake", "snake.py"),
    ("Pong", "pong.py"),
    ("Pong Rachid", "pong_r.py"),
    ("Bataille Navale", "bataille_navale.py"),
]

# =========================
# FONCTION LANCEMENT
# =========================

def launch_game(script):
    pygame.quit()

    path = os.path.join(os.path.dirname(__file__), script)

    subprocess.run([sys.executable, path])

    # Relance complètement le launcher
    os.execv(sys.executable, [sys.executable] + sys.argv)

# =========================
# BOUTON UI
# =========================

class Button:
    def __init__(self, text, rect):
        self.text = text
        self.rect = pygame.Rect(rect)

    def draw(self):
        mouse = pygame.mouse.get_pos()
        color = LIGHT_GRAY if self.rect.collidepoint(mouse) else GRAY

        pygame.draw.rect(screen, color, self.rect, border_radius=10)

        label = font_button.render(self.text, True, WHITE)

        screen.blit(
            label,
            (
                self.rect.centerx - label.get_width() // 2,
                self.rect.centery - label.get_height() // 2
            )
        )

    def clicked(self, pos):
        return self.rect.collidepoint(pos)

# =========================
# CREATION DES BOUTONS
# =========================

buttons = []

button_width = 300
button_height = 60
spacing = 20

total_buttons = len(games) + 1  # +1 pour le bouton Quitter
total_height = total_buttons * button_height + (total_buttons - 1) * spacing

start_y = HEIGHT // 2 - total_height // 2 + 30

for i, (name, script) in enumerate(games):
    rect = (
        WIDTH // 2 - button_width // 2,
        start_y + i * (button_height + spacing),
        button_width,
        button_height
    )
    buttons.append(Button(name, rect))

quit_button = Button(
    "Quitter",
    (
        WIDTH // 2 - button_width // 2,
        start_y + len(games) * (button_height + spacing),
        button_width,
        button_height
    )
)

# =========================
# BOUCLE PRINCIPALE
# =========================

running = True

while running:
    screen.fill(BLACK)

    title = font_title.render("Choisir un jeu", True, WHITE)
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 70))

    for b in buttons:
        b.draw()

    quit_button.draw()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.MOUSEBUTTONDOWN:
            for (name, script), button in zip(games, buttons):
                if button.clicked(event.pos):
                    launch_game(script)

            if quit_button.clicked(event.pos):
                running = False

    pygame.display.update()
    clock.tick(FPS)

pygame.quit()