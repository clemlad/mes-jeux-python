"""
loup_garou_solo.py – Mode solo contre des IA
CORRECTIONS :
  - run() n'appelle plus pygame.quit() (seulement pygame.display.quit)
  - Thème visuel change selon phase nuit/jour (fond, couleurs)
  - Correction logique reveal pour loup-garou coéquipiers
  - Badges rôles colorés dans la liste
"""
import random
from collections import Counter
import math

import pygame

from loup_shared import MAX_PLAYERS, MIN_PLAYERS, build_roles, check_winner, serialize_players_for, is_wolf_role
from loup_ui_theme import (
    BG_DEEP, BG_TOP, BG_BOTTOM, BG_MID,
    WOLF_RED, WOLF_RED_DK, BLOOD_RED,
    MIST_PURPLE, MIST_LIGHT,
    GOLD_WARM, GOLD_PALE,
    CYAN_COOL, WHITE_SOFT, GREY_DIM, GREY_DARK,
    MOON_SILVER,
    BTN_PRIMARY, BTN_PRIMARY_H,
    BTN_DANGER, BTN_DANGER_H,
    BTN_SUCCESS, BTN_SUCCESS_H,
    BTN_NEUTRAL, BTN_NEUTRAL_H,
    ROLE_WOLF_CLR, ROLE_VILLAGE_CLR, ROLE_NEUTRAL_CLR,
    draw_gradient_bg, draw_glass_panel, draw_text, wrap_text,
    draw_moon, draw_tree_silhouette,
    ParticleSystem, Button,
    scaled_fonts,
)

BASE_W, BASE_H = 1280, 840
MIN_W,  MIN_H  = 980,  700
FPS = 60

# Couleurs thème nuit
NIGHT_BG_TOP    = (6,  4, 14)
NIGHT_BG_BOT    = (30, 16, 50)
# Couleurs thème jour
DAY_BG_TOP      = (30, 55, 80)
DAY_BG_BOT      = (70, 100, 60)

ROLE_BADGE_COLORS = {
    "Loup-garou":   ROLE_WOLF_CLR,
    "Infect Pere des Loups": ROLE_WOLF_CLR,
    "Voyante":      (50, 120, 200),
    "Sorciere":     (110, 50, 170),
    "Chasseur":     (130, 90, 40),
    "Villageois":   (40, 100, 60),
}


def _role_badge_col(role: str) -> tuple:
    return ROLE_BADGE_COLORS.get(role, MIST_PURPLE)


class WerewolfSoloGame:
    def __init__(self, player_name="Joueur", player_count=6, role_config=None):
        pygame.init()
        self.screen = pygame.display.set_mode((BASE_W, BASE_H), pygame.RESIZABLE)
        pygame.display.set_caption("Loup-Garou – Solo")
        self.clock = pygame.time.Clock()
        self.running = True
        self.t = 0.0

        self.player_name   = player_name
        self.total_players = max(MIN_PLAYERS, min(MAX_PLAYERS, int(player_count)))
        self.role_config   = role_config or {"Loup-garou": 1, "Voyante": 1, "Sorciere": 1}
        self.player_id     = 0

        self.players: list         = []
        self.phase: str            = "night"
        self.day_count: int        = 0
        self.message: str          = ""
        self.action_hint: str      = ""
        self.selected_target       = None
        self.winner                = None
        self.last_deaths: list     = []
        self.night_target_name     = None
        self.seer_result           = None
        self.witch_heal_used       = False
        self.witch_poison_used     = False
        self.pending_night: dict   = {}

        self.btn_restart = Button("NOUVELLE PARTIE", BTN_SUCCESS, BTN_SUCCESS_H, icon="")
        self.btn_vote    = Button("VALIDER",          BTN_PRIMARY, BTN_PRIMARY_H, icon="")
        self.btn_skip    = Button("PASSER",           BTN_NEUTRAL, BTN_NEUTRAL_H)
        self.btn_save    = Button("SAUVER",           BTN_SUCCESS, BTN_SUCCESS_H)

        self.particles   = ParticleSystem(BASE_W, BASE_H, 30)
        self.player_rects: list = []
        self.compute_layout()
        self.setup_game()

    # ── Fonts & Layout ────────────────────────────────────────────────────────

    def fonts(self) -> dict:
        w, h = self.screen.get_size()
        return scaled_fonts(w, h, BASE_W, BASE_H)

    def compute_layout(self):
        w, h = self.screen.get_size()
        pad = 16
        self.top_rect    = pygame.Rect(pad, pad, w - pad * 2, 72)
        self.left_rect   = pygame.Rect(pad, 104, int(w * 0.36), h - 170)
        self.right_rect  = pygame.Rect(self.left_rect.right + pad, 104,
                                       w - self.left_rect.width - pad * 3, h - 170)
        self.bottom_rect = pygame.Rect(pad, h - 50, w - pad * 2, 36)

        bw = min(240, self.right_rect.width - 40)
        bx = self.right_rect.x + 20
        by = self.right_rect.bottom - 60
        self.btn_restart.set_rect((bx, by, self.right_rect.width - 40, 46))
        self.btn_vote.set_rect   ((bx, by, bw, 46))
        skip_x = bx + bw + 10
        skip_w = max(80, self.right_rect.right - 20 - skip_x)
        self.btn_skip.set_rect   ((skip_x, by, skip_w, 46))
        self.btn_save.set_rect   ((skip_x, by, skip_w, 46))

    # ── Logique ───────────────────────────────────────────────────────────────

    def setup_game(self):
        try:
            roles = build_roles(self.total_players, self.role_config)
        except ValueError:
            # fallback config
            self.role_config = {"Loup-garou": 1, "Voyante": 1, "Sorciere": 1}
            roles = build_roles(self.total_players, self.role_config)

        self.players = [
            {"id": i,
             "name": self.player_name if i == 0 else f"IA {i}",
             "role": roles[i],
             "alive": True,
             "revealed_role": None}
            for i in range(self.total_players)
        ]
        self.phase             = "night"
        self.day_count         = 1
        self.message           = "La nuit s'etend sur le village..."
        self.action_hint       = ""
        self.selected_target   = None
        self.winner            = None
        self.last_deaths       = []
        self.night_target_name = None
        self.seer_result       = None
        self.witch_heal_used   = False
        self.witch_poison_used = False
        self.pending_night     = {"seer_done": False, "witch_done": False}
        self.run_ai_night_until_player()

    def current_player(self):   return self.players[self.player_id]
    def current_role(self) -> str: return self.current_player()["role"]

    def alive_ids(self) -> list:
        return [p["id"] for p in self.players if p["alive"]]

    def human_can_act(self) -> bool:
        if not self.current_player()["alive"] or self.winner:
            return False
        if self.phase == "day":
            return True
        if self.phase != "night":
            return False
        role = self.current_role()
        if role == "Loup-garou":
            return True
        if role == "Voyante" and not self.pending_night.get("seer_done"):
            return True
        if role == "Sorciere" and not self.pending_night.get("witch_done"):
            return True
        return False

    def random_target(self, exclude=None):
        choices = [pid for pid in self.alive_ids() if pid != exclude]
        return random.choice(choices) if choices else None

    def resolve_night(self):
        deaths: set = set()
        if (self.pending_night.get("wolf_target") is not None
                and not self.pending_night.get("saved")):
            deaths.add(self.pending_night["wolf_target"])
        if self.pending_night.get("poison_target") is not None:
            deaths.add(self.pending_night["poison_target"])
        for pid in deaths:
            if self.players[pid]["alive"]:
                self.players[pid]["alive"]        = False
                self.players[pid]["revealed_role"] = self.players[pid]["role"]
        self.last_deaths = [self.players[pid]["name"] for pid in deaths]
        self.winner = check_winner(self.players)
        if self.winner:
            self.phase   = "end"
            self.message = f"Victoire du camp : {self.winner} !"
        else:
            self.phase       = "day"
            self.message     = "Le soleil se leve. Le village doit voter."
            self.action_hint = "Clique sur un joueur vivant, puis valide ton vote."

    def run_ai_night_until_player(self):
        if self.winner:
            return
        self.pending_night = {"seer_done": False, "witch_done": False}
        wolves = [p for p in self.players if p["alive"] and p["role"] == "Loup-garou"]
        if wolves:
            votes = []
            for wolf in wolves:
                if wolf["id"] == self.player_id:
                    self.action_hint = "Tu es loup-garou : designe une victime."
                    return
                t = self.random_target(exclude=wolf["id"])
                if t is not None:
                    votes.append(t)
            if votes:
                self.pending_night["wolf_target"] = Counter(votes).most_common(1)[0][0]
                self.night_target_name = self.players[self.pending_night["wolf_target"]]["name"]

        seer = next((p for p in self.players if p["alive"] and p["role"] == "Voyante"), None)
        if seer:
            if seer["id"] == self.player_id:
                self.action_hint = "Tu es voyante : choisis un joueur pour voir son role."
                return
            self.pending_night["seer_done"] = True

        witch = next((p for p in self.players if p["alive"] and p["role"] == "Sorciere"), None)
        if witch:
            if witch["id"] == self.player_id and not self.pending_night.get("witch_done"):
                self.action_hint = "Tu es sorciere : tu peux sauver ou empoisonner."
                return
            if witch["id"] != self.player_id:
                if (self.pending_night.get("wolf_target") is not None
                        and not self.witch_heal_used and random.random() < 0.35):
                    self.pending_night["saved"] = True
                    self.witch_heal_used = True
                elif not self.witch_poison_used and random.random() < 0.2:
                    t = self.random_target(exclude=witch["id"])
                    if t is not None:
                        self.pending_night["poison_target"] = t
                        self.witch_poison_used = True
                self.pending_night["witch_done"] = True

        self.resolve_night()

    def run_ai_day(self):
        if self.phase != "day" or self.winner:
            return
        votes: dict = {}
        alive_count = sum(1 for p in self.players if p["alive"])
        for p in self.players:
            if not p["alive"] or p["id"] == self.player_id:
                continue
            t = self.random_target(exclude=p["id"])
            if t is not None:
                votes[p["id"]] = t
        if self.selected_target is not None:
            votes[self.player_id] = self.selected_target
        if len(votes) < alive_count:
            return
        counts: dict = {}
        for tgt in votes.values():
            counts[tgt] = counts.get(tgt, 0) + 1
        chosen = max(counts.items(), key=lambda x: (x[1], -x[0]))[0]
        self.players[chosen]["alive"]        = False
        self.players[chosen]["revealed_role"] = self.players[chosen]["role"]
        self.last_deaths = [self.players[chosen]["name"]]
        self.winner = check_winner(self.players)
        if self.winner:
            self.phase   = "end"
            self.message = (f"{self.players[chosen]['name']} elimine. "
                            f"Victoire : {self.winner} !")
        else:
            self.phase      = "night"
            self.day_count += 1
            self.message    = f"{self.players[chosen]['name']} elimine. La nuit tombe..."
            self.selected_target = None
            self.run_ai_night_until_player()

    def apply_human_action(self):
        role = self.current_role()
        if self.phase == "day":
            self.run_ai_day()
            return
        if self.phase != "night" or self.selected_target is None:
            return
        if role == "Loup-garou":
            self.pending_night["wolf_target"] = self.selected_target
        elif role == "Voyante":
            self.pending_night["seer_done"] = True
            tgt = self.selected_target
            self.seer_result = (f"{self.players[tgt]['name']} "
                                f"est {self.players[tgt]['role']}.")
        elif role == "Sorciere":
            self.pending_night["poison_target"] = self.selected_target
            self.pending_night["witch_done"]    = True
            self.witch_poison_used = True

        if role in ("Loup-garou", "Voyante"):
            witch = next((p for p in self.players
                          if p["alive"] and p["role"] == "Sorciere"), None)
            if witch and witch["id"] != self.player_id and not self.pending_night.get("witch_done"):
                if (self.pending_night.get("wolf_target") is not None
                        and not self.witch_heal_used and random.random() < 0.35):
                    self.pending_night["saved"] = True
                    self.witch_heal_used = True
                self.pending_night["witch_done"] = True
        self.resolve_night()

    def skip_or_save(self):
        if self.current_role() != "Sorciere" or self.phase != "night":
            return
        if (self.pending_night.get("wolf_target") is not None and not self.witch_heal_used):
            self.pending_night["saved"] = True
            self.witch_heal_used = True
        self.pending_night["witch_done"] = True
        self.resolve_night()

    # ── Dessin ────────────────────────────────────────────────────────────────

    def _draw_background(self):
        """Fond qui change selon nuit/jour."""
        w, h = self.screen.get_size()
        is_day = (self.phase == "day")

        if is_day:
            # Ciel de jour (bleu-vert)
            draw_gradient_bg(self.screen, DAY_BG_TOP, DAY_BG_BOT)
            # Soleil
            sun_x, sun_y = int(w * 0.82), int(h * 0.14)
            sun_r = int(min(w, h) * 0.06)
            # Halo soleil
            for step in range(6):
                hr = sun_r + step * 5
                a = max(0, 40 - step * 7)
                ss = pygame.Surface((hr * 2 + 4, hr * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(ss, (255, 230, 100, a), (hr + 2, hr + 2), hr)
                self.screen.blit(ss, (sun_x - hr - 2, sun_y - hr - 2))
            pygame.draw.circle(self.screen, (255, 240, 120), (sun_x, sun_y), sun_r)
            pygame.draw.circle(self.screen, (240, 210, 80), (sun_x, sun_y), sun_r, 3)
            # Arbres de jour (vert sombre)
            day_tree = (18, 48, 24)
            for xi, hi in [(0.0, 0.36), (0.08, 0.30), (0.17, 0.38), (0.55, 0.32),
                           (0.66, 0.40), (0.78, 0.34), (0.90, 0.36), (0.98, 0.30)]:
                draw_tree_silhouette(self.screen, int(xi * w), h, int(hi * h), day_tree)
        else:
            # Fond de nuit
            draw_gradient_bg(self.screen, NIGHT_BG_TOP, NIGHT_BG_BOT)
            draw_moon(self.screen, int(w * 0.84), int(h * 0.14),
                      int(min(w, h) * 0.065), self.t)
            # Étoiles simples
            for sx, sy, sz in [
                (int(w * 0.1), int(h * 0.08), 2),
                (int(w * 0.25), int(h * 0.05), 1),
                (int(w * 0.42), int(h * 0.12), 2),
                (int(w * 0.58), int(h * 0.06), 1),
                (int(w * 0.70), int(h * 0.09), 2),
                (int(w * 0.35), int(h * 0.03), 1),
                (int(w * 0.90), int(h * 0.04), 1),
            ]:
                a = int(150 + 60 * math.sin(self.t * 0.9 + sx))
                ss = pygame.Surface((sz * 3, sz * 3), pygame.SRCALPHA)
                pygame.draw.circle(ss, (210, 215, 255, a), (sz + 1, sz + 1), max(1, sz))
                self.screen.blit(ss, (sx - sz - 1, sy - sz - 1))
            # Arbres nuit
            for xi, hi in [(0.0, 0.36), (0.08, 0.30), (0.17, 0.38), (0.55, 0.32),
                           (0.66, 0.40), (0.78, 0.34), (0.90, 0.36), (0.98, 0.30)]:
                draw_tree_silhouette(self.screen, int(xi * w), h, int(hi * h), (5, 4, 12))

        # Particules (lucioles la nuit, poussière le jour)
        self.particles.update()
        self.particles.draw(self.screen)

    def _player_row(self, p: dict, rect: pygame.Rect, selected: bool):
        is_dead = not p["alive"]
        is_me   = (p["id"] == self.player_id)

        # Fond ligne
        if is_dead:
            bg = (14, 10, 26)
        elif selected:
            bg = (58, 36, 88)
        else:
            bg = (26, 18, 46)
        pygame.draw.rect(self.screen, bg, rect, border_radius=14)
        bord = MIST_LIGHT if selected else (46, 38, 72)
        pygame.draw.rect(self.screen, bord, rect, 2, border_radius=14)

        f = self.fonts()
        # Déterminer si on affiche le rôle
        my_role = self.current_role()
        reveal = (is_dead or is_me
                  or (is_wolf_role(my_role) and is_wolf_role(p.get("role", ""))))
        role_str = (p.get("revealed_role") or p.get("role", "?")) if reveal else "?"
        badge_col = _role_badge_col(role_str)

        # Badge
        badge = pygame.Rect(rect.x + 9, rect.y + 9, 40, 30)
        pygame.draw.rect(self.screen, badge_col, badge, border_radius=10)
        draw_text(self.screen,
                  role_str[:2].upper() if role_str not in ("?",) else "?",
                  f["xs"], WHITE_SOFT, center=badge.center)

        # Nom
        name_col = GREY_DARK if is_dead else (GOLD_WARM if is_me else WHITE_SOFT)
        draw_text(self.screen, p["name"], f["small"], name_col,
                  topleft=(rect.x + 58, rect.y + 5))

        # Statut / rôle
        if is_dead:
            draw_text(self.screen, "Elimine - " + role_str, f["xs"], WOLF_RED,
                      topleft=(rect.x + 58, rect.y + 26))
        else:
            info = role_str if reveal else "Role inconnu"
            draw_text(self.screen, info, f["xs"], CYAN_COOL,
                      topleft=(rect.x + 58, rect.y + 26))

        # Marqueur sélectionné
        if selected:
            pygame.draw.circle(self.screen, GOLD_WARM, (rect.right - 16, rect.centery), 6)
        # Marqueur "moi"
        if is_me:
            draw_text(self.screen, "MOI", f["xs"], GOLD_WARM,
                      topleft=(rect.right - 38, rect.y + 5))

    def draw_player_list(self):
        f = self.fonts()
        draw_glass_panel(self.screen, self.left_rect, radius=22)
        draw_text(self.screen, "Joueurs", f["big"], MOON_SILVER,
                  topleft=(self.left_rect.x + 16, self.left_rect.y + 12), shadow=True)
        alive = sum(1 for p in self.players if p["alive"])
        draw_text(self.screen, f"{alive}/{len(self.players)} vivants",
                  f["xs"], GOLD_PALE,
                  topleft=(self.left_rect.x + 16, self.left_rect.y + 54))

        self.player_rects = []
        y = self.left_rect.y + 78
        data = serialize_players_for(self.player_id, self.players,
                                     reveal_all=(self.winner is not None))
        for p in data:
            row_h = 52
            rect = pygame.Rect(self.left_rect.x + 10, y,
                               self.left_rect.width - 20, row_h)
            # N'afficher que si dans les bornes du panneau
            if y + row_h <= self.left_rect.bottom - 8:
                self._player_row(p, rect, p["id"] == self.selected_target)
            self.player_rects.append((p["id"], rect))
            y += row_h + 6

    def draw_info_panel(self):
        f = self.fonts()
        is_day = (self.phase == "day")

        # Panneau avec teinte différente selon phase
        panel = pygame.Surface((self.right_rect.width, self.right_rect.height), pygame.SRCALPHA)
        panel_col = (30, 50, 35, 205) if is_day else (22, 14, 38, 210)
        pygame.draw.rect(panel, panel_col,
                         (0, 0, self.right_rect.width, self.right_rect.height),
                         border_radius=22)
        border_col = (60, 100, 70, 160) if is_day else (90, 70, 130, 140)
        pygame.draw.rect(panel, border_col,
                         (0, 0, self.right_rect.width, self.right_rect.height),
                         width=2, border_radius=22)
        self.screen.blit(panel, self.right_rect.topleft)

        # En-tête phase
        phase_labels = {
            "night": ("Nuit " + str(self.day_count), MOON_SILVER),
            "day":   ("Jour " + str(self.day_count),  GOLD_WARM),
            "end":   ("Fin de partie",                  WOLF_RED),
        }
        ph_text, ph_col = phase_labels.get(self.phase, (self.phase, WHITE_SOFT))
        # Icone selon phase
        icon = "Nuit" if self.phase == "night" else ("Jour" if self.phase == "day" else "Fin")
        draw_text(self.screen, ph_text, f["big"], ph_col,
                  topleft=(self.right_rect.x + 20, self.right_rect.y + 12), shadow=True)

        # Badge rôle joueur
        role = self.current_role()
        badge_col = _role_badge_col(role)
        rb = pygame.Rect(self.right_rect.x + 20, self.right_rect.y + 58, 130, 32)
        pygame.draw.rect(self.screen, badge_col, rb, border_radius=14)
        draw_text(self.screen, role, f["xs"], WHITE_SOFT, center=rb.center)

        y  = self.right_rect.y + 106
        dy = 26

        def line(txt, col):
            nonlocal y
            if not txt:
                return
            for l in wrap_text(txt, max(20, (self.right_rect.width - 40) // 9)):
                draw_text(self.screen, l, f["xs"], col,
                          topleft=(self.right_rect.x + 20, y))
                y += 19
            y += 4

        line(self.message, WHITE_SOFT)
        line(self.action_hint, GOLD_PALE)
        if self.seer_result:
            line(self.seer_result, CYAN_COOL)
        if self.last_deaths:
            line("Elimines : " + ", ".join(self.last_deaths), WOLF_RED)

        # Séparateur
        pygame.draw.line(self.screen, (60, 52, 90),
                         (self.right_rect.x + 20, y + 4),
                         (self.right_rect.right - 20, y + 4))
        y += 14
        line(f"Joueurs : {self.total_players}  |  IA jouent automatiquement.", GREY_DIM)

        # Boutons
        mouse = pygame.mouse.get_pos()
        if self.phase == "end":
            self.btn_restart.draw(self.screen, f["small"], mouse)
        else:
            can_vote = self.human_can_act() and self.selected_target is not None
            self.btn_vote.draw(self.screen, f["small"], mouse, enabled=can_vote)
            if self.phase == "night" and role == "Sorciere":
                wolf_tgt = self.pending_night.get("wolf_target")
                if wolf_tgt is not None and not self.witch_heal_used:
                    self.btn_save.draw(self.screen, f["small"], mouse,
                                       enabled=self.human_can_act())
                else:
                    self.btn_skip.draw(self.screen, f["small"], mouse,
                                       enabled=self.human_can_act())

    def draw(self):
        self._draw_background()
        f = self.fonts()
        # Barre du haut
        draw_glass_panel(self.screen, self.top_rect, radius=18)
        draw_text(self.screen, "LOUP-GAROU  -  MODE SOLO",
                  f["title"], MOON_SILVER,
                  center=(self.top_rect.centerx, self.top_rect.centery), shadow=True)
        self.draw_player_list()
        self.draw_info_panel()
        draw_text(self.screen,
                  "Clique sur un joueur vivant pour le cibler",
                  f["xs"], GREY_DIM,
                  center=self.bottom_rect.center)

    # ── Événements ───────────────────────────────────────────────────────────

    def handle_event(self, event):
        if event.type == pygame.VIDEORESIZE:
            self.screen = pygame.display.set_mode(
                (max(MIN_W, event.w), max(MIN_H, event.h)), pygame.RESIZABLE)
            self.compute_layout()
            return
        if event.type != pygame.MOUSEBUTTONDOWN:
            return
        for pid, rect in self.player_rects:
            if rect.collidepoint(event.pos):
                if pid != self.player_id and self.players[pid]["alive"]:
                    self.selected_target = pid
                return
        if self.phase == "end":
            if self.btn_restart.is_clicked(event.pos):
                self.setup_game()
        else:
            if self.btn_vote.is_clicked(event.pos):
                self.apply_human_action()
            elif self.phase == "night" and self.current_role() == "Sorciere":
                if self.btn_save.is_clicked(event.pos):
                    self.skip_or_save()
                elif self.btn_skip.is_clicked(event.pos):
                    self.skip_or_save()

    # ── Boucle ───────────────────────────────────────────────────────────────

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS)
            self.t += dt * 0.001
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                else:
                    self.handle_event(event)
            self.draw()
            pygame.display.flip()
        # NE PAS appeler pygame.quit() ici – géré par le Launcher
        pygame.display.quit()
