"""
main.py – Lanceur principal : menu de sélection de mode et pont vers les sous-jeux.

Les sous-jeux (solo, online) appellent pygame.display.quit() mais PAS pygame.quit()
pour que le Launcher puisse recréer la fenêtre proprement après leur fermeture.
"""
import threading
import time
import math
import random

import pygame

from loup_garou_online import WerewolfOnlineGame
from loup_garou_solo import WerewolfSoloGame
from loup_server import WerewolfServer
from loup_shared import MIN_PLAYERS, MAX_PLAYERS
from server_discovery import ServerDiscovery
from loup_ui_theme import (
    BG_DEEP, BG_TOP, BG_BOTTOM, BG_MID,
    MOON_SILVER, MOON_GLOW,
    WOLF_RED, MIST_PURPLE, MIST_LIGHT,
    GOLD_WARM, GOLD_PALE,
    CYAN_COOL, WHITE_SOFT, GREY_DIM,
    BTN_PRIMARY, BTN_PRIMARY_H,
    BTN_DANGER, BTN_DANGER_H,
    BTN_SUCCESS, BTN_SUCCESS_H,
    BTN_NEUTRAL, BTN_NEUTRAL_H,
    BTN_BORDER,
    draw_gradient_bg, draw_glass_panel, draw_text, wrap_text,
    draw_moon, draw_tree_silhouette,
    ParticleSystem, Button, InputBox, Stepper,
    scaled_fonts, clear_font_cache,
)

BASE_W, BASE_H = 1100, 760
MIN_W,  MIN_H  = 900,  660


# ── Fond forestier animé ─────────────────────────────────────────────────────

_STARS = None
_STARS_SIZE = (0, 0)


def _init_stars(w, h):
    # Recalcule les étoiles uniquement si la taille de la fenêtre a changé
    global _STARS, _STARS_SIZE
    if _STARS is None or _STARS_SIZE != (w, h):
        _STARS = [(random.randint(0, w), random.randint(0, h * 55 // 100),
                   random.uniform(0.5, 1.8), random.uniform(0, math.pi * 2))
                  for _ in range(80)]
        _STARS_SIZE = (w, h)


def draw_forest_scene(surface: pygame.Surface, t: float):
    w, h = surface.get_size()
    draw_gradient_bg(surface, BG_DEEP, BG_BOTTOM)
    _init_stars(w, h)
    # Étoiles
    for sx, sy, sr, sp in _STARS:
        a = int(130 + 80 * math.sin(t * 0.7 + sp))
        ss = pygame.Surface((6, 6), pygame.SRCALPHA)
        pygame.draw.circle(ss, (210, 215, 255, a), (3, 3), max(1, int(sr)))
        surface.blit(ss, (sx - 3, sy - 3))
    # Lune
    draw_moon(surface, int(w * 0.80), int(h * 0.16), int(min(w, h) * 0.07), t)
    # Brume basse
    for i in range(3):
        mist = pygame.Surface((w, 36), pygame.SRCALPHA)
        a = int(14 + 8 * math.sin(t * 0.4 + i))
        for mx in range(w):
            wave = int(5 * math.sin(mx / 90 + t * 0.25 + i))
            pygame.draw.line(mist, (130, 110, 170, a), (mx, 18 + wave), (mx, 36 + wave))
        surface.blit(mist, (0, h - 80 + i * 16))
    # Arbres lointains
    for xi, hi in [(0.03, 0.34), (0.11, 0.28), (0.19, 0.36), (0.27, 0.26),
                   (0.62, 0.31), (0.71, 0.38), (0.81, 0.26), (0.93, 0.33)]:
        draw_tree_silhouette(surface, int(xi * w), h, int(hi * h), (10, 8, 22))
    # Arbres proches
    for xi, hi in [(0.0, 0.46), (0.08, 0.40), (0.17, 0.48), (0.28, 0.42),
                   (0.56, 0.44), (0.66, 0.50), (0.77, 0.46), (0.87, 0.42), (0.97, 0.48)]:
        draw_tree_silhouette(surface, int(xi * w), h, int(hi * h), (5, 4, 12))


# ── Lanceur ───────────────────────────────────────────────────────────────────

class Launcher:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((BASE_W, BASE_H), pygame.RESIZABLE)
        pygame.display.set_caption("Loup-Garou")
        self.clock = pygame.time.Clock()
        self.running = True
        self.state = "main"
        self.t = 0.0
        self.particles = ParticleSystem(BASE_W, BASE_H, 45)

        self.input_name = InputBox(placeholder="Entre ton pseudonyme…", max_len=20)
        self.btn_solo    = Button("MODE SOLO",       BTN_NEUTRAL,  BTN_NEUTRAL_H,  icon="🌙")
        self.btn_online  = Button("MODE EN LIGNE",   BTN_PRIMARY,  BTN_PRIMARY_H,  icon="🐺")
        self.btn_quit    = Button("QUITTER",          BTN_DANGER,   BTN_DANGER_H,   icon="✕")
        self.btn_create  = Button("CREER UN SALON",   BTN_SUCCESS,  BTN_SUCCESS_H,  icon="⚔")
        self.btn_join    = Button("REJOINDRE",         BTN_PRIMARY,  BTN_PRIMARY_H,  icon="🚪")
        self.btn_back    = Button("RETOUR",            BTN_DANGER,   BTN_DANGER_H)
        self.stepper     = Stepper("Nombre de joueurs (IA inclus)", 6, MIN_PLAYERS, 12)
        self.btn_launch  = Button("LANCER LA PARTIE", BTN_SUCCESS,  BTN_SUCCESS_H,  icon="▶")

        self.discovery = ServerDiscovery()
        self.discovery.start()
        self.message       = ""
        self.hosted_server = None
        self.host_thread   = None
        self.selected_idx  = 0
        self.row_rects: list = []

    # ── Utilitaires ──────────────────────────────────────────────────────────

    def fonts(self) -> dict:
        w, h = self.screen.get_size()
        return scaled_fonts(w, h, BASE_W, BASE_H)

    def valid_name(self) -> str:
        return self.input_name.text.strip()[:20]

    def ensure_name(self) -> bool:
        if not self.valid_name():
            self.message = "⚠  Choisis un pseudonyme avant de continuer."
            return False
        return True

    def reset_state(self):
        self.state = "main"
        self.selected_idx = 0
        self.row_rects = []
        self.message = ""

    def restore_window(self, size: tuple):
        """Recrée la fenêtre après qu'un sous-jeu a appelé pygame.display.quit()."""
        if not pygame.get_init():
            pygame.init()
        if not pygame.display.get_init():
            pygame.display.init()
        if not pygame.font.get_init():
            pygame.font.init()
        # Les objets Font ne survivent pas à un reinit de pygame.font → vider le cache
        clear_font_cache()
        self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
        pygame.display.set_caption("Loup-Garou")
        self.clock = pygame.time.Clock()
        pygame.event.clear()

    # ── Lancements ───────────────────────────────────────────────────────────

    def launch_online_game(self, host: str, shutdown_after: bool = False):
        sz = self.screen.get_size()
        error_msg = ""
        try:
            game = WerewolfOnlineGame(host, self.valid_name())
            game.run()
        except Exception as e:
            error_msg = f"Erreur connexion : {e}"
        self.restore_window(sz)
        if shutdown_after and self.hosted_server is not None:
            try:
                self.hosted_server.shutdown()
            except Exception:
                pass
            self.hosted_server = None
            self.host_thread   = None
        self.reset_state()
        if error_msg:
            self.message = error_msg

    def launch_solo_game(self):
        sz = self.screen.get_size()
        error_msg = ""
        try:
            game = WerewolfSoloGame(self.valid_name(), self.stepper.value, None)
            game.run()
        except Exception as e:
            error_msg = f"Erreur solo : {e}"
        self.restore_window(sz)
        self.reset_state()
        if error_msg:
            self.message = error_msg

    def create_server(self):
        """Démarre le serveur dans un thread puis rejoint immédiatement en tant qu'hôte."""
        if self.hosted_server is not None:
            try:
                self.hosted_server.shutdown()
            except Exception:
                pass
            self.hosted_server = None
            self.host_thread   = None

        ready_event = threading.Event()
        server = WerewolfServer(
            host_name=self.valid_name(),
            max_players=MAX_PLAYERS,
            role_config=None,
            ready_event=ready_event,
        )
        self.hosted_server = server
        self.host_thread = threading.Thread(target=server.serve_forever, daemon=True)
        self.host_thread.start()

        # On attend le signal du serveur avant de se connecter : sans ça, le client
        # arriverait avant que le socket ne soit prêt à accepter des connexions.
        if not ready_event.wait(timeout=3.0) or not server.bind_ok:
            self.message = "Impossible de démarrer le serveur (port occupé ?)."
            self.hosted_server = None
            self.host_thread   = None
            return

        self.launch_online_game("127.0.0.1", shutdown_after=True)

    def join_selected(self):
        servers = self.discovery.get_servers()
        if not servers:
            self.message = "Aucun salon trouvé sur le réseau local."
            return
        self.selected_idx = max(0, min(self.selected_idx, len(servers) - 1))
        host = servers[self.selected_idx]["host"]
        self.launch_online_game(host, shutdown_after=False)

    # ── Layout ───────────────────────────────────────────────────────────────

    def _center_panel(self, pw: int = 600, ph: int = 500) -> pygame.Rect:
        w, h = self.screen.get_size()
        return pygame.Rect(w // 2 - pw // 2, h // 2 - ph // 2, pw, ph)

    def layout_main(self) -> pygame.Rect:
        p = self._center_panel(580, 480)
        bw, bh = p.width - 100, 54
        bx = p.x + 50
        self.input_name.set_rect((bx, p.y + 130, bw, 50))
        self.btn_solo.set_rect  ((bx, p.y + 210, bw, bh))
        self.btn_online.set_rect((bx, p.y + 282, bw, bh))
        self.btn_quit.set_rect  ((bx, p.y + 374, bw, 46))
        return p

    def layout_online(self) -> pygame.Rect:
        p = self._center_panel(580, 390)
        bw, bh = p.width - 100, 56
        bx = p.x + 50
        self.btn_create.set_rect((bx, p.y + 160, bw, bh))
        self.btn_join.set_rect  ((bx, p.y + 236, bw, bh))
        self.btn_back.set_rect  ((bx, p.y + 318, bw, 46))
        return p

    def layout_solo(self) -> pygame.Rect:
        p = self._center_panel(580, 460)
        bw = p.width - 100
        bx = p.x + 50
        self.stepper.set_layout(bx, p.y + 190, bw)
        self.btn_launch.set_rect((bx, p.y + 300, bw, 54))
        self.btn_back.set_rect  ((bx, p.y + 376, bw, 46))
        return p

    def layout_join(self) -> pygame.Rect:
        w, h = self.screen.get_size()
        p = pygame.Rect(60, 50, w - 120, h - 120)
        self.btn_back.set_rect((p.x, p.bottom + 10, 180, 42))
        return p

    # ── Dessin ───────────────────────────────────────────────────────────────

    def _logo(self, panel: pygame.Rect, f: dict):
        cx = panel.centerx
        lw = panel.width // 3
        pygame.draw.line(self.screen, GOLD_WARM,
                         (cx - lw // 2, panel.y + 42), (cx + lw // 2, panel.y + 42), 1)
        draw_text(self.screen, "LOUP-GAROU", f["title"], MOON_SILVER,
                  center=(cx, panel.y + 74), shadow=True)
        pygame.draw.line(self.screen, GOLD_WARM,
                         (cx - lw // 2, panel.y + 108), (cx + lw // 2, panel.y + 108), 1)

    def draw_main(self):
        f = self.fonts()
        p = self.layout_main()
        draw_glass_panel(self.screen, p, radius=24)
        self._logo(p, f)
        draw_text(self.screen, "Choisis ton pseudonyme", f["small"], GOLD_PALE,
                  center=(p.centerx, p.y + 118))
        self.input_name.draw(self.screen, f["medium"])
        mouse = pygame.mouse.get_pos()
        self.btn_solo.draw  (self.screen, f["medium"], mouse)
        self.btn_online.draw(self.screen, f["medium"], mouse)
        self.btn_quit.draw  (self.screen, f["medium"], mouse)
        if self.message:
            draw_text(self.screen, self.message, f["small"], WOLF_RED,
                      center=(p.centerx, p.bottom + 28))

    def draw_online(self):
        f = self.fonts()
        p = self.layout_online()
        draw_glass_panel(self.screen, p, radius=24)
        draw_text(self.screen, "MODE EN LIGNE", f["big"], MOON_SILVER,
                  center=(p.centerx, p.y + 52), shadow=True)
        draw_text(self.screen,
                  "Crée un salon ou rejoins-en un sur le réseau local.",
                  f["small"], GOLD_PALE, center=(p.centerx, p.y + 100))
        draw_text(self.screen,
                  "Les rôles se configurent dans le lobby.",
                  f["xs"] if "xs" in f else f["small"], GREY_DIM,
                  center=(p.centerx, p.y + 128))
        mouse = pygame.mouse.get_pos()
        self.btn_create.draw(self.screen, f["medium"], mouse)
        self.btn_join.draw  (self.screen, f["medium"], mouse)
        self.btn_back.draw  (self.screen, f["medium"], mouse)

    def draw_solo(self):
        f = self.fonts()
        p = self.layout_solo()
        draw_glass_panel(self.screen, p, radius=24)
        draw_text(self.screen, "MODE SOLO", f["big"], MOON_SILVER,
                  center=(p.centerx, p.y + 52), shadow=True)
        draw_text(self.screen,
                  f"Tu joues contre des IA – minimum {MIN_PLAYERS} joueurs",
                  f["small"], GOLD_PALE, center=(p.centerx, p.y + 100))
        draw_text(self.screen,
                  "Rôles classiques (loup, voyante, sorcière) attribués automatiquement.",
                  f["xs"] if "xs" in f else f["small"], GREY_DIM,
                  center=(p.centerx, p.y + 132))
        mouse = pygame.mouse.get_pos()
        self.stepper.draw   (self.screen, f["medium"], f["small"], mouse)
        self.btn_launch.draw(self.screen, f["medium"], mouse)
        self.btn_back.draw  (self.screen, f["medium"], mouse)

    def draw_join(self):
        f = self.fonts()
        p = self.layout_join()
        draw_glass_panel(self.screen, p, radius=22)
        draw_text(self.screen, "Salons disponibles", f["big"], MOON_SILVER,
                  center=(p.centerx, p.y + 44), shadow=True)
        self.row_rects = []
        servers = self.discovery.get_servers()
        y = p.y + 90
        if not servers:
            draw_text(self.screen, "Aucun salon trouvé sur le réseau local…",
                      f["medium"], GREY_DIM, center=(p.centerx, p.centery))
        else:
            self.selected_idx = max(0, min(self.selected_idx, len(servers) - 1))
            for i, srv in enumerate(servers):
                sel = (i == self.selected_idx)
                row = pygame.Rect(p.x + 18, y, p.width - 36, 82)
                pygame.draw.rect(self.screen, (58, 38, 88) if sel else (26, 18, 46),
                                 row, border_radius=16)
                pygame.draw.rect(self.screen, MIST_LIGHT if sel else (52, 42, 78),
                                 row, 2, border_radius=16)
                draw_text(self.screen, srv["name"], f["medium"], MOON_SILVER,
                          topleft=(row.x + 60, row.y + 10))
                draw_text(self.screen,
                          f"{srv['players']}/{srv['max_players']} joueurs  •  {srv['host']}",
                          f["small"], CYAN_COOL, topleft=(row.x + 60, row.y + 36))
                draw_text(self.screen,
                          f"Roles : {srv.get('roles', '')}",
                          f["xs"] if "xs" in f else f["small"], GREY_DIM,
                          topleft=(row.x + 60, row.y + 58))
                # Icône
                draw_text(self.screen, "🌕", f["big"], GOLD_WARM,
                          center=(row.x + 34, row.centery))
                if sel:
                    draw_text(self.screen, "▶ Cliquer pour rejoindre", f["small"],
                              GOLD_WARM, topleft=(row.right - 200, row.y + 30))
                self.row_rects.append((i, row))
                y += 92
        mouse = pygame.mouse.get_pos()
        self.btn_back.draw(self.screen, f["small"], mouse)
        draw_text(self.screen, "Haut/Bas pour naviguer  •  Entree pour rejoindre",
                  f["xs"] if "xs" in f else f["small"], GREY_DIM,
                  center=(p.centerx, p.bottom + 20))
        if self.message:
            draw_text(self.screen, self.message, f["small"], WOLF_RED,
                      center=(p.centerx, p.bottom + 40))

    # ── Événements ───────────────────────────────────────────────────────────

    def handle_main(self, event):
        self.input_name.handle_event(event)
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.btn_solo.is_clicked(event.pos):
                if self.ensure_name():
                    self.state = "solo"
            elif self.btn_online.is_clicked(event.pos):
                if self.ensure_name():
                    self.state = "online"
            elif self.btn_quit.is_clicked(event.pos):
                self.running = False

    def handle_online(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.btn_create.is_clicked(event.pos):
                if self.ensure_name():
                    self.create_server()
            elif self.btn_join.is_clicked(event.pos):
                if self.ensure_name():
                    self.state = "join"
                    self.selected_idx = 0
            elif self.btn_back.is_clicked(event.pos):
                self.reset_state()

    def handle_solo(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.stepper.handle_click(event.pos)
            if self.btn_launch.is_clicked(event.pos):
                self.launch_solo_game()
            elif self.btn_back.is_clicked(event.pos):
                self.reset_state()

    def handle_join(self, event):
        servers = self.discovery.get_servers()
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.btn_back.is_clicked(event.pos):
                self.state = "online"
                return
            for i, rect in self.row_rects:
                if rect.collidepoint(event.pos):
                    self.selected_idx = i
                    self.join_selected()
                    return
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.state = "online"
            elif event.key == pygame.K_DOWN and servers:
                self.selected_idx = min(self.selected_idx + 1, len(servers) - 1)
            elif event.key == pygame.K_UP and servers:
                self.selected_idx = max(self.selected_idx - 1, 0)
            elif event.key == pygame.K_RETURN and servers:
                self.join_selected()

    # ── Boucle principale ────────────────────────────────────────────────────

    def run(self):
        while self.running:
            dt = self.clock.tick(60)
            self.t += dt * 0.001

            draw_forest_scene(self.screen, self.t)
            self.particles.update()
            self.particles.draw(self.screen)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.VIDEORESIZE:
                    nw = max(MIN_W, event.w)
                    nh = max(MIN_H, event.h)
                    self.screen = pygame.display.set_mode((nw, nh), pygame.RESIZABLE)
                    self.particles.resize(nw, nh)
                elif self.state == "main":
                    self.handle_main(event)
                elif self.state == "online":
                    self.handle_online(event)
                elif self.state == "solo":
                    self.handle_solo(event)
                else:
                    self.handle_join(event)

            if self.state == "main":
                self.draw_main()
            elif self.state == "online":
                self.draw_online()
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
