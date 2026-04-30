"""
loup_garou_solo.py – Mode solo contre des IA
AMÉLIORATIONS :
  - Phase de nuit animée avec délais entre chaque action IA
  - Votes diurnes visibles : les IA votent un par un avec messages
  - IA communicante : messages stratégiques durant la discussion
  - Correction : "Sorcière" avec accent (correspondance avec ROLE_CATALOG)
"""
import random
from collections import Counter
import math

import pygame

from loup_shared import (MAX_PLAYERS, MIN_PLAYERS, build_roles, check_winner,
                          serialize_players_for, is_wolf_role)
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

NIGHT_BG_TOP = (6,  4, 14)
NIGHT_BG_BOT = (30, 16, 50)
DAY_BG_TOP   = (30, 55, 80)
DAY_BG_BOT   = (70, 100, 60)

ROLE_BADGE_COLORS = {
    "Loup-garou":          ROLE_WOLF_CLR,
    "Infect Père des Loups": ROLE_WOLF_CLR,
    "Voyante":             (50, 120, 200),
    "Sorcière":            (110, 50, 170),
    "Chasseur":            (130, 90, 40),
    "Villageois":          (40, 100, 60),
}

# Messages de discussion des IA selon leur rôle (les {} sont remplacés par des noms)
_WOLF_MSGS = [
    "Je pense que {} se comporte bizarrement...",
    "Moi je suis innocent. Regardez plutôt {}.",
    "Je suis villageois, faites-moi confiance.",
    "{} n'a pas l'air d'un villageois ordinaire.",
    "Je vote contre {}. Son comportement est suspect.",
]
_VILLAGE_MSGS = [
    "Je soupçonne {} d'être un loup...",
    "Quelqu'un a des informations sur {} ?",
    "{} n'a pas réagi normalement hier soir.",
    "Prudence, les loups sont parmi nous.",
    "Je fais confiance à {}, mais méfiez-vous de {}.",
    "Nous devons voter intelligemment aujourd'hui.",
]
_SEER_MSGS = [
    "J'ai des informations, mais je dois rester prudente.",
    "Je surveille {} de près, quelque chose cloche.",
    "Faisons attention à qui nous votons.",
    "Mon instinct me dit que {} est dangereux.",
]
_WITCH_MSGS = [
    "Je garde mes ressources pour le bon moment.",
    "{} semble suspect, je le surveille.",
    "Votons de manière réfléchie aujourd'hui.",
]


def _role_badge_col(role: str) -> tuple:
    return ROLE_BADGE_COLORS.get(role, MIST_PURPLE)


def _ai_chat_msg(player: dict, players: list) -> str:
    """Génère un message contextuel pour une IA selon son rôle."""
    role = player.get("role", "Villageois")
    alive = [p for p in players if p["alive"] and p["id"] != player["id"]]
    if not alive:
        return "..."

    if is_wolf_role(role):
        non_wolves = [p for p in alive if not is_wolf_role(p["role"])]
        pool = non_wolves if non_wolves else alive
        templates = _WOLF_MSGS
    elif role == "Voyante":
        pool = alive
        templates = _SEER_MSGS
    elif role == "Sorcière":
        pool = alive
        templates = _WITCH_MSGS
    else:
        pool = alive
        templates = _VILLAGE_MSGS

    t1 = random.choice(pool)["name"]
    others = [p for p in alive if p["name"] != t1]
    t2 = random.choice(others)["name"] if others else t1

    tpl = random.choice(templates)
    count = tpl.count("{}")
    if count == 2:
        return tpl.format(t1, t2)
    if count == 1:
        return tpl.format(t1)
    return tpl


class WerewolfSoloGame:
    def __init__(self, player_name="Joueur", player_count=6, role_config=None):
        pygame.init()
        self.screen = pygame.display.set_mode((BASE_W, BASE_H), pygame.RESIZABLE)
        pygame.display.set_caption("Loup-Garou – Solo")
        self.clock   = pygame.time.Clock()
        self.running = True
        self.t       = 0.0

        self.player_name   = player_name
        self.total_players = max(MIN_PLAYERS, min(MAX_PLAYERS, int(player_count)))
        self.role_config   = role_config  # None → DEFAULT_ROLE_CONFIG via normalize
        self.player_id     = 0

        # État de partie
        self.players: list       = []
        self.phase: str          = "night"
        self.day_count: int      = 0
        self.message: str        = ""
        self.action_hint: str    = ""
        self.selected_target     = None
        self.winner              = None
        self.last_deaths: list   = []
        self.night_target_name   = None
        self.seer_result         = None
        self.witch_heal_used     = False
        self.witch_poison_used   = False
        self.pending_night: dict = {}

        # Système de queue temporisée
        self.game_ms: int       = 0
        self.action_queue: list = []   # [(abs_ms, callable)]
        self.is_animating: bool = False

        # Log nuit + chat jour
        self.night_log: list = []   # messages affichés pendant la nuit
        self.chat_log: list  = []   # [{"author", "text", "wolf"}]
        self.day_votes: dict = {}   # {voter_id: target_id} visible

        self.btn_restart = Button("NOUVELLE PARTIE",  BTN_SUCCESS, BTN_SUCCESS_H, icon="")
        self.btn_vote    = Button("VALIDER MON VOTE", BTN_PRIMARY, BTN_PRIMARY_H, icon="")
        self.btn_skip    = Button("PASSER",           BTN_NEUTRAL, BTN_NEUTRAL_H)
        self.btn_save    = Button("SAUVER",           BTN_SUCCESS, BTN_SUCCESS_H)

        self.particles      = ParticleSystem(BASE_W, BASE_H, 30)
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
        self.left_rect   = pygame.Rect(pad, 104, int(w * 0.34), h - 170)
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

    # ── Queue temporisée ──────────────────────────────────────────────────────

    def schedule(self, delay_ms: float, fn):
        self.action_queue.append((self.game_ms + delay_ms, fn))
        self.action_queue.sort(key=lambda x: x[0])

    def update(self, dt_ms: float):
        self.game_ms += dt_ms
        while self.action_queue and self.action_queue[0][0] <= self.game_ms:
            _, fn = self.action_queue.pop(0)
            fn()

    # ── Helpers logs ──────────────────────────────────────────────────────────

    def night_msg(self, msg: str):
        self.night_log.append(msg)
        if len(self.night_log) > 10:
            self.night_log.pop(0)

    def add_chat(self, author: str, text: str, wolf: bool = False):
        self.chat_log.append({"author": author, "text": text, "wolf": wolf})
        if len(self.chat_log) > 40:
            self.chat_log.pop(0)

    # ── Initialisation ────────────────────────────────────────────────────────

    def setup_game(self):
        try:
            roles = build_roles(self.total_players, self.role_config)
        except ValueError:
            self.role_config = None
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
        self.message           = "La nuit s'étend sur le village..."
        self.action_hint       = ""
        self.selected_target   = None
        self.winner            = None
        self.last_deaths       = []
        self.night_target_name = None
        self.seer_result       = None
        self.witch_heal_used   = False
        self.witch_poison_used = False
        self.pending_night     = {"seer_done": False, "witch_done": False}
        self.action_queue      = []
        self.game_ms           = 0
        self.is_animating      = True
        self.night_log         = []
        self.chat_log          = []
        self.day_votes         = {}

        self.add_chat("Système", "Bonne chance ! Les rôles ont été distribués.", False)
        self._start_night()

    def current_player(self):    return self.players[self.player_id]
    def current_role(self) -> str: return self.current_player()["role"]

    def alive_ids(self) -> list:
        return [p["id"] for p in self.players if p["alive"]]

    def human_can_act(self) -> bool:
        if not self.current_player()["alive"] or self.winner or self.is_animating:
            return False
        if self.phase == "day":
            return True
        if self.phase != "night":
            return False
        role = self.current_role()
        if is_wolf_role(role):
            return True
        if role == "Voyante" and not self.pending_night.get("seer_done"):
            return True
        if role == "Sorcière" and not self.pending_night.get("witch_done"):
            return True
        return False

    def random_target(self, exclude=None):
        choices = [pid for pid in self.alive_ids() if pid != exclude]
        return random.choice(choices) if choices else None

    # ── Phase de nuit ─────────────────────────────────────────────────────────

    def _start_night(self):
        self.is_animating  = True
        self.action_hint   = ""
        self.seer_result   = None
        self.night_log     = []
        self.pending_night = {"seer_done": False, "witch_done": False}
        self.night_target_name = None
        t = 0

        self.schedule(t, lambda: self.night_msg("Le village s'endort..."))
        t += 1200

        wolves = [p for p in self.players if p["alive"] and is_wolf_role(p["role"])]
        if wolves:
            self.schedule(t, lambda: self.night_msg("Les loups-garous se réveillent..."))
            t += 900
            if any(w["id"] == self.player_id for w in wolves):
                self.schedule(t, self._pause_human_wolf)
                # _resume_after_human() continuera la chaîne
            else:
                def _wolves_act(wlist=wolves):
                    votes = []
                    for w in wlist:
                        tid = self.random_target(exclude=w["id"])
                        if tid is not None:
                            votes.append(tid)
                    if votes:
                        chosen = Counter(votes).most_common(1)[0][0]
                        self.pending_night["wolf_target"] = chosen
                        self.night_target_name = self.players[chosen]["name"]
                        self.night_msg("Les loups ont choisi leur victime dans l'ombre...")
                    else:
                        self.night_msg("Les loups ne trouvent pas de cible.")
                self.schedule(t, _wolves_act)
                t += 1600
                self.schedule(t, lambda: self.night_msg("Les loups-garous se rendorment."))
                t += 900
                self._chain_seer(t)
        else:
            self._chain_seer(t)

    def _chain_seer(self, t: int):
        seer = next((p for p in self.players if p["alive"] and p["role"] == "Voyante"), None)
        if not seer:
            self._chain_witch(t)
            return
        self.schedule(t, lambda: self.night_msg("La Voyante se réveille..."))
        t += 900
        if seer["id"] == self.player_id:
            self.schedule(t, self._pause_human_seer)
        else:
            def _seer_act(s=seer):
                self.pending_night["seer_done"] = True
                tid = self.random_target(exclude=s["id"])
                if tid is not None:
                    self.night_msg("La Voyante scrute les âmes dans le noir...")
            self.schedule(t, _seer_act)
            t += 1400
            self.schedule(t, lambda: self.night_msg("La Voyante se rendort."))
            t += 900
            self._chain_witch(t)

    def _chain_witch(self, t: int):
        witch = next((p for p in self.players if p["alive"] and p["role"] == "Sorcière"), None)
        if not witch:
            self._chain_end(t)
            return
        self.schedule(t, lambda: self.night_msg("La Sorcière se réveille..."))
        t += 900
        if witch["id"] == self.player_id:
            self.schedule(t, self._pause_human_witch)
        else:
            def _witch_act():
                wolf_tgt = self.pending_night.get("wolf_target")
                if wolf_tgt is not None and not self.witch_heal_used and random.random() < 0.35:
                    self.pending_night["saved"] = True
                    self.witch_heal_used = True
                    self.night_msg("La Sorcière hésite... et utilise sa potion de soin.")
                elif not self.witch_poison_used and random.random() < 0.20:
                    tid = self.random_target(exclude=witch["id"])
                    if tid is not None:
                        self.pending_night["poison_target"] = tid
                        self.witch_poison_used = True
                        self.night_msg("La Sorcière prépare sa potion de mort...")
                else:
                    self.night_msg("La Sorcière observe et ne fait rien.")
                self.pending_night["witch_done"] = True
            self.schedule(t, _witch_act)
            t += 1600
            self.schedule(t, lambda: self.night_msg("La Sorcière se rendort."))
            t += 900
            self._chain_end(t)

    def _chain_end(self, t: int):
        self.schedule(t, self._resolve_night)

    # Attentes humain

    def _pause_human_wolf(self):
        self.is_animating = False
        self.action_hint  = "Tu es loup-garou : désigne une victime parmi les vivants."

    def _pause_human_seer(self):
        self.is_animating = False
        self.action_hint  = "Tu es Voyante : choisis un joueur pour voir son rôle."

    def _pause_human_witch(self):
        self.is_animating = False
        wolf_tgt = self.pending_night.get("wolf_target")
        if wolf_tgt is not None:
            victim = self.players[wolf_tgt]["name"]
            self.action_hint = (f"Tu es Sorcière : {victim} a été visé par les loups. "
                                f"Sauver ou empoisonner ?")
        else:
            self.action_hint = "Tu es Sorcière : personne n'est visé. Utilise ton poison ?"

    def _resume_after_human(self):
        """Reprend la chaîne de nuit après une action humaine."""
        role = self.current_role()
        self.is_animating = True
        self.action_hint  = ""
        t = 0
        if is_wolf_role(role):
            self.schedule(t, lambda: self.night_msg("Les loups-garous se rendorment."))
            t += 900
            self._chain_seer(t)
        elif role == "Voyante":
            self.schedule(t, lambda: self.night_msg("La Voyante se rendort."))
            t += 900
            self._chain_witch(t)
        elif role == "Sorcière":
            self.schedule(t, lambda: self.night_msg("La Sorcière se rendort."))
            t += 900
            self._chain_end(t)
        else:
            self._chain_end(t)

    def _resolve_night(self):
        deaths: set = set()
        if (self.pending_night.get("wolf_target") is not None
                and not self.pending_night.get("saved")):
            deaths.add(self.pending_night["wolf_target"])
        if self.pending_night.get("poison_target") is not None:
            deaths.add(self.pending_night["poison_target"])
        for pid in deaths:
            if self.players[pid]["alive"]:
                self.players[pid]["alive"]         = False
                self.players[pid]["revealed_role"] = self.players[pid]["role"]
        self.last_deaths = [self.players[pid]["name"] for pid in deaths]
        self.winner = check_winner(self.players)
        if self.winner:
            self.phase   = "end"
            self.message = f"Victoire du camp : {self.winner} !"
            self.is_animating = False
            return
        self.phase = "day"
        if self.last_deaths:
            victims = ", ".join(self.last_deaths)
            self.message = f"Au petit matin... {victims} est retrouvé mort."
            self.add_chat("Système", f"{victims} a été éliminé cette nuit.", False)
        else:
            self.message = "Le village se réveille — personne n'est mort cette nuit !"
            self.add_chat("Système", "Personne n'est mort cette nuit.", False)
        self.selected_target = None
        self.day_votes       = {}
        self._start_day()

    # ── Phase de jour ─────────────────────────────────────────────────────────

    def _start_day(self):
        """Discussion des IA puis ouverture du vote."""
        self.is_animating = True
        t = 0
        ai_speakers = [p for p in self.players if p["alive"] and p["id"] != self.player_id]
        random.shuffle(ai_speakers)
        speakers = ai_speakers[:min(4, len(ai_speakers))]
        for sp in speakers:
            def _say(player=sp):
                msg = _ai_chat_msg(player, self.players)
                self.add_chat(player["name"], msg, is_wolf_role(player.get("role", "")))
            self.schedule(t, _say)
            t += random.randint(1000, 1800)
        self.schedule(t, self._open_vote)

    def _open_vote(self):
        self.message = "C'est l'heure du vote ! Qui est le loup ?"
        if not self.current_player()["alive"]:
            # Joueur mort → IA votent directement
            self.add_chat("Système", "Tu es éliminé. Le village vote sans toi.", False)
            self.is_animating = True
            self._ai_votes()
        else:
            self.action_hint = "Clique sur un joueur vivant puis valide ton vote."
            self.is_animating = False

    def _ai_votes(self):
        """Les IA votent une par une avec animation."""
        self.is_animating = True
        t = 0
        ai_voters = [p for p in self.players
                     if p["alive"] and p["id"] != self.player_id
                     and p["id"] not in self.day_votes]
        random.shuffle(ai_voters)
        for voter in ai_voters:
            def _vote(v=voter):
                # Loup : préfère cibler des non-loups
                if is_wolf_role(v["role"]):
                    pool = [pid for pid in self.alive_ids()
                            if pid != v["id"] and not is_wolf_role(self.players[pid]["role"])]
                    if not pool:
                        pool = [pid for pid in self.alive_ids() if pid != v["id"]]
                else:
                    pool = [pid for pid in self.alive_ids() if pid != v["id"]]
                if not pool:
                    return
                tid = random.choice(pool)
                self.day_votes[v["id"]] = tid
                tgt_name = self.players[tid]["name"]
                self.add_chat(v["name"], f"Je vote contre {tgt_name}.",
                              is_wolf_role(v.get("role", "")))
            self.schedule(t, _vote)
            t += random.randint(700, 1300)
        self.schedule(t + 500, self._resolve_day)

    def _resolve_day(self):
        alive_count = sum(1 for p in self.players if p["alive"])
        # Remplir les votes manquants (sécurité)
        for p in self.players:
            if p["alive"] and p["id"] not in self.day_votes:
                tid = self.random_target(exclude=p["id"])
                if tid is not None:
                    self.day_votes[p["id"]] = tid
        counts: dict = {}
        for tgt in self.day_votes.values():
            counts[tgt] = counts.get(tgt, 0) + 1
        chosen = max(counts.items(), key=lambda x: (x[1], -x[0]))[0]
        self.players[chosen]["alive"]         = False
        self.players[chosen]["revealed_role"] = self.players[chosen]["role"]
        self.last_deaths = [self.players[chosen]["name"]]
        role_reveal = self.players[chosen]["role"]
        self.add_chat("Système",
                      f"{self.players[chosen]['name']} est éliminé ! C'était un {role_reveal}.",
                      False)
        self.winner = check_winner(self.players)
        if self.winner:
            self.phase   = "end"
            self.message = (f"{self.players[chosen]['name']} éliminé. "
                            f"Victoire : {self.winner} !")
            self.is_animating = False
            return
        self.phase      = "night"
        self.day_count += 1
        self.message    = f"{self.players[chosen]['name']} éliminé. La nuit tombe..."
        self.selected_target = None
        self.day_votes  = {}
        self.schedule(900, self._start_night)

    # ── Actions humaines ──────────────────────────────────────────────────────

    def apply_human_action(self):
        role = self.current_role()
        if self.phase == "day":
            if self.selected_target is None:
                return
            tid = self.selected_target
            self.day_votes[self.player_id] = tid
            self.add_chat(self.player_name,
                          f"Je vote contre {self.players[tid]['name']}.", False)
            self.selected_target = None
            self.is_animating = True
            self._ai_votes()
            return
        if self.phase != "night" or self.selected_target is None:
            return
        if is_wolf_role(role):
            self.pending_night["wolf_target"] = self.selected_target
            self.night_target_name = self.players[self.selected_target]["name"]
            self.night_msg(f"Tu as désigné ta victime.")
        elif role == "Voyante":
            self.pending_night["seer_done"] = True
            tgt = self.selected_target
            self.seer_result = (f"{self.players[tgt]['name']} "
                                f"est {self.players[tgt]['role']}.")
            self.night_msg("Tu as observé un joueur dans l'obscurité.")
        elif role == "Sorcière":
            self.pending_night["poison_target"] = self.selected_target
            self.pending_night["witch_done"]    = True
            self.witch_poison_used = True
            self.night_msg("Tu as utilisé ta potion de mort.")
        self.selected_target = None
        self._resume_after_human()

    def save_victim(self):
        if self.current_role() != "Sorcière" or self.phase != "night":
            return
        wolf_tgt = self.pending_night.get("wolf_target")
        if wolf_tgt is not None and not self.witch_heal_used:
            self.pending_night["saved"] = True
            self.witch_heal_used = True
            self.night_msg(f"Tu as sauvé {self.players[wolf_tgt]['name']} avec ta potion de soin !")
        self.pending_night["witch_done"] = True
        self.selected_target = None
        self._resume_after_human()

    def skip_witch(self):
        if self.current_role() != "Sorcière" or self.phase != "night":
            return
        self.night_msg("Tu passes ton tour de Sorcière.")
        self.pending_night["witch_done"] = True
        self.selected_target = None
        self._resume_after_human()

    # ── Dessin ────────────────────────────────────────────────────────────────

    def _draw_background(self):
        w, h = self.screen.get_size()
        is_day = (self.phase == "day")
        if is_day:
            draw_gradient_bg(self.screen, DAY_BG_TOP, DAY_BG_BOT)
            sx, sy = int(w * 0.82), int(h * 0.14)
            sr = int(min(w, h) * 0.06)
            for step in range(6):
                hr = sr + step * 5
                a  = max(0, 40 - step * 7)
                ss = pygame.Surface((hr * 2 + 4, hr * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(ss, (255, 230, 100, a), (hr + 2, hr + 2), hr)
                self.screen.blit(ss, (sx - hr - 2, sy - hr - 2))
            pygame.draw.circle(self.screen, (255, 240, 120), (sx, sy), sr)
            tree_col = (18, 48, 24)
        else:
            draw_gradient_bg(self.screen, NIGHT_BG_TOP, NIGHT_BG_BOT)
            draw_moon(self.screen, int(w * 0.84), int(h * 0.14),
                      int(min(w, h) * 0.065), self.t)
            for sx2, sy2, sz in [(int(w*.10), int(h*.08), 2), (int(w*.25), int(h*.05), 1),
                                  (int(w*.42), int(h*.12), 2), (int(w*.58), int(h*.06), 1)]:
                a  = int(150 + 60 * math.sin(self.t * 0.9 + sx2))
                ss = pygame.Surface((sz * 3, sz * 3), pygame.SRCALPHA)
                pygame.draw.circle(ss, (210, 215, 255, a), (sz + 1, sz + 1), max(1, sz))
                self.screen.blit(ss, (sx2 - sz - 1, sy2 - sz - 1))
            tree_col = (5, 4, 12)
        for xi, hi in [(0.0, 0.36), (0.08, 0.30), (0.17, 0.38), (0.55, 0.32),
                       (0.66, 0.40), (0.78, 0.34), (0.90, 0.36), (0.98, 0.30)]:
            draw_tree_silhouette(self.screen, int(xi * w), h, int(hi * h), tree_col)
        self.particles.update()
        self.particles.draw(self.screen)

    def _player_row(self, p: dict, rect: pygame.Rect, selected: bool):
        is_dead = not p["alive"]
        is_me   = (p["id"] == self.player_id)
        bg = (14, 10, 26) if is_dead else ((58, 36, 88) if selected else (26, 18, 46))
        pygame.draw.rect(self.screen, bg, rect, border_radius=14)
        bord = MIST_LIGHT if selected else (46, 38, 72)
        pygame.draw.rect(self.screen, bord, rect, 2, border_radius=14)

        f = self.fonts()
        my_role  = self.current_role()
        reveal   = (is_dead or is_me
                    or (is_wolf_role(my_role) and is_wolf_role(p.get("role", ""))))
        role_str = (p.get("revealed_role") or p.get("role") or "?") if reveal else "?"
        badge_col = _role_badge_col(role_str)

        badge = pygame.Rect(rect.x + 9, rect.y + 9, 40, 30)
        pygame.draw.rect(self.screen, badge_col, badge, border_radius=10)
        draw_text(self.screen,
                  role_str[:2].upper() if role_str != "?" else "?",
                  f["xs"], WHITE_SOFT, center=badge.center)

        name_col = GREY_DARK if is_dead else (GOLD_WARM if is_me else WHITE_SOFT)
        draw_text(self.screen, p["name"], f["small"], name_col,
                  topleft=(rect.x + 58, rect.y + 5))

        if is_dead:
            draw_text(self.screen, "Éliminé — " + role_str, f["xs"], WOLF_RED,
                      topleft=(rect.x + 58, rect.y + 26))
        elif self.phase == "day" and p["id"] in self.day_votes:
            tgt_id   = self.day_votes[p["id"]]
            tgt_name = self.players[tgt_id]["name"] if tgt_id < len(self.players) else "?"
            draw_text(self.screen, f"▶ {tgt_name}", f["xs"], GOLD_PALE,
                      topleft=(rect.x + 58, rect.y + 26))
        else:
            info = role_str if reveal else "Rôle inconnu"
            draw_text(self.screen, info, f["xs"], CYAN_COOL,
                      topleft=(rect.x + 58, rect.y + 26))

        if selected:
            pygame.draw.circle(self.screen, GOLD_WARM, (rect.right - 16, rect.centery), 6)
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
            rect  = pygame.Rect(self.left_rect.x + 10, y,
                                self.left_rect.width - 20, row_h)
            if y + row_h <= self.left_rect.bottom - 8:
                self._player_row(p, rect, p["id"] == self.selected_target)
            self.player_rects.append((p["id"], rect))
            y += row_h + 6

    def draw_info_panel(self):
        f  = self.fonts()
        is_day = (self.phase == "day")
        rw     = self.right_rect.width - 40

        panel = pygame.Surface((self.right_rect.width, self.right_rect.height), pygame.SRCALPHA)
        pcol  = (30, 50, 35, 205) if is_day else (22, 14, 38, 210)
        bcol  = (60, 100, 70, 160) if is_day else (90, 70, 130, 140)
        pygame.draw.rect(panel, pcol,
                         (0, 0, self.right_rect.width, self.right_rect.height), border_radius=22)
        pygame.draw.rect(panel, bcol,
                         (0, 0, self.right_rect.width, self.right_rect.height),
                         width=2, border_radius=22)
        self.screen.blit(panel, self.right_rect.topleft)

        # En-tête phase
        phase_labels = {
            "night": (f"Nuit {self.day_count}", MOON_SILVER),
            "day":   (f"Jour {self.day_count}",  GOLD_WARM),
            "end":   ("Fin de partie",            WOLF_RED),
        }
        ph_text, ph_col = phase_labels.get(self.phase, (self.phase, WHITE_SOFT))
        draw_text(self.screen, ph_text, f["big"], ph_col,
                  topleft=(self.right_rect.x + 20, self.right_rect.y + 12), shadow=True)

        # Badge rôle + indicateur animation
        role = self.current_role()
        rb   = pygame.Rect(self.right_rect.x + 20, self.right_rect.y + 58, 130, 30)
        pygame.draw.rect(self.screen, _role_badge_col(role), rb, border_radius=14)
        draw_text(self.screen, role, f["xs"], WHITE_SOFT, center=rb.center)
        if self.is_animating:
            dots = "." * (int(self.t * 2.5) % 4)
            draw_text(self.screen, f"En cours{dots}", f["xs"], GREY_DIM,
                      topleft=(rb.right + 12, self.right_rect.y + 64))

        y = self.right_rect.y + 102
        chat_reserve = 220  # px réservés en bas pour chat + boutons

        def line(txt, col):
            nonlocal y
            if not txt:
                return
            for l in wrap_text(txt, max(20, rw // 9)):
                if y + 18 > self.right_rect.bottom - chat_reserve:
                    return
                draw_text(self.screen, l, f["xs"], col,
                          topleft=(self.right_rect.x + 20, y))
                y += 18
            y += 3

        line(self.message, WHITE_SOFT)
        if self.action_hint:
            line(self.action_hint, GOLD_PALE)
        if self.seer_result:
            line(self.seer_result, CYAN_COOL)
        if self.last_deaths:
            line("Éliminés : " + ", ".join(self.last_deaths), WOLF_RED)

        # Log de nuit (messages séquentiels)
        if self.phase == "night" and self.night_log:
            sep_y = y + 4
            if sep_y < self.right_rect.bottom - chat_reserve:
                pygame.draw.line(self.screen, (60, 52, 90),
                                 (self.right_rect.x + 20, sep_y),
                                 (self.right_rect.right - 20, sep_y))
                y = sep_y + 10
            for msg in self.night_log[-6:]:
                if y + 17 > self.right_rect.bottom - chat_reserve:
                    break
                draw_text(self.screen, msg, f["xs"], MOON_SILVER,
                          topleft=(self.right_rect.x + 20, y))
                y += 17

        # ── Chat log ─────────────────────────────────────────────────────────
        chat_top = self.right_rect.bottom - 215
        chat_bot = self.right_rect.bottom - 68
        chat_h   = chat_bot - chat_top
        if chat_h > 20:
            pygame.draw.rect(self.screen, (14, 10, 28),
                             (self.right_rect.x + 10, chat_top,
                              self.right_rect.width - 20, chat_h),
                             border_radius=12)
            pygame.draw.rect(self.screen, (52, 40, 84),
                             (self.right_rect.x + 10, chat_top,
                              self.right_rect.width - 20, chat_h),
                             1, border_radius=12)
            draw_text(self.screen, "Discussion", f["xs"], GREY_DIM,
                      topleft=(self.right_rect.x + 16, chat_top + 4))
            line_h  = 34
            max_vis = max(1, (chat_h - 22) // line_h)
            visible = self.chat_log[-max_vis:]
            cy = chat_top + 20
            for entry in visible:
                if cy + line_h > chat_bot - 2:
                    break
                is_sys = (entry["author"] == "Système")
                a_col  = (200, 80, 80) if is_sys else (WOLF_RED if entry["wolf"] else GOLD_WARM)
                draw_text(self.screen, entry["author"] + ":", f["xs"], a_col,
                          topleft=(self.right_rect.x + 16, cy))
                max_c = max(10, (self.right_rect.width - 32) // 8)
                txt = entry["text"]
                if len(txt) > max_c:
                    txt = txt[:max_c - 2] + ".."
                draw_text(self.screen, txt, f["xs"], WHITE_SOFT,
                          topleft=(self.right_rect.x + 22, cy + 16))
                cy += line_h

        # Boutons
        mouse = pygame.mouse.get_pos()
        if self.phase == "end":
            self.btn_restart.draw(self.screen, f["small"], mouse)
        else:
            can_act = self.human_can_act() and self.selected_target is not None
            self.btn_vote.draw(self.screen, f["small"], mouse, enabled=can_act)
            if self.phase == "night" and role == "Sorcière":
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
        draw_glass_panel(self.screen, self.top_rect, radius=18)
        draw_text(self.screen, "LOUP-GAROU  —  MODE SOLO",
                  f["title"], MOON_SILVER,
                  center=(self.top_rect.centerx, self.top_rect.centery), shadow=True)
        self.draw_player_list()
        self.draw_info_panel()
        hint = ("En attente des IA..." if self.is_animating
                else "Clique sur un joueur vivant pour le cibler")
        draw_text(self.screen, hint, f["xs"], GREY_DIM,
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
                if pid != self.player_id and self.players[pid]["alive"] and not self.is_animating:
                    self.selected_target = pid
                return
        if self.phase == "end":
            if self.btn_restart.is_clicked(event.pos):
                self.setup_game()
        elif not self.is_animating:
            if self.btn_vote.is_clicked(event.pos):
                self.apply_human_action()
            elif self.phase == "night" and self.current_role() == "Sorcière":
                if self.btn_save.is_clicked(event.pos):
                    self.save_victim()
                elif self.btn_skip.is_clicked(event.pos):
                    self.skip_witch()

    # ── Boucle principale ────────────────────────────────────────────────────

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS)
            self.t += dt * 0.001
            self.update(float(dt))
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                else:
                    self.handle_event(event)
            self.draw()
            pygame.display.flip()
        pygame.display.quit()
