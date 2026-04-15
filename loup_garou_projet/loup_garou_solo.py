import random
from collections import Counter
import pygame

from loup_shared import MAX_PLAYERS, MIN_PLAYERS, build_roles, check_winner, serialize_players_for

BASE_W, BASE_H = 1240, 820
MIN_W, MIN_H = 980, 700
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
        img = font.render(self.text, True, WHITE if enabled else (150, 150, 160))
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


class WerewolfSoloGame:
    def __init__(self, player_name="Joueur", player_count=6, role_config=None):
        pygame.init()
        self.screen = pygame.display.set_mode((BASE_W, BASE_H), pygame.RESIZABLE)
        pygame.display.set_caption("Loup-Garou Solo")
        self.clock = pygame.time.Clock()
        self.running = True
        self.player_name = player_name
        self.total_players = max(MIN_PLAYERS, min(MAX_PLAYERS, int(player_count)))
        self.role_config = role_config or {"Loup-garou": 1, "Voyante": 1, "Sorcière": 1}
        self.player_id = 0
        self.players = []
        self.phase = "night"
        self.day_count = 0
        self.message = ""
        self.action_hint = ""
        self.selected_target = None
        self.winner = None
        self.last_deaths = []
        self.night_target_name = None
        self.seer_result = None
        self.witch_heal_used = False
        self.witch_poison_used = False
        self.pending_night = {}
        self.start_btn = Button("NOUVELLE PARTIE", (90, 120, 80), (110, 145, 95))
        self.vote_btn = Button("VALIDER", (55, 85, 125), (75, 105, 155))
        self.skip_btn = Button("PASSER", (120, 85, 60), (150, 105, 75))
        self.player_rects = []
        self.compute_layout()
        self.setup_game()

    def fonts(self):
        w, h = self.screen.get_size()
        scale = min(w / BASE_W, h / BASE_H)
        return {
            "small": pygame.font.SysFont("arial", max(16, int(19 * scale))),
            "medium": pygame.font.SysFont("arial", max(22, int(26 * scale))),
            "big": pygame.font.SysFont("arial", max(30, int(38 * scale))),
            "title": pygame.font.SysFont("arial", max(40, int(52 * scale)), bold=True),
        }

    def compute_layout(self):
        w, h = self.screen.get_size()
        self.top_rect = pygame.Rect(20, 20, w - 40, 90)
        self.left_rect = pygame.Rect(20, 130, int(w * 0.42), h - 200)
        self.right_rect = pygame.Rect(self.left_rect.right + 20, 130, w - self.left_rect.width - 60, h - 200)
        self.bottom_rect = pygame.Rect(20, h - 60, w - 40, 40)
        btn_w = min(240, self.right_rect.width - 40)
        self.start_btn.set_rect((self.right_rect.x + 20, self.right_rect.bottom - 60, btn_w, 44))
        self.vote_btn.set_rect((self.right_rect.x + 20, self.right_rect.bottom - 60, btn_w, 44))
        self.skip_btn.set_rect((self.right_rect.x + 20 + btn_w + 14, self.right_rect.bottom - 60, max(140, self.right_rect.width - btn_w - 54), 44))

    def setup_game(self):
        roles = build_roles(self.total_players, self.role_config)
        self.players = []
        for i in range(self.total_players):
            name = self.player_name if i == 0 else f"IA {i}"
            self.players.append({
                "id": i,
                "name": name,
                "role": roles[i],
                "alive": True,
                "revealed_role": None,
            })
        self.phase = "night"
        self.day_count = 1
        self.message = "La nuit commence."
        self.action_hint = ""
        self.selected_target = None
        self.winner = None
        self.last_deaths = []
        self.night_target_name = None
        self.seer_result = None
        self.witch_heal_used = False
        self.witch_poison_used = False
        self.pending_night = {"seer_done": False, "witch_done": False}
        self.run_ai_night_until_player()

    def current_player(self):
        return self.players[self.player_id]

    def current_role(self):
        return self.current_player()["role"]

    def alive_ids(self):
        return [p["id"] for p in self.players if p["alive"]]

    def human_can_act(self):
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
        if role == "Sorcière" and not self.pending_night.get("witch_done"):
            return True
        return False

    def random_target(self, exclude=None):
        choices = [pid for pid in self.alive_ids() if pid != exclude]
        return random.choice(choices) if choices else None

    def resolve_night(self):
        deaths = set()
        if self.pending_night.get("wolf_target") is not None and not self.pending_night.get("saved"):
            deaths.add(self.pending_night["wolf_target"])
        if self.pending_night.get("poison_target") is not None:
            deaths.add(self.pending_night["poison_target"])
        for pid in deaths:
            if self.players[pid]["alive"]:
                self.players[pid]["alive"] = False
                self.players[pid]["revealed_role"] = self.players[pid]["role"]
        self.last_deaths = [self.players[pid]["name"] for pid in deaths]
        self.winner = check_winner(self.players)
        if self.winner:
            self.phase = "end"
            self.message = f"Victoire du camp : {self.winner}."
        else:
            self.phase = "day"
            self.message = "Jour : vote pour éliminer un joueur."
            self.action_hint = "Clique sur un joueur vivant puis valide ton vote."

    def run_ai_night_until_player(self):
        if self.winner:
            return
        self.pending_night = {"seer_done": False, "witch_done": False}
        wolves = [p for p in self.players if p["alive"] and p["role"] == "Loup-garou"]
        if wolves:
            votes = []
            for wolf in wolves:
                if wolf["id"] == self.player_id and wolf["alive"]:
                    self.action_hint = "Tu es loup-garou : choisis une victime."
                    return
                votes.append(self.random_target(exclude=wolf["id"]))
            votes = [v for v in votes if v is not None]
            if votes:
                self.pending_night["wolf_target"] = Counter(votes).most_common(1)[0][0]
                self.night_target_name = self.players[self.pending_night["wolf_target"]]["name"]
        seer = next((p for p in self.players if p["alive"] and p["role"] == "Voyante"), None)
        if seer:
            if seer["id"] == self.player_id:
                self.action_hint = "Tu es voyante : choisis un joueur pour voir son rôle."
                return
            target = self.random_target(exclude=seer["id"])
            self.pending_night["seer_done"] = True
            if target is not None:
                pass
        witch = next((p for p in self.players if p["alive"] and p["role"] == "Sorcière"), None)
        if witch:
            if witch["id"] == self.player_id and not self.pending_night.get("witch_done"):
                self.action_hint = "Tu es sorcière : tu peux sauver ou empoisonner."
                return
            if witch["id"] != self.player_id:
                if self.pending_night.get("wolf_target") is not None and not self.witch_heal_used and random.random() < 0.35:
                    self.pending_night["saved"] = True
                    self.witch_heal_used = True
                elif not self.witch_poison_used and random.random() < 0.2:
                    target = self.random_target(exclude=witch["id"])
                    if target is not None:
                        self.pending_night["poison_target"] = target
                        self.witch_poison_used = True
                self.pending_night["witch_done"] = True
        self.resolve_night()

    def run_ai_day(self):
        if self.phase != "day" or self.winner:
            return
        votes = {}
        for p in self.players:
            if not p["alive"] or p["id"] == self.player_id:
                continue
            target = self.random_target(exclude=p["id"])
            if target is not None:
                votes[p["id"]] = target
        if self.selected_target is not None:
            votes[self.player_id] = self.selected_target
        if len(votes) < len([p for p in self.players if p["alive"]]):
            return
        counts = {}
        for target in votes.values():
            counts[target] = counts.get(target, 0) + 1
        chosen = max(counts.items(), key=lambda x: (x[1], -x[0]))[0]
        self.players[chosen]["alive"] = False
        self.players[chosen]["revealed_role"] = self.players[chosen]["role"]
        self.last_deaths = [self.players[chosen]["name"]]
        self.winner = check_winner(self.players)
        if self.winner:
            self.phase = "end"
            self.message = f"{self.players[chosen]['name']} a été éliminé. Victoire du camp : {self.winner}."
        else:
            self.phase = "night"
            self.day_count += 1
            self.message = f"{self.players[chosen]['name']} a été éliminé. La nuit tombe..."
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
            self.seer_result = f"{self.players[self.selected_target]['name']} est {self.players[self.selected_target]['role']}."
        elif role == "Sorcière":
            self.pending_night["poison_target"] = self.selected_target
            self.pending_night["witch_done"] = True
            self.witch_poison_used = True
        if role in ("Loup-garou", "Voyante"):
            witch = next((p for p in self.players if p["alive"] and p["role"] == "Sorcière"), None)
            if witch and witch["id"] != self.player_id and not self.pending_night.get("witch_done"):
                if self.pending_night.get("wolf_target") is not None and not self.witch_heal_used and random.random() < 0.35:
                    self.pending_night["saved"] = True
                    self.witch_heal_used = True
                self.pending_night["witch_done"] = True
            self.resolve_night()
        elif role == "Sorcière":
            self.resolve_night()

    def skip_or_save(self):
        if self.current_role() != "Sorcière" or self.phase != "night":
            return
        if self.pending_night.get("wolf_target") is not None and not self.witch_heal_used:
            self.pending_night["saved"] = True
            self.witch_heal_used = True
        self.pending_night["witch_done"] = True
        self.resolve_night()

    def draw_player_list(self):
        f = self.fonts()
        draw_glass_panel(self.screen, self.left_rect, radius=22)
        draw_text(self.screen, "Joueurs", f["big"], WHITE, topleft=(self.left_rect.x + 18, self.left_rect.y + 14))
        self.player_rects = []
        y = self.left_rect.y + 72
        for p in serialize_players_for(self.player_id, self.players, reveal_all=self.winner is not None):
            rect = pygame.Rect(self.left_rect.x + 16, y, self.left_rect.width - 32, 48)
            selected = p["id"] == self.selected_target
            base = (42, 30, 60) if not selected else (80, 52, 100)
            pygame.draw.rect(self.screen, base, rect, border_radius=12)
            pygame.draw.rect(self.screen, BUTTON_BORDER, rect, 1, border_radius=12)
            status = "vivant" if p["alive"] else "mort"
            role = p.get("revealed_role") or p.get("role", "?") if (not p["alive"] or p["id"] == self.player_id or p.get("role") == "Loup-garou") else "?"
            draw_text(self.screen, p["name"], f["medium"], WHITE, topleft=(rect.x + 14, rect.y + 8))
            draw_text(self.screen, f"{status} - {role}", f["small"], CYAN if p["alive"] else RED, topleft=(rect.x + 14, rect.y + 25))
            self.player_rects.append((p["id"], rect))
            y += 56

    def draw_info(self):
        f = self.fonts()
        draw_glass_panel(self.screen, self.right_rect, radius=22)
        draw_text(self.screen, "Mode solo", f["big"], WHITE, topleft=(self.right_rect.x + 18, self.right_rect.y + 14))
        phase_label = {"night": f"Nuit {self.day_count}", "day": f"Jour {self.day_count}", "end": "Fin de partie"}.get(self.phase, self.phase)
        draw_text(self.screen, phase_label, f["medium"], GOLD, topleft=(self.right_rect.x + 20, self.right_rect.y + 70))
        draw_text(self.screen, f"Ton rôle : {self.current_role()}", f["medium"], CYAN, topleft=(self.right_rect.x + 20, self.right_rect.y + 110))
        draw_text(self.screen, self.message, f["small"], WHITE, topleft=(self.right_rect.x + 20, self.right_rect.y + 150))
        if self.action_hint:
            draw_text(self.screen, self.action_hint, f["small"], GOLD, topleft=(self.right_rect.x + 20, self.right_rect.y + 180))
        if self.seer_result:
            draw_text(self.screen, self.seer_result, f["small"], GREEN, topleft=(self.right_rect.x + 20, self.right_rect.y + 210))
        if self.last_deaths:
            draw_text(self.screen, "Derniers éliminés : " + ", ".join(self.last_deaths), f["small"], RED, topleft=(self.right_rect.x + 20, self.right_rect.y + 240))
        y = self.right_rect.y + 290
        for line in [
            f"Joueurs totaux : {self.total_players}",
            "Les IA jouent automatiquement.",
            "Tu peux refaire une partie à la fin.",
        ]:
            draw_text(self.screen, line, f["small"], WHITE, topleft=(self.right_rect.x + 20, y))
            y += 28
        mouse = pygame.mouse.get_pos()
        if self.phase == "end":
            self.start_btn.draw(self.screen, f["small"], mouse, enabled=True)
        else:
            self.vote_btn.draw(self.screen, f["small"], mouse, enabled=self.human_can_act() and self.selected_target is not None)
            if self.phase == "night" and self.current_role() == "Sorcière":
                self.skip_btn.text = "SAUVER" if self.pending_night.get("wolf_target") is not None and not self.witch_heal_used else "PASSER"
                self.skip_btn.draw(self.screen, f["small"], mouse, enabled=self.human_can_act())

    def draw(self):
        draw_vertical_gradient(self.screen, BG_TOP, BG_BOTTOM)
        f = self.fonts()
        draw_glass_panel(self.screen, self.top_rect, radius=22)
        draw_text(self.screen, "LOUP-GAROU SOLO", f["title"], WHITE, center=(self.top_rect.centerx, self.top_rect.y + 32))
        draw_text(self.screen, "Affronte des IA dans une partie locale", f["small"], CYAN, center=(self.top_rect.centerx, self.top_rect.y + 68))
        self.draw_player_list()
        self.draw_info()
        draw_text(self.screen, "Clique sur un joueur vivant pour le cibler.", f["small"], WHITE, center=self.bottom_rect.center)

    def handle_event(self, event):
        if event.type == pygame.VIDEORESIZE:
            self.screen = pygame.display.set_mode((max(MIN_W, event.w), max(MIN_H, event.h)), pygame.RESIZABLE)
            self.compute_layout()
            return
        if event.type != pygame.MOUSEBUTTONDOWN:
            return
        for pid, rect in self.player_rects:
            if rect.collidepoint(event.pos):
                if pid != self.player_id and self.players[pid]["alive"]:
                    self.selected_target = pid
                    return
        if self.phase == "end" and self.start_btn.is_clicked(event.pos):
            self.setup_game()
        elif self.vote_btn.is_clicked(event.pos):
            self.apply_human_action()
        elif self.phase == "night" and self.current_role() == "Sorcière" and self.skip_btn.is_clicked(event.pos):
            self.skip_or_save()

    def run(self):
        while self.running:
            self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                else:
                    self.handle_event(event)
            self.draw()
            pygame.display.flip()
        pygame.quit()
