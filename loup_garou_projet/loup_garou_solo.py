
import random
from collections import Counter
import pygame

from loup_shared import MAX_PLAYERS, MIN_PLAYERS, build_roles, check_winner, get_role_def, serialize_players_for, team_of

BASE_W, BASE_H = 1320, 860
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


class WerewolfSoloGame:
    def __init__(self, player_name="Joueur", player_count=6, role_config=None):
        pygame.init()
        self.screen = pygame.display.set_mode((BASE_W, BASE_H), pygame.RESIZABLE)
        pygame.display.set_caption("Loup-Garou Solo")
        self.clock = pygame.time.Clock()
        self.running = True
        self.player_name = player_name
        self.total_players = max(MIN_PLAYERS, min(MAX_PLAYERS, int(player_count)))
        self.role_config = role_config or {"Loup-garou": 1, "Voyante": 1, "Sorciere": 1}
        self.player_id = 0
        self.players = []
        self.phase = "night"
        self.day_count = 0
        self.message = ""
        self.action_hint = ""
        self.selected_target = None
        self.winner = None
        self.last_deaths = []
        self.seer_result = None
        self.witch_heal_used = False
        self.witch_poison_used = False
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
        self.left_rect = pygame.Rect(20, 130, int(w * 0.40), h - 200)
        self.right_rect = pygame.Rect(self.left_rect.right + 20, 130, w - self.left_rect.width - 60, h - 200)
        self.bottom_rect = pygame.Rect(20, h - 60, w - 40, 40)
        self.start_btn.set_rect((self.right_rect.x + 20, self.right_rect.bottom - 56, self.right_rect.width - 40, 42))
        self.vote_btn.set_rect((self.right_rect.x + 20, self.right_rect.bottom - 108, self.right_rect.width - 40, 42))
        self.skip_btn.set_rect((self.right_rect.x + 20, self.right_rect.bottom - 56, self.right_rect.width - 40, 42))

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
                "lover_ids": [],
                "mentor_id": None,
                "renard_active": True,
                "doused": False,
                "charmed_by": None,
            })
        self.phase = "night"
        self.day_count = 1
        self.message = "La nuit commence."
        self.action_hint = "Cette version solo gère les nouveaux rôles en version simplifiée."
        self.selected_target = None
        self.winner = None
        self.last_deaths = []
        self.seer_result = None
        self.witch_heal_used = False
        self.witch_poison_used = False

    def current_player(self):
        return self.players[self.player_id]

    def current_role(self):
        return self.current_player()["role"]

    def alive_ids(self):
        return [p["id"] for p in self.players if p["alive"]]

    def human_can_act(self):
        return self.current_player()["alive"] and not self.winner

    def random_target(self, exclude=None):
        choices = [pid for pid in self.alive_ids() if pid != exclude]
        return random.choice(choices) if choices else None

    def kill_player(self, pid):
        if pid is None or not self.players[pid]["alive"]:
            return
        self.players[pid]["alive"] = False
        self.players[pid]["revealed_role"] = self.players[pid]["role"]
        self.last_deaths.append(self.players[pid]["name"])
        for lover_id in self.players[pid].get("lover_ids", []):
            if self.players[lover_id]["alive"]:
                self.kill_player(lover_id)
        for child in self.players:
            if child["alive"] and child["role"] == "Enfant sauvage" and child.get("mentor_id") == pid:
                child["role"] = "Loup-garou"

    def ai_night(self):
        wolves = [p for p in self.players if p["alive"] and team_of(p) == "Loups" and p["id"] != self.player_id]
        if wolves:
            target = self.random_target(exclude=wolves[0]["id"])
            if target is not None and self.players[target]["role"] == "Villageois maudit":
                self.players[target]["role"] = "Loup-garou"
            elif target is not None:
                self.kill_player(target)
        for p in self.players:
            if not p["alive"] or p["id"] == self.player_id:
                continue
            if p["role"] == "Sirène":
                for _ in range(3):
                    t = self.random_target(exclude=p["id"])
                    if t is not None:
                        self.players[t]["charmed_by"] = p["id"]
            elif p["role"] == "Pyroman":
                t = self.random_target(exclude=p["id"])
                if t is not None:
                    self.players[t]["doused"] = True
            elif p["role"] == "Cupidon" and self.day_count == 1:
                a = self.random_target(exclude=p["id"])
                b = self.random_target(exclude=p["id"])
                if a is not None and b is not None and a != b:
                    self.players[a]["lover_ids"] = [b]
                    self.players[b]["lover_ids"] = [a]
            elif p["role"] == "Enfant sauvage" and self.day_count == 1 and p["mentor_id"] is None:
                p["mentor_id"] = self.random_target(exclude=p["id"])
        self.winner = check_winner(self.players)
        if not self.winner:
            self.phase = "day"
            self.message = "Jour : vote pour éliminer un joueur."
            self.action_hint = "Clique sur un joueur vivant puis valide."

    def run_ai_day(self):
        votes = {}
        for p in self.players:
            if not p["alive"] or p["id"] == self.player_id:
                continue
            target = self.random_target(exclude=p["id"])
            if target is not None:
                votes[p["id"]] = target
        if self.selected_target is not None:
            votes[self.player_id] = self.selected_target
        alive_count = len([p for p in self.players if p["alive"]])
        if len(votes) < alive_count - 1:
            return
        counts = Counter(votes.values())
        chosen = max(counts.items(), key=lambda x: (x[1], -x[0]))[0]
        self.last_deaths = []
        self.kill_player(chosen)
        self.winner = check_winner(self.players)
        if self.winner:
            self.phase = "end"
            self.message = f"Victoire du camp : {self.winner}."
        else:
            self.phase = "night"
            self.day_count += 1
            self.message = f"{self.players[chosen]['name']} a été éliminé. La nuit tombe..."
            self.selected_target = None
            self.ai_night()

    def apply_human_action(self):
        if self.phase == "day":
            self.run_ai_day()
            return
        if self.phase == "night":
            role = self.current_role()
            if role == "Voyante" and self.selected_target is not None:
                self.seer_result = f"{self.players[self.selected_target]['name']} est {self.players[self.selected_target]['role']}."
            elif role in ("Loup-garou", "Infect Père des Loups") and self.selected_target is not None:
                if self.players[self.selected_target]["role"] == "Villageois maudit":
                    self.players[self.selected_target]["role"] = "Loup-garou"
                else:
                    self.kill_player(self.selected_target)
            elif role == "Sorciere" and self.selected_target is not None and not self.witch_poison_used and self.day_count > 1:
                self.kill_player(self.selected_target)
                self.witch_poison_used = True
            elif role == "Cupidon" and self.selected_target is not None:
                target2 = self.random_target(exclude=self.selected_target)
                if target2 is not None:
                    self.players[self.selected_target]["lover_ids"] = [target2]
                    self.players[target2]["lover_ids"] = [self.selected_target]
            elif role == "Enfant sauvage" and self.selected_target is not None:
                self.current_player()["mentor_id"] = self.selected_target
            self.winner = check_winner(self.players)
            if self.winner:
                self.phase = "end"
                self.message = f"Victoire du camp : {self.winner}."
            else:
                self.phase = "day"
                self.message = "Jour : vote pour éliminer un joueur."
                self.action_hint = "Clique sur un joueur vivant puis valide."

    def draw_player_list(self):
        f = self.fonts()
        draw_glass_panel(self.screen, self.left_rect, radius=22)
        draw_text(self.screen, "Joueurs", f["big"], WHITE, topleft=(self.left_rect.x + 18, self.left_rect.y + 14))
        self.player_rects = []
        y = self.left_rect.y + 72
        for p in serialize_players_for(self.player_id, self.players, reveal_all=self.winner is not None):
            rect = pygame.Rect(self.left_rect.x + 16, y, self.left_rect.width - 32, 56)
            selected = p["id"] == self.selected_target
            base = (42, 30, 60) if not selected else (80, 52, 100)
            pygame.draw.rect(self.screen, base, rect, border_radius=12)
            pygame.draw.rect(self.screen, BUTTON_BORDER, rect, 1, border_radius=12)
            status = "vivant" if p["alive"] else "mort"
            role = p.get("revealed_role") or p.get("role", "?") if (not p["alive"] or p["id"] == self.player_id or p.get("role") in ("Loup-garou", "Infect Père des Loups")) else "?"
            draw_text(self.screen, p["name"], f["medium"], WHITE, topleft=(rect.x + 14, rect.y + 8))
            draw_text(self.screen, f"{status} - {role}", f["small"], CYAN if p["alive"] else RED, topleft=(rect.x + 14, rect.y + 30))
            self.player_rects.append((p["id"], rect))
            y += 64

    def draw_info(self):
        f = self.fonts()
        draw_glass_panel(self.screen, self.right_rect, radius=22)
        draw_text(self.screen, "Mode solo", f["big"], WHITE, topleft=(self.right_rect.x + 18, self.right_rect.y + 14))
        phase_label = {"night": f"Nuit {self.day_count}", "day": f"Jour {self.day_count}", "end": "Fin de partie"}.get(self.phase, self.phase)
        draw_text(self.screen, phase_label, f["medium"], GOLD, topleft=(self.right_rect.x + 20, self.right_rect.y + 70))
        role = self.current_role()
        draw_text(self.screen, f"Ton rôle : {role}", f["medium"], CYAN, topleft=(self.right_rect.x + 20, self.right_rect.y + 110))
        role_def = get_role_def(role)
        y = self.right_rect.y + 150
        draw_text(self.screen, f"Camp : {role_def['camp']} | Aura : {role_def['aura']}", f["small"], WHITE, topleft=(self.right_rect.x + 20, y))
        y += 28
        for line in wrap_text(role_def["description"], f["small"], self.right_rect.width - 40):
            draw_text(self.screen, line, f["small"], WHITE, topleft=(self.right_rect.x + 20, y))
            y += 22
        y += 10
        for line in wrap_text(self.message, f["small"], self.right_rect.width - 40):
            draw_text(self.screen, line, f["small"], WHITE, topleft=(self.right_rect.x + 20, y))
            y += 22
        if self.action_hint:
            for line in wrap_text(self.action_hint, f["small"], self.right_rect.width - 40):
                draw_text(self.screen, line, f["small"], GOLD, topleft=(self.right_rect.x + 20, y))
                y += 22
        if self.seer_result:
            draw_text(self.screen, self.seer_result, f["small"], GREEN, topleft=(self.right_rect.x + 20, y))
            y += 28
        if self.last_deaths:
            draw_text(self.screen, "Derniers éliminés : " + ", ".join(self.last_deaths), f["small"], RED, topleft=(self.right_rect.x + 20, y))
            y += 28
        mouse = pygame.mouse.get_pos()
        if self.phase == "end":
            self.start_btn.draw(self.screen, f["small"], mouse, enabled=True)
        else:
            self.vote_btn.draw(self.screen, f["small"], mouse, enabled=self.human_can_act() and self.selected_target is not None)
            self.skip_btn.text = "PASSER LA NUIT" if self.phase == "night" else "PASSER"
            self.skip_btn.draw(self.screen, f["small"], mouse, enabled=self.human_can_act())

    def draw(self):
        draw_vertical_gradient(self.screen, BG_TOP, BG_BOTTOM)
        f = self.fonts()
        draw_glass_panel(self.screen, self.top_rect, radius=22)
        draw_text(self.screen, "LOUP-GAROU SOLO", f["title"], WHITE, center=(self.top_rect.centerx, self.top_rect.y + 32))
        draw_text(self.screen, "Version locale avec catalogue enrichi des rôles", f["small"], CYAN, center=(self.top_rect.centerx, self.top_rect.y + 68))
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
        elif self.skip_btn.is_clicked(event.pos) and self.phase == "night":
            self.ai_night()

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
