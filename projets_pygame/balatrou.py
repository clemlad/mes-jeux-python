"""
╔══════════════════════════════════════════════╗
║   BALTROU - Poker Roguelite  MDRRRRRRRRRR    ║
║          Version PYGAME                      ║
╚══════════════════════════════════════════════╝
Lancer: python3 baltrou_pygame.py
"""

import pygame
import random
import sys
import math
from enum import Enum
from typing import Optional

pygame.init()
pygame.font.init()

W, H = 1280, 800
screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
pygame.display.set_caption("BALTROU  MDRRRRRRRRRRRRRRRRRR")
clock = pygame.time.Clock()
FPS = 60
fullscreen = False

COL = {
    "bg":       (18, 14, 28),
    "bg2":      (28, 22, 42),
    "panel":    (34, 28, 52),
    "card_w":   (245, 238, 220),
    "card_sel": (255, 230, 80),
    "card_brd": (60, 50, 80),
    "red":      (220, 60, 60),
    "green":    (80, 200, 100),
    "gold":     (255, 200, 40),
    "blue":     (80, 140, 255),
    "purple":   (160, 80, 255),
    "orange":   (255, 150, 40),
    "white":    (240, 235, 225),
    "dim":      (100, 90, 120),
    "heart":    (220, 50, 70),
    "spade":    (40, 40, 60),
    "club":     (40, 80, 50),
    "diamond":  (60, 120, 255),   # BLEU
    "enhanced": (255, 215, 0),
    "btn":      (60, 50, 90),
    "btn_h":    (90, 75, 130),
    "btn_play": (50, 150, 80),
    "btn_disc": (160, 80, 30),
    "shop_bg":  (22, 18, 36),
    "joker_c":  (70, 60, 100),
    "mystique": (180, 0, 255),
    "troll":    (50, 200, 50),
}

def load_font(size, bold=False):
    try:
        return pygame.font.SysFont("dejavusans", size, bold=bold)
    except:
        return pygame.font.Font(None, size)

F = {
    "title":  load_font(48, True),
    "big":    load_font(32, True),
    "med":    load_font(22, True),
    "sm":     load_font(18),
    "xs":     load_font(14),
    "rank":   load_font(26, True),
    "suit":   load_font(22),
    "joker":  load_font(16, True),
}

class Suit(Enum):
    HEART   = ("hearts",   "heart",   COL["heart"])
    DIAMOND = ("diamond",  "diamond", COL["diamond"])
    SPADE   = ("spade",    "spade",   COL["spade"])
    CLUB    = ("club",     "club",    COL["club"])

    def __init__(self, symbol, key, color):
        self.symbol = symbol
        self.key    = key
        self.color  = color

SUIT_SYMBOLS = {
    "hearts":  chr(9829),
    "diamond": chr(9830),
    "spade":   chr(9824),
    "club":    chr(9827),
}

class Rank(Enum):
    TWO   = (2,  "2",  2)
    THREE = (3,  "3",  3)
    FOUR  = (4,  "4",  4)
    FIVE  = (5,  "5",  5)
    SIX   = (6,  "6",  6)
    SEVEN = (7,  "7",  7)
    EIGHT = (8,  "8",  8)
    NINE  = (9,  "9",  9)
    TEN   = (10, "10", 10)
    JACK  = (11, "J",  10)
    QUEEN = (12, "Q",  10)
    KING  = (13, "K",  10)
    ACE   = (14, "A",  11)

    def __init__(self, rank_val, display, chip_val):
        self.rank_val  = rank_val
        self.display   = display
        self.chip_val  = chip_val

class HandRank(Enum):
    HIGH_CARD       = (1,  "Carte Haute",         5,   1.0)
    ONE_PAIR        = (2,  "Une Paire",           10,  2.0)
    TWO_PAIR        = (3,  "Deux Paires",         20,  2.0)
    THREE_OF_A_KIND = (4,  "Brelan",              30,  3.0)
    STRAIGHT        = (5,  "Suite",               30,  4.0)
    FLUSH           = (6,  "Couleur",             35,  4.0)
    FULL_HOUSE      = (7,  "Full House",          40,  4.0)
    FOUR_OF_A_KIND  = (8,  "Carre",               60,  7.0)
    STRAIGHT_FLUSH  = (9,  "Quinte Flush",       100,  8.0)
    ROYAL_FLUSH     = (10, "Quinte Flush Royale", 200, 10.0)

    def __init__(self, rank, name_fr, base_chips, multiplier):
        self.rank_order  = rank
        self.name_fr     = name_fr
        self.base_chips  = base_chips
        self.multiplier  = multiplier

render_surf = pygame.Surface((W, H))

def get_scale_offset():
    sw, sh = screen.get_size()
    scale = min(sw / W, sh / H)
    ox = (sw - W * scale) / 2
    oy = (sh - H * scale) / 2
    return scale, ox, oy

def screen_to_game(mx, my):
    scale, ox, oy = get_scale_offset()
    return int((mx - ox) / scale), int((my - oy) / scale)

_orig_mouse_get_pos = pygame.mouse.get_pos
def _game_mouse_get_pos():
    mx, my = _orig_mouse_get_pos()
    return screen_to_game(mx, my)
pygame.mouse.get_pos = _game_mouse_get_pos

def _patch_event_pos(event):
    if hasattr(event, 'pos'):
        gx, gy = screen_to_game(event.pos[0], event.pos[1])
        d = event.__dict__.copy()
        d['pos'] = (gx, gy)
        return pygame.event.Event(event.type, d)
    return event

def toggle_fullscreen():
    global screen, fullscreen
    fullscreen = not fullscreen
    if fullscreen:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    else:
        screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)

class BalatroBackground:
    def __init__(self):
        self.time  = 0.0
        self.orbs  = [self._new_orb() for _ in range(12)]
        self.stars = [(random.randint(0,W), random.randint(0,H), random.uniform(0.3,1.0)) for _ in range(120)]
        self._grid = pygame.Surface((W,H), pygame.SRCALPHA)
        for gx in range(0,W,48): pygame.draw.line(self._grid,(255,255,255,8),(gx,0),(gx,H))
        for gy in range(0,H,48): pygame.draw.line(self._grid,(255,255,255,8),(0,gy),(W,gy))

    def _new_orb(self):
        return {"x":random.uniform(0,W),"y":random.uniform(0,H),"r":random.uniform(60,180),
                "vx":random.uniform(-0.3,0.3),"vy":random.uniform(-0.2,0.2),
                "phase":random.uniform(0,math.tau),"hue":random.choice([(120,50,200),(60,20,140),(200,50,100),(40,100,200)])}

    def update(self):
        self.time += 0.016
        for o in self.orbs:
            o["x"]+=o["vx"]; o["y"]+=o["vy"]
            if o["x"]<-200 or o["x"]>W+200: o["vx"]*=-1
            if o["y"]<-200 or o["y"]>H+200: o["vy"]*=-1

    def draw(self, surf):
        surf.fill(COL["bg"]); surf.blit(self._grid,(0,0))
        orb=pygame.Surface((W,H),pygame.SRCALPHA)
        for o in self.orbs:
            p=0.7+0.3*math.sin(self.time*1.2+o["phase"]); r=int(o["r"]*p); cx,cy=int(o["x"]),int(o["y"])
            for st in range(4,0,-1):
                f=st/4; a=int(30*f*p); sr=int(r*(2.0-f))
                s2=pygame.Surface((sr*2,sr*2),pygame.SRCALPHA)
                pygame.draw.circle(s2,(*o["hue"],a),(sr,sr),sr); orb.blit(s2,(cx-sr,cy-sr))
        surf.blit(orb,(0,0))
        for (sx,sy,br) in self.stars:
            tw=abs(math.sin(self.time*br*2)); a=int(40+80*tw*br); rs=1 if br<0.6 else 2
            s3=pygame.Surface((rs*2+2,rs*2+2),pygame.SRCALPHA)
            pygame.draw.circle(s3,(220,200,255,a),(rs+1,rs+1),rs); surf.blit(s3,(sx-rs,sy-rs))
        vign=pygame.Surface((W,H),pygame.SRCALPHA)
        for i in range(0,200,8):
            f=i/200; a=int(120*(1-f)); pygame.draw.rect(vign,(0,0,0,a),(i,i,W-2*i,H-2*i),8)
        surf.blit(vign,(0,0))

def draw_text(surf, text, font, color, x, y, center=False, right=False):
    s=font.render(text,True,color); r=s.get_rect()
    if center: r.center=(x,y)
    elif right: r.right=x; r.top=y
    else: r.topleft=(x,y)
    surf.blit(s,r); return r

def draw_rect_rounded(surf, color, rect, radius=10, alpha=255):
    s=pygame.Surface((rect[2],rect[3]),pygame.SRCALPHA)
    pygame.draw.rect(s,(*color,alpha),(0,0,rect[2],rect[3]),border_radius=radius)
    surf.blit(s,(rect[0],rect[1]))

def draw_border(surf, color, rect, width=2, radius=10):
    pygame.draw.rect(surf,color,rect,width,border_radius=radius)

def lerp_color(c1,c2,t):
    return tuple(int(c1[i]+(c2[i]-c1[i])*t) for i in range(3))

CARD_W, CARD_H = 72, 108

class Card:
    def __init__(self, rank: Rank, suit: Suit):
        self.rank=rank; self.suit=suit
        self.selected=False; self.enhanced=False
        self._hover=False; self._anim_y=0.0
        self.is_joker_wildcard=False

    def __repr__(self):
        return f"{self.rank.display}{SUIT_SYMBOLS[self.suit.symbol]}"

    @property
    def chip_val(self):
        return self.rank.chip_val*(2 if self.enhanced else 1)

    def draw(self, surf, x, y, small=False):
        cw=CARD_W if not small else 52; ch=CARD_H if not small else 78
        ay=int(self._anim_y)
        draw_rect_rounded(surf,(0,0,0),(x+3,y+ay+3,cw,ch),8,120)
        bg=COL["card_sel"] if self.selected else COL["card_w"]
        draw_rect_rounded(surf,bg,(x,y+ay,cw,ch),8)
        brd=COL["gold"] if self.selected else COL["card_brd"]
        draw_border(surf,brd,(x,y+ay,cw,ch),3 if self.selected else 1,8)
        sc=self.suit.color; rd=self.rank.display
        fn=F["rank"] if not small else F["sm"]; fs=F["suit"] if not small else F["xs"]
        sym=SUIT_SYMBOLS[self.suit.symbol]
        draw_text(surf,rd,fn,sc,x+5,y+ay+4)
        draw_text(surf,sym,fs,sc,x+5,y+ay+4+fn.get_height()-2)
        draw_text(surf,sym,load_font(28 if not small else 20),sc,x+cw//2,y+ay+ch//2,center=True)
        draw_text(surf,rd,fn,sc,x+cw-5,y+ay+ch-4-fn.get_height()*2,right=True)
        if self.enhanced: draw_text(surf,"*",F["xs"],COL["enhanced"],x+cw-14,y+ay+4)
        if self._hover and not self.selected:
            draw_border(surf,(200,200,100),(x-1,y+ay-1,cw+2,ch+2),1,9)

    def get_rect(self,x,y):
        return pygame.Rect(x,y+int(self._anim_y),CARD_W,CARD_H)


class WildcardJokerCard(Card):
    TROLL_CHANCE = 0.03

    def __init__(self):
        super().__init__(Rank.ACE, Suit.HEART)
        self.is_joker_wildcard=True; self.is_troll=False

    def check_troll_mutation(self):
        if not self.is_troll and random.random()<self.TROLL_CHANCE:
            self.is_troll=True; return True
        return False

    def draw(self, surf, x, y, small=False):
        cw=CARD_W if not small else 52; ch=CARD_H if not small else 78
        ay=int(self._anim_y)
        draw_rect_rounded(surf,(0,0,0),(x+3,y+ay+3,cw,ch),8,120)
        if self.is_troll: self._draw_troll(surf,x,y+ay,cw,ch)
        else: self._draw_wild(surf,x,y+ay,cw,ch)
        if self._hover and not self.selected:
            hc=COL["troll"] if self.is_troll else COL["mystique"]
            draw_border(surf,hc,(x-1,y+ay-1,cw+2,ch+2),1,9)

    def _draw_wild(self, surf, x, y, cw, ch):
        bg=(230,200,255) if not self.selected else COL["card_sel"]
        draw_rect_rounded(surf,bg,(x,y,cw,ch),8)
        draw_border(surf,COL["mystique"],(x,y,cw,ch),3 if self.selected else 2,8)
        draw_text(surf,"*",load_font(32),COL["mystique"],x+cw//2,y+ch//2,center=True)
        draw_text(surf,"?",F["rank"],COL["mystique"],x+5,y+4)
        draw_text(surf,"?",F["rank"],COL["mystique"],x+cw-5,y+ch-4-F["rank"].get_height()*2,right=True)
        draw_text(surf,"WILD",F["xs"],COL["mystique"],x+cw//2,y+ch-14,center=True)

    def _draw_troll(self, surf, x, y, cw, ch):
        draw_rect_rounded(surf,(20,45,20),(x,y,cw,ch),8)
        draw_border(surf,COL["troll"],(x,y,cw,ch),3,8)
        fx=x+cw//2; fy=y+ch//2-6
        pygame.draw.circle(surf,(100,180,80),(fx,fy),22)
        pygame.draw.circle(surf,(255,255,255),(fx-8,fy-5),6)
        pygame.draw.circle(surf,(255,255,255),(fx+8,fy-5),6)
        pygame.draw.circle(surf,(0,0,0),(fx-6,fy-4),3)
        pygame.draw.circle(surf,(0,0,0),(fx+9,fy-4),3)
        pygame.draw.line(surf,(0,0,0),(fx-14,fy-14),(fx-2,fy-12),2)
        pygame.draw.line(surf,(0,0,0),(fx+2,fy-12),(fx+14,fy-14),2)
        pts=[(fx-10,fy+10),(fx-5,fy+16),(fx,fy+18),(fx+5,fy+16),(fx+10,fy+10)]
        pygame.draw.lines(surf,(0,0,0),False,pts,2)
        pygame.draw.ellipse(surf,(150,100,70),(fx-5,fy+1,10,7))
        draw_text(surf,"XD",F["xs"],COL["troll"],x+cw//2,y+ch-14,center=True)

    def get_rect(self,x,y):
        return pygame.Rect(x,y+int(self._anim_y),CARD_W,CARD_H)


class PoissonDegueulasse(Card):
    CURSE_CHANCE = 0.15

    def __init__(self):
        super().__init__(Rank.TWO, Suit.CLUB)
        self.is_poisson=True; self.is_joker_wildcard=False

    def draw(self, surf, x, y, small=False):
        cw=CARD_W if not small else 52; ch=CARD_H if not small else 78; ay=int(self._anim_y)
        draw_rect_rounded(surf,(0,0,0),(x+3,y+ay+3,cw,ch),8,120)
        bg=(180,210,160) if not self.selected else (220,255,180)
        draw_rect_rounded(surf,bg,(x,y+ay,cw,ch),8)
        brd=COL["gold"] if self.selected else (80,140,60)
        draw_border(surf,brd,(x,y+ay,cw,ch),3 if self.selected else 2,8)
        fx=x+cw//2; fy=y+ay+ch//2-4
        pygame.draw.ellipse(surf,(60,120,80),(fx-18,fy-9,36,18))
        pygame.draw.polygon(surf,(60,120,80),[(fx+18,fy),(fx+28,fy-10),(fx+28,fy+10)])
        pygame.draw.circle(surf,(255,255,255),(fx-6,fy-2),4)
        pygame.draw.circle(surf,(0,0,0),(fx-5,fy-2),2)
        pygame.draw.circle(surf,(100,160,80),(fx-18,fy-14),3)
        pygame.draw.circle(surf,(100,160,80),(fx-12,fy-18),2)
        draw_text(surf,"FORCE",F["xs"],(60,140,60),x+cw//2,y+ay+ch-14,center=True)
        if self._hover and not self.selected:
            draw_border(surf,(150,220,100),(x-1,y+ay-1,cw+2,ch+2),1,9)

    def get_rect(self,x,y):
        return pygame.Rect(x,y+int(self._anim_y),CARD_W,CARD_H)


class Deck:
    def __init__(self):
        self._wildcard: Optional[WildcardJokerCard] = None
        self.cards: list[Card] = []
        self.reset()

    def reset(self):
        self.cards=[Card(r,s) for s in Suit for r in Rank]
        if self._wildcard is not None:
            new_wc=WildcardJokerCard()
            new_wc.is_troll=self._wildcard.is_troll
            self._wildcard=new_wc
            self.cards.append(new_wc)
        self.cards.append(PoissonDegueulasse())
        random.shuffle(self.cards)

    def add_wildcard(self):
        wc=WildcardJokerCard(); self._wildcard=wc
        self.cards.append(wc); random.shuffle(self.cards)

    def draw(self, n=1) -> list[Card]:
        result=[]
        for _ in range(n):
            if self.cards:
                card=self.cards.pop()
                if isinstance(card,WildcardJokerCard):
                    card.check_troll_mutation()
                    if card.is_troll and self._wildcard: self._wildcard.is_troll=True
                result.append(card)
        return result

    def remaining(self): return len(self.cards)
    def has_wildcard(self): return self._wildcard is not None


class HandEvaluator:
    @staticmethod
    def evaluate(cards: list[Card]) -> tuple[HandRank, list[Card]]:
        wildcards=[c for c in cards if isinstance(c,WildcardJokerCard)]
        normals=[c for c in cards if not isinstance(c,WildcardJokerCard)]
        if not wildcards: return HandEvaluator._eval(normals)
        best_hr,best_sc=HandEvaluator._eval(normals)
        for sub_r in Rank:
            for sub_s in Suit:
                fake=Card(sub_r,sub_s); test=normals+[fake]
                hr,sc=HandEvaluator._eval(test)
                if hr.rank_order>best_hr.rank_order:
                    best_hr=hr; best_sc=[wildcards[0] if c is fake else c for c in sc]
        return best_hr,best_sc

    @staticmethod
    def _eval(cards: list[Card]) -> tuple[HandRank, list[Card]]:
        if not cards: return HandRank.HIGH_CARD,[]
        sorted_c=sorted(cards,key=lambda c:c.rank.rank_val,reverse=True)
        ranks=[c.rank.rank_val for c in sorted_c]; suits=[c.suit for c in sorted_c]
        rg={}
        for c in sorted_c: rg.setdefault(c.rank.rank_val,[]).append(c)
        groups=sorted(rg.values(),key=lambda g:(len(g),g[0].rank.rank_val),reverse=True)
        freq=sorted([len(g) for g in groups],reverse=True)
        is_flush=len(cards)==5 and len(set(suits))==1
        is_straight=False; straight_cards=[]
        if len(cards)==5:
            ur=sorted(set(ranks),reverse=True)
            if len(ur)==5:
                if ur[0]-ur[-1]==4: is_straight=True; straight_cards=sorted_c
                elif ur==[14,5,4,3,2]:
                    is_straight=True
                    straight_cards=sorted(cards,key=lambda c:1 if c.rank.rank_val==14 else c.rank.rank_val,reverse=True)
        gc=[c for g in groups for c in g]
        if is_straight and is_flush:
            sv={c.rank.rank_val for c in straight_cards}
            if sv=={10,11,12,13,14}: return HandRank.ROYAL_FLUSH,straight_cards
            return HandRank.STRAIGHT_FLUSH,straight_cards
        if freq in ([4,1],[4]): return HandRank.FOUR_OF_A_KIND,gc
        if freq==[3,2]: return HandRank.FULL_HOUSE,gc
        if is_flush: return HandRank.FLUSH,sorted_c
        if is_straight: return HandRank.STRAIGHT,straight_cards
        if freq in ([3,1,1],[3,1],[3]): return HandRank.THREE_OF_A_KIND,gc
        if freq in ([2,2,1],[2,2]): return HandRank.TWO_PAIR,gc
        if freq in ([2,1,1,1],[2,1,1],[2,1],[2]): return HandRank.ONE_PAIR,gc
        return HandRank.HIGH_CARD,[sorted_c[0]]

    @staticmethod
    def score(hr: HandRank, scoring: list[Card], jokers: list, game_ref=None) -> tuple[int, float]:
        chips=hr.base_chips; mult=hr.multiplier; troll_loss=0
        for c in scoring:
            if isinstance(c,WildcardJokerCard):
                if c.is_troll:
                    if random.random()<0.5: mult=mult*3
                    else: troll_loss=random.randint(50,900); chips=max(0,chips-troll_loss)
                else: chips=int(chips*6.7); mult=mult*6.7
            else: chips+=c.chip_val
        if game_ref: game_ref._troll_loss=troll_loss
        for j in jokers: chips,mult=j.apply(chips,mult,hr,scoring)
        return int(chips*mult), mult


# ──────────────────────────────────────────────
#  JOKERS (slots joueur)
# ──────────────────────────────────────────────
class Joker:
    def __init__(self,name,desc,price,rarity):
        self.name=name; self.desc=desc; self.price=price
        self.rarity=rarity; self.locked=False
    def apply(self,c,m,h,s): return c,m
    @property
    def color(self):
        return {"Commun":COL["dim"],"Rare":COL["blue"],
                "Legendaire":COL["gold"],"Mystique":COL["mystique"]}.get(self.rarity,COL["dim"])

class JokerClassique(Joker):
    def __init__(self): super().__init__("Le Classique","+4 Mult",6,"Commun")
    def apply(self,c,m,h,s): return c,m+4

class LeGlouton(Joker):
    def __init__(self): super().__init__("Le Glouton","+3 chips/carte",5,"Commun")
    def apply(self,c,m,h,s): return c+3*len(s),m

class LeParrain(Joker):
    def __init__(self): super().__init__("Le Parrain","x2 si Carre+",10,"Rare")
    def apply(self,c,m,h,s): return c,m*2 if h.rank_order>=8 else m

class LeMatheux(Joker):
    def __init__(self): super().__init__("Le Matheux","+2 Mult/paire",7,"Commun")
    def apply(self,c,m,h,s):
        if h in (HandRank.ONE_PAIR,HandRank.TWO_PAIR,HandRank.FULL_HOUSE):
            m+=2*(2 if h==HandRank.TWO_PAIR else 1)
        return c,m

class LeTricheur(Joker):
    def __init__(self): super().__init__("Le Tricheur","+20 chips Couleur",8,"Rare")
    def apply(self,c,m,h,s): return c+(20 if h.rank_order>=6 else 0),m

class LaChance(Joker):
    def __init__(self): super().__init__("La Chance","50% x2 Mult",6,"Commun")
    def apply(self,c,m,h,s): return c,m*2 if random.random()<.5 else m

class LeCollectionneur(Joker):
    def __init__(self): super().__init__("Le Collec.","+5 chips/*",9,"Rare")
    def apply(self,c,m,h,s): return c+5*sum(1 for x in s if x.enhanced),m

class LeDoubleur(Joker):
    def __init__(self): super().__init__("Le Doubleur","x2 chips si Suite",12,"Legendaire")
    def apply(self,c,m,h,s):
        return c*2 if h in (HandRank.STRAIGHT,HandRank.STRAIGHT_FLUSH,HandRank.ROYAL_FLUSH) else c,m

class LeMaudit(Joker):
    def __init__(self): super().__init__("Le Maudit","+8 Mult, -10 chips",4,"Commun")
    def apply(self,c,m,h,s): return max(0,c-10),m+8

class LeSage(Joker):
    def __init__(self): super().__init__("Le Sage","+1 Mult/carte",8,"Rare")
    def apply(self,c,m,h,s): return c,m+len(s)


# ──────────────────────────────────────────────
#  ITEMS SPECIAUX DU SHOP
#  Tous dans le meme pool, actualises ensemble
# ──────────────────────────────────────────────

class ShopItem:
    """Base pour les items speciaux du shop (non-jokers)."""
    def __init__(self,name,desc,price,rarity,icon="[?]"):
        self.name=name; self.desc=desc; self.price=price
        self.rarity=rarity; self.icon=icon

    @property
    def color(self):
        return {"Commun":COL["dim"],"Rare":COL["blue"],
                "Legendaire":COL["gold"],"Mystique":COL["mystique"]}.get(self.rarity,COL["dim"])

    def on_buy(self, player, deck):
        """Appele quand le joueur achete cet item. Retourne un message."""
        return "Achete !"


class MainPlusItem(ShopItem):
    """Main+ : +1 main par round (permanent)."""
    def __init__(self):
        super().__init__("Main +","+1 main par round",5,"Rare","[+M]")

    def on_buy(self, player, deck):
        player.bonus_hands+=1
        return "+1 main gagnee ! Vos prochains rounds auront une main de plus."


class PoubellItem(ShopItem):
    """Poubelle : +1 defausse par round (permanent)."""
    def __init__(self):
        super().__init__("Poubelle","+1 defausse par round",4,"Rare","[+D]")

    def on_buy(self, player, deck):
        player.bonus_discards+=1
        return "+1 defausse gagnee ! Vos prochains rounds auront une defausse de plus."


class LaRouletteItem(ShopItem):
    """La Roulette : injecte une WILDCARD dans le deck."""
    def __init__(self):
        super().__init__("La Roulette",
                         "Ajoute 1 WILDCARD\ndans votre deck.\nCombo universel\nx6.7 chips+mult\n3% -> TROLL !",
                         15,"Mystique","[~]")

    def on_buy(self, player, deck):
        deck.add_wildcard()
        return "WILDCARD ajoutee au deck ! Attention aux mutations..."


class BobTavernierItem(ShopItem):
    """BOB le tavernier : +1 slot joker + 3 refreshs gratuits/visite."""
    def __init__(self):
        super().__init__("BOB le tavernier",
                         "+1 slot joker\n(5->6)\n3 refreshs\ngratuits/visite",
                         12,"Legendaire","[B]")

    def on_buy(self, player, deck):
        player.has_bob=True
        player.max_jokers=6
        player.free_refreshes=3
        return "BOB est avec vous ! +1 slot joker + 3 refreshs/visite !"


# ──────────────────────────────────────────────
#  POOL UNIFIE DU SHOP
#  Jokers + items speciaux, tout melange
#  Poids de tirage selon conditions
# ──────────────────────────────────────────────

JOKER_CLASSES = [JokerClassique,LeGlouton,LeParrain,LeMatheux,LeTricheur,
                 LaChance,LeCollectionneur,LeDoubleur,LeMaudit,LeSage]


def build_shop_pool(player, deck):
    """
    Construit la liste d'items disponibles pour ce tirage.
    Retourne une liste de (poids, constructeur) selon les conditions.
    """
    pool = []
    # Jokers normaux : poids 10 chacun
    for jc in JOKER_CLASSES:
        pool.append((10, jc))
    # Main+ et Poubelle : Rare, peuvent reapparaitre, poids 6
    pool.append((6, MainPlusItem))
    pool.append((6, PoubellItem))
    # BOB : Legendaire, uniquement si pas encore possede, poids 3
    if not player.has_bob:
        pool.append((3, BobTavernierItem))
    # La Roulette : Mystique, uniquement si pas deja dans le deck, poids 2
    if not deck.has_wildcard():
        pool.append((2, LaRouletteItem))
    return pool


def draw_shop_items(pool, n, player, deck):
    """Tire n items distincts dans le pool (sans remise pour eviter doublons de meme instance)."""
    weights=[w for w,_ in pool]
    classes=[c for _,c in pool]
    chosen=[]
    used_classes=set()
    attempts=0
    while len(chosen)<n and attempts<200:
        attempts+=1
        total=sum(w for w,c in pool if c not in used_classes)
        if total==0: break
        r=random.uniform(0,total); acc=0
        for w,c in pool:
            if c in used_classes: continue
            acc+=w
            if r<=acc:
                chosen.append(c())
                used_classes.add(c)
                break
    return chosen


# ──────────────────────────────────────────────
#  BLINDS
# ──────────────────────────────────────────────
class Blind:
    def __init__(self,name,desc,target,reward,boss_type=None):
        self.name=name; self.desc=desc; self.target=target
        self.reward=reward; self.boss_type=boss_type

BLINDS=[
    [Blind("la Fourmie","Echauffez-vous !",    300, 3),
     Blind("Le Scarabe","Ca commence !",        500, 4),
     Blind("Boss: Limace","Jokers desactives", 1000, 6,"limace")],
    [Blind("le Ciment","Allez-y !",            1100, 4),
     Blind("La Brique","Concentrez-vous !",    1300, 6),
     Blind("Boss: Mur","4 mains seulement",    2000, 8,"mur")],
    [Blind("le Crane","La vraie partie",       2100, 5),
     Blind("Le Squelette","Pas de pitie",      2300, 8),
     Blind("Boss: La Sorciere","Score x0.5",  3000,12,"sorciere")],
    [Blind("Le Soldat","Courage !",            3100, 7),
     Blind("Garde Royal","Presque la...",      4000,10),
     Blind("BOSS FINAL: ROI","Score x0.25",   5000,20,"roi")],
]

# ──────────────────────────────────────────────
#  JOUEUR
# ──────────────────────────────────────────────
class Player:
    def __init__(self):
        self.money=10; self.jokers: list[Joker]=[]
        self.max_jokers=5; self.hands_left=4
        self.discards_left=3; self.hands_played=0
        self.has_bob=False; self.free_refreshes=0
        self.bonus_hands=0      # bonus permanent de mains (Main+)
        self.bonus_discards=0   # bonus permanent de defausses (Poubelle)

    def add_joker(self,j):
        if len(self.jokers)<self.max_jokers: self.jokers.append(j); return True
        return False

    def spend(self,n):
        if self.money>=n: self.money-=n; return True
        return False

    def earn(self,n): self.money+=n

# ──────────────────────────────────────────────
#  PARTICULES
# ──────────────────────────────────────────────
class Particle:
    def __init__(self,x,y,color,text=None):
        self.x=x; self.y=y; self.vx=random.uniform(-1.5,1.5)
        self.vy=random.uniform(-3,-1); self.life=60; self.max=60
        self.color=color; self.text=text
        self.r=random.randint(3,7) if not text else 0

    def update(self):
        self.x+=self.vx; self.y+=self.vy; self.vy+=0.05; self.life-=1
        return self.life>0

    def draw(self,surf):
        alpha=int(255*self.life/self.max)
        if self.text:
            s=F["sm"].render(self.text,True,self.color); s.set_alpha(alpha)
            surf.blit(s,(int(self.x),int(self.y)))
        else:
            s=pygame.Surface((self.r*2,self.r*2),pygame.SRCALPHA)
            pygame.draw.circle(s,(*self.color,alpha),(self.r,self.r),self.r)
            surf.blit(s,(int(self.x-self.r),int(self.y-self.r)))


class DiscardParticle:
    def __init__(self,card,x,y):
        self.card=card; self.x=float(x); self.y=float(y)
        self.vx=random.uniform(-3,3); self.vy=random.uniform(-6,-3)
        self.life=35; self.max=35

    def update(self):
        self.x+=self.vx; self.y+=self.vy; self.vy+=0.25; self.life-=1
        return self.life>0

    def draw(self,surf):
        alpha=int(255*self.life/self.max)
        temp=pygame.Surface((CARD_W,CARD_H),pygame.SRCALPHA)
        pygame.draw.rect(temp,(*COL["card_w"],alpha),(0,0,CARD_W,CARD_H),border_radius=8)
        pygame.draw.rect(temp,(*COL["card_brd"],alpha),(0,0,CARD_W,CARD_H),2,border_radius=8)
        if not isinstance(self.card,(WildcardJokerCard,PoissonDegueulasse)):
            sc=self.card.suit.color; f=F["rank"]
            sr=f.render(self.card.rank.display,True,(*sc,alpha))
            ss=F["suit"].render(SUIT_SYMBOLS[self.card.suit.symbol],True,(*sc,alpha))
            temp.blit(sr,(5,5)); temp.blit(ss,(5,5+f.get_height()-2))
        surf.blit(temp,(int(self.x),int(self.y)))

class Button:
    def __init__(self,x,y,w,h,text,color=None,text_color=None):
        self.rect=pygame.Rect(x,y,w,h); self.text=text
        self.color=color or COL["btn"]; self.text_color=text_color or COL["white"]
        self.hover=False; self.disabled=False

    def draw(self,surf):
        c=COL["dim"] if self.disabled else (COL["btn_h"] if self.hover else self.color)
        draw_rect_rounded(surf,c,self.rect,8)
        draw_border(surf,(100,90,130) if not self.disabled else COL["dim"],self.rect,1,8)
        tc=COL["dim"] if self.disabled else self.text_color
        draw_text(surf,self.text,F["med"],tc,self.rect.centerx,self.rect.centery,center=True)
        if self.hover and not self.disabled:
            glow=pygame.Surface((self.rect.w+8,self.rect.h+8),pygame.SRCALPHA)
            pygame.draw.rect(glow,(*self.color,60),(0,0,self.rect.w+8,self.rect.h+8),border_radius=10)
            surf.blit(glow,(self.rect.x-4,self.rect.y-4))

    def update(self,mx,my): self.hover=self.rect.collidepoint(mx,my) and not self.disabled
    def clicked(self,event):
        return (event.type==pygame.MOUSEBUTTONDOWN and event.button==1
                and self.rect.collidepoint(event.pos) and not self.disabled)


# ──────────────────────────────────────────────
#  BOUTIQUE — pool unifie, layout centre
# ──────────────────────────────────────────────
SHOP_SLOTS   = 4      # nombre d'items affiches simultanement
CARD_SLOT_W  = 190    # largeur d'un slot
CARD_SLOT_H  = 240    # hauteur d'un slot
CARD_SLOT_Y  = 175    # y de depart des cartes
CARD_SLOT_GAP= 14     # espace entre les cartes

class ShopScreen:
    def __init__(self,player,deck,on_close):
        self.player=player; self.deck=deck; self.on_close=on_close
        self.items=[]   # liste d'items affiches (Joker ou ShopItem)
        self._refresh_items()
        self.msg=""; self.msg_timer=0
        if self.player.has_bob:
            self.player.free_refreshes=3
        # Boutons en bas, bien espaces
        btn_y=H-68
        self.btn_close  =Button(W//2+110, btn_y, 170, 44, "Continuer ->", COL["btn_play"])
        self.btn_sell_all=[]
        self._build_sell_buttons()
        self._update_refresh_btn()
        self._ranim=0.0

    def _update_refresh_btn(self):
        btn_y=H-68
        if self.player.free_refreshes>0:
            label=f"Gratuit ({self.player.free_refreshes})"
            col=COL["btn_play"]
        else:
            label="Rafraichir 2$"
            col=COL["btn"]
        self.btn_refresh=Button(W//2-80, btn_y, 180, 44, label, col)

    def _refresh_items(self):
        pool=build_shop_pool(self.player,self.deck)
        self.items=draw_shop_items(pool, SHOP_SLOTS, self.player, self.deck)

    def _build_sell_buttons(self):
        self.btn_sell_all=[]
        for i,j in enumerate(self.player.jokers):
            bx=self._joker_slot_x(i)
            if j.locked:
                b=Button(bx,662,155,28,"[VERROUILLE]",COL["dim"]); b.disabled=True
            else:
                b=Button(bx,662,155,28,f"Vendre {j.price//2}$",COL["btn_disc"])
            self.btn_sell_all.append(b)

    def _item_rect(self,i):
        """Rect du i-eme item du shop, centres."""
        n=len(self.items)
        total_w=n*CARD_SLOT_W+(n-1)*CARD_SLOT_GAP
        x0=(W-total_w)//2
        x=x0+i*(CARD_SLOT_W+CARD_SLOT_GAP)
        return pygame.Rect(x, CARD_SLOT_Y, CARD_SLOT_W, CARD_SLOT_H)

    def _joker_slot_x(self,i):
        return 30+i*165

    def handle(self,event):
        mx,my=pygame.mouse.get_pos()
        self.btn_close.update(mx,my); self.btn_refresh.update(mx,my)
        for b in self.btn_sell_all: b.update(mx,my)

        if self.btn_close.clicked(event): self.on_close(); return

        if self.btn_refresh.clicked(event):
            if self.player.free_refreshes>0:
                self.player.free_refreshes-=1
                self._refresh_items()
                self._update_refresh_btn()
                self._show_msg(f"Rafraichi gratuitement ! ({self.player.free_refreshes} restants)")
            elif self.player.spend(2):
                self._refresh_items()
                self._show_msg("Boutique rafraichie !")
            else:
                self._show_msg("Pas assez d'argent !")
            return

        for i,b in enumerate(self.btn_sell_all):
            if b.clicked(event) and i<len(self.player.jokers):
                j=self.player.jokers[i]
                if j.locked: self._show_msg(f"{j.name} est verrouille !"); return
                sold=self.player.jokers.pop(i); self.player.earn(sold.price//2)
                self._show_msg(f"Vendu {sold.name} pour {sold.price//2}$")
                self._build_sell_buttons(); return

        if event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
            for i,item in enumerate(self.items):
                r=self._item_rect(i)
                if r.collidepoint(event.pos):
                    self._try_buy(i); return

    def _try_buy(self,i):
        item=self.items[i]
        price=item.price if hasattr(item,'price') else 0

        if not self.player.spend(price):
            self._show_msg("Pas assez d'argent !"); return

        # Item special (ShopItem)
        if isinstance(item, ShopItem):
            msg=item.on_buy(self.player, self.deck)
            self.items.pop(i)
            self._update_refresh_btn()
            self._build_sell_buttons()
            self._show_msg(msg)
        # Joker normal
        else:
            if self.player.add_joker(item):
                self.items.pop(i)
                self._build_sell_buttons()
                self._show_msg(f"{item.name} achete !")
            else:
                self.player.earn(price)
                self._show_msg("Jokers pleins ! Vendez-en un.")

    def _show_msg(self,m): self.msg=m; self.msg_timer=180

    def update(self): self._ranim+=0.05

    def _draw_item_card(self, surf, item, r, hv):
        """Dessine un slot d'item du shop (joker ou item special)."""
        is_roulette=isinstance(item, LaRouletteItem)
        is_bob=isinstance(item, BobTavernierItem)
        is_main=isinstance(item, MainPlusItem)
        is_poubelle=isinstance(item, PoubellItem)
        is_special=isinstance(item, ShopItem)

        # Fond
        if is_roulette:
            pulse=0.5+0.5*abs(math.sin(self._ranim))
            bg=lerp_color((20,10,40),COL["mystique"],pulse*0.4)
        elif is_bob:
            pulse=0.5+0.5*abs(math.sin(self._ranim*0.8))
            bg=lerp_color((40,30,10),COL["gold"],pulse*0.3)
        else:
            bg=lerp_color(COL["panel"],COL["btn_h"],0.3 if hv else 0)
        draw_rect_rounded(surf,bg,r,12)

        # Bordure
        col=item.color if is_special else item.color
        brd_w=3 if hv else 2
        if is_roulette:
            pulse=0.5+0.5*abs(math.sin(self._ranim))
            col=lerp_color(COL["mystique"],(220,180,255),0.4*abs(math.sin(self._ranim*1.8)))
        elif is_bob:
            pulse=0.5+0.5*abs(math.sin(self._ranim*0.8))
            col=lerp_color(COL["gold"],(255,240,150),0.4*abs(math.sin(self._ranim)))
        draw_border(surf,col,r,brd_w,12)

        # Rarete
        rar_col=item.color if is_special else item.color
        draw_text(surf,f"* {item.rarity} *",F["xs"],rar_col,r.centerx,r.top+14,center=True)

        # Icone / dessin
        iy=r.top+52
        if is_bob:
            # Dessin Bob
            bcx=r.centerx; bcy=r.top+56
            pygame.draw.circle(surf,(220,180,120),(bcx,bcy),14)
            pygame.draw.rect(surf,(120,60,20),(bcx-10,bcy+14,20,22))
            pygame.draw.line(surf,(120,60,20),(bcx-10,bcy+18),(bcx-20,bcy+30),3)
            pygame.draw.line(surf,(120,60,20),(bcx+10,bcy+18),(bcx+20,bcy+30),3)
            pygame.draw.circle(surf,(0,0,0),(bcx-4,bcy-2),2)
            pygame.draw.circle(surf,(0,0,0),(bcx+4,bcy-2),2)
            pygame.draw.arc(surf,(0,0,0),pygame.Rect(bcx-5,bcy+5,10,6),math.pi,0,2)
            pygame.draw.rect(surf,(200,160,40),(bcx+18,bcy+22,8,10))
            pygame.draw.rect(surf,(220,220,100),(bcx+18,bcy+22,8,4))
            iy=r.top+88
        elif is_roulette:
            spin=["[~]","[*]","[?]","[@]"]
            icon=spin[int(self._ranim*3)%len(spin)] if hv else "[~]"
            draw_text(surf,icon,load_font(24,True),COL["mystique"],r.centerx,r.top+52,center=True)
            iy=r.top+78
        elif is_main:
            draw_text(surf,"+M",load_font(36,True),COL["blue"],r.centerx,r.top+52,center=True)
            iy=r.top+82
        elif is_poubelle:
            draw_text(surf,"+D",load_font(36,True),COL["green"],r.centerx,r.top+52,center=True)
            iy=r.top+82
        else:
            draw_text(surf,"[J]",load_font(30),COL["white"],r.centerx,r.top+50,center=True)
            iy=r.top+80

        # Nom
        draw_text(surf,item.name,F["joker"],COL["white"],r.centerx,iy,center=True)

        # Description (wrap)
        desc_raw=item.desc if hasattr(item,'desc') else ""
        lines=desc_raw.split("\n") if "\n" in desc_raw else []
        if not lines:
            words=desc_raw.split(); line=[]; lines2=[]
            for w in words:
                if F["xs"].size(" ".join(line+[w]))[0]<r.width-16: line.append(w)
                else: lines2.append(" ".join(line)); line=[w]
            lines2.append(" ".join(line)); lines=lines2
        for li,l in enumerate(lines):
            lc=COL["red"] if "TROLL" in l else COL["dim"]
            draw_text(surf,l,F["xs"],lc,r.centerx,iy+18+li*16,center=True)

        # Prix
        pc=COL["green"] if self.player.money>=item.price else COL["red"]
        draw_text(surf,f"Prix: {item.price}$",F["med"],pc,r.centerx,r.bottom-34,center=True)
        if hv:
            draw_text(surf,"Cliquer pour acheter",F["xs"],COL["gold"],r.centerx,r.bottom-16,center=True)

        # Glow hover pour items speciaux
        if hv and is_special:
            glow=pygame.Surface((r.w+16,r.h+16),pygame.SRCALPHA)
            gc=item.color
            pygame.draw.rect(glow,(*gc,30),(0,0,r.w+16,r.h+16),border_radius=16)
            surf.blit(glow,(r.x-8,r.y-8))

    def draw(self,surf):
        draw_rect_rounded(surf,COL["shop_bg"],(0,0,W,H),0)
        draw_text(surf,"* BOUTIQUE *",F["title"],COL["gold"],W//2,40,center=True)
        draw_text(surf,f"Argent: {self.player.money}$",F["big"],COL["green"],W//2,92,center=True)

        # Infos statut
        info_y=138
        if self.player.has_bob:
            draw_text(surf,f"[BOB] slots joker: {self.player.max_jokers} | {self.player.free_refreshes} refresh(s) gratuit(s)",
                      F["xs"],COL["gold"],W//2,info_y,center=True); info_y+=17
        if self.deck.has_wildcard():
            wt=self.deck._wildcard
            wc_col=COL["troll"] if wt and wt.is_troll else COL["mystique"]
            wc_txt="[TROLL] dans deck !" if (wt and wt.is_troll) else "[WILD] dans deck"
            draw_text(surf,wc_txt,F["xs"],wc_col,W//2,info_y,center=True); info_y+=17
        bonuses=[]
        if self.player.bonus_hands>0: bonuses.append(f"+{self.player.bonus_hands} mains/round")
        if self.player.bonus_discards>0: bonuses.append(f"+{self.player.bonus_discards} defausses/round")
        if bonuses:
            draw_text(surf," | ".join(bonuses),F["xs"],COL["green"],W//2,info_y,center=True)

        # Items du shop (centres)
        mx,my=pygame.mouse.get_pos()
        for i,item in enumerate(self.items):
            r=self._item_rect(i); hv=r.collidepoint(mx,my)
            self._draw_item_card(surf,item,r,hv)

        # Separateur
        pygame.draw.line(surf,COL["dim"],(30,430),(W-30,430),1)

        # Jokers du joueur
        draw_text(surf,f"Vos jokers ({len(self.player.jokers)}/{self.player.max_jokers})",
                  F["med"],COL["purple"],W//2,442,center=True)

        for i,j in enumerate(self.player.jokers):
            bx=self._joker_slot_x(i); bw,bh=155,110; by=462
            draw_rect_rounded(surf,COL["panel"],(bx,by,bw,bh),8)
            draw_border(surf,j.color,(bx,by,bw,bh),2 if j.locked else 1,8)
            draw_text(surf,j.name,F["joker"],COL["white"],bx+bw//2,by+14,center=True)
            draw_text(surf,j.rarity,F["xs"],j.color,bx+bw//2,by+32,center=True)
            draw_text(surf,j.desc[:20],F["xs"],COL["dim"],bx+bw//2,by+50,center=True)
            draw_text(surf,j.desc[20:42],F["xs"],COL["dim"],bx+bw//2,by+66,center=True)
            if i<len(self.btn_sell_all): self.btn_sell_all[i].draw(surf)

        # Boutons du bas bien espaces
        self.btn_refresh.draw(surf)
        self.btn_close.draw(surf)

        if self.msg_timer>0:
            self.msg_timer-=1; alpha=min(255,self.msg_timer*3)
            s=F["med"].render(self.msg,True,COL["gold"]); s.set_alpha(alpha)
            surf.blit(s,s.get_rect(center=(W//2,H//2-20)))


# ──────────────────────────────────────────────
#  JEU
# ──────────────────────────────────────────────
class GameScreen:
    HAND_SIZE=8

    def __init__(self):
        self.player=Player(); self.deck=Deck()
        self.hand: list[Card]=[]
        self.particles: list[Particle]=[]
        self.discard_particles: list[DiscardParticle]=[]
        self.ante=0; self.blind_idx=0; self.score=0
        self.state="playing"
        self.result_msg=""; self.result_pts=0; self.result_hand=""
        self.result_timer=0; self.msg=""; self.msg_timer=0
        self.shop_screen: Optional[ShopScreen]=None
        self.anim_score=0; self._troll_loss=0
        self._setup_round(); self._build_buttons()
        self.state="welcome"; self.bg=BalatroBackground()

    def _current_blind(self): return BLINDS[self.ante][self.blind_idx]

    def _setup_round(self):
        self.deck.reset()
        self.hand=self.deck.draw(self.HAND_SIZE)
        self.score=0; self.anim_score=0
        blind=self._current_blind()
        base_hands=3 if blind.boss_type=="mur" else 4
        self.player.hands_left   = base_hands + self.player.bonus_hands
        self.player.discards_left= 3 + self.player.bonus_discards
        self._enforce_poisson()
        for c in self.hand:
            if isinstance(c,WildcardJokerCard) and c.is_troll:
                self._show_msg("!!! TROLOLOLOLO !!! La WILDCARD a mute en TROLL !!!")
                break

    def _enforce_poisson(self):
        for c in self.hand:
            if isinstance(c,PoissonDegueulasse):
                c.selected=True
                self._show_msg("~~ POISSON DEGUEULASSE en main ! Il sera joue de force ! ~~")

    def _build_buttons(self):
        self.btn_play=Button(W-220,H-130,190,48,"JOUER",    COL["btn_play"],COL["white"])
        self.btn_disc=Button(W-220,H-72, 190,48,"DEFAUSSER",COL["btn_disc"],COL["white"])

    def _selected(self): return [c for c in self.hand if c.selected]

    def _toggle(self,card):
        if isinstance(card,PoissonDegueulasse): return
        sel=self._selected()
        if card.selected: card.selected=False
        elif len(sel)<5: card.selected=True

    def _play_hand(self):
        sel=self._selected()
        if not sel: self._show_msg("Selectionnez des cartes !"); return
        if self.player.hands_left<=0: self._show_msg("Plus de mains !"); return

        hr,scoring=HandEvaluator.evaluate(sel)
        blind=self._current_blind()
        jokers=[] if blind.boss_type=="limace" else self.player.jokers
        penalty={"crane":0.5,"roi":0.25}.get(blind.boss_type,1.0)

        self._troll_loss=0
        pts,mult=HandEvaluator.score(hr,scoring,jokers,game_ref=self)
        pts=int(pts*penalty)

        poisson_in_sel=[c for c in sel if isinstance(c,PoissonDegueulasse)]
        poisson_curse=False
        if poisson_in_sel:
            if random.random()<PoissonDegueulasse.CURSE_CHANCE:
                self.player.discards_left=0; poisson_curse=True
                self._show_msg("~~ POISSON MAUDIT ! Toutes vos defausses sont perdues ! ~~")
            else:
                pts=int(pts*4); mult=mult*4

        self.score+=pts; self.player.hands_left-=1; self.player.hands_played+=1

        cx=W//2; cy=H-180
        for _ in range(20):
            self.particles.append(Particle(cx+random.randint(-80,80),cy,COL["gold"]))
        self.particles.append(Particle(cx-30,cy-20,COL["green"],f"+{pts:,}"))

        has_wild_normal=any(isinstance(c,WildcardJokerCard) and not c.is_troll for c in sel)
        has_troll=any(isinstance(c,WildcardJokerCard) and c.is_troll for c in sel)

        if has_wild_normal:
            for _ in range(10):
                self.particles.append(Particle(cx+random.randint(-100,100),cy+random.randint(-30,30),
                    COL["mystique"],random.choice(["x6.7","WILD","*","!"])))
        if has_troll:
            for _ in range(14):
                self.particles.append(Particle(cx+random.randint(-140,140),cy+random.randint(-50,50),
                    COL["troll"],random.choice(["XD","lol","HEHE","TROL","gg"])))
            if self._troll_loss>0:
                self.particles.append(Particle(cx+40,cy-40,COL["red"],f"-{self._troll_loss}"))
        if poisson_in_sel:
            pcolor=COL["red"] if poisson_curse else COL["green"]
            plabel="MAUDIT!" if poisson_curse else "x4 POISSON!"
            for _ in range(12):
                self.particles.append(Particle(cx+random.randint(-110,110),cy+random.randint(-40,40),
                    pcolor,random.choice([plabel,"~","*~*","glou"])))

        self.hand=[c for c in self.hand if not c.selected]
        new_cards=self.deck.draw(len(sel))
        for c in new_cards:
            if isinstance(c,WildcardJokerCard) and c.is_troll:
                self._show_msg("!!! La WILDCARD vient de MUTER en TROLL !!!")
        self.hand.extend(new_cards)
        for c in self.hand: c.selected=False
        self._enforce_poisson()

        self.result_msg=hr.name_fr; self.result_pts=pts
        wild_note=" | WILD x6.7!" if has_wild_normal else ""
        troll_note=f" | TROLL -{self._troll_loss}" if self._troll_loss>0 else (" | TROLL x3!" if has_troll else "")
        poisson_note=" | POISSON x4!" if (poisson_in_sel and not poisson_curse) else (" | POISSON MAUDIT!" if poisson_curse else "")
        self.result_hand=f"Chips:{hr.base_chips}  xMult:{mult:.1f}{wild_note}{troll_note}{poisson_note}"
        self.result_timer=120; self.state="result"

    def _discard(self):
        sel=self._selected()
        if not sel: self._show_msg("Selectionnez des cartes !"); return
        if self.player.discards_left<=0: self._show_msg("Plus de defausses !"); return

        blocked=[c for c in sel if isinstance(c,(WildcardJokerCard,PoissonDegueulasse))]
        if blocked:
            for bc in blocked: bc.selected=False
            sel=[c for c in sel if not isinstance(c,(WildcardJokerCard,PoissonDegueulasse))]
            self._show_msg("Ces cartes ne peuvent pas etre defaussees !")
            if not sel: return

        card_x0=(W-(self.HAND_SIZE*82))//2
        for c in sel:
            idx=self.hand.index(c); cx=card_x0+idx*82
            self.discard_particles.append(DiscardParticle(c,cx,H-160))

        self.hand=[c for c in self.hand if not c.selected]
        new_cards=self.deck.draw(len(sel))
        for c in new_cards:
            if isinstance(c,WildcardJokerCard) and c.is_troll:
                self._show_msg("!!! La WILDCARD vient de MUTER en TROLL !!!")
        self.hand.extend(new_cards)
        for c in self.hand: c.selected=False
        self.player.discards_left-=1
        self._enforce_poisson()

    def _show_msg(self,m): self.msg=m; self.msg_timer=120

    def _check_blind(self):
        blind=self._current_blind()
        if self.score>=blind.target: return "win"
        if self.player.hands_left<=0: return "lose"
        return "continue"

    def _advance(self):
        blind=self._current_blind()
        self.player.earn(blind.reward+self.player.money//5)
        self.blind_idx+=1
        if self.blind_idx>=3:
            self.blind_idx=0; self.ante+=1
            if self.ante>=len(BLINDS): self.state="victory"; return
        self.shop_screen=ShopScreen(self.player,self.deck,self._after_shop)
        self.state="shop"

    def _after_shop(self): self.state="playing"; self._setup_round()

    def handle(self,event):
        if self.state=="welcome":
            if event.type in (pygame.MOUSEBUTTONDOWN,pygame.KEYDOWN): self.state="playing"
            return
        if self.state=="shop": self.shop_screen.handle(event); return
        if self.state in ("gameover","victory"):
            if event.type==pygame.MOUSEBUTTONDOWN: self.__init__()
            return
        if self.state=="result":
            if event.type==pygame.MOUSEBUTTONDOWN:
                check=self._check_blind()
                if check=="win": self._advance()
                elif check=="lose": self.state="gameover"
                else: self.state="playing"
            return

        mx,my=pygame.mouse.get_pos()
        self.btn_play.update(mx,my); self.btn_disc.update(mx,my)
        self.btn_play.disabled=not self._selected() or self.player.hands_left<=0
        self.btn_disc.disabled=not self._selected() or self.player.discards_left<=0

        if event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
            if self.btn_play.clicked(event): self._play_hand(); return
            if self.btn_disc.clicked(event): self._discard(); return
            card_x0=(W-(self.HAND_SIZE*82))//2
            for i,card in enumerate(self.hand):
                if card.get_rect(card_x0+i*82,H-160).collidepoint(event.pos):
                    self._toggle(card); break

        if event.type==pygame.KEYDOWN:
            if pygame.K_1<=event.key<=pygame.K_8:
                idx=event.key-pygame.K_1
                if idx<len(self.hand): self._toggle(self.hand[idx])
            elif event.key==pygame.K_RETURN: self._play_hand()
            elif event.key==pygame.K_d: self._discard()

    def update(self):
        self.bg.update()
        if self.anim_score<self.score:
            self.anim_score=min(self.score,self.anim_score+max(1,(self.score-self.anim_score)//8))
        self.particles=[p for p in self.particles if p.update()]
        self.discard_particles=[p for p in self.discard_particles if p.update()]
        mx,my=pygame.mouse.get_pos()
        card_x0=(W-(self.HAND_SIZE*82))//2
        for i,card in enumerate(self.hand):
            cx=card_x0+i*82
            card._hover=card.get_rect(cx,H-160).collidepoint(mx,my)
            target_y=-18 if card.selected else 0
            card._anim_y+=(target_y-card._anim_y)*0.25
        if self.msg_timer>0: self.msg_timer-=1
        if self.result_timer>0: self.result_timer-=1
        if self.state=="shop" and self.shop_screen: self.shop_screen.update()

    def draw(self,surf):
        self.bg.draw(surf)
        if self.state=="welcome": self._draw_welcome(surf); return
        if self.state=="shop": self.shop_screen.draw(surf); return
        if self.state=="gameover": self._draw_gameover(surf); return
        if self.state=="victory": self._draw_victory(surf); return

        blind=self._current_blind()
        draw_rect_rounded(surf,COL["panel"],(10,10,300,230),12,200)
        draw_border(surf,COL["purple"],(10,10,300,230),1,12)
        draw_text(surf,f"Score: {self.anim_score:,}",F["big"],COL["gold"],20,18)
        draw_text(surf,f"Objectif: {blind.target:,}",F["sm"],COL["white"],20,58)
        draw_text(surf,f"Blind: {blind.name}",F["xs"],COL["dim"],20,82)
        bar_w=270; prog=min(1.0,self.anim_score/max(1,blind.target))
        draw_rect_rounded(surf,(40,30,60),(20,108,bar_w,14),6)
        if prog>0:
            draw_rect_rounded(surf,lerp_color(COL["red"],COL["green"],prog),(20,108,int(bar_w*prog),14),6)
        draw_border(surf,COL["dim"],(20,108,bar_w,14),1,6)
        draw_text(surf,f"Mains:    {self.player.hands_left}",F["sm"],COL["white"],20,132)
        draw_text(surf,f"Defausses: {self.player.discards_left}",F["sm"],COL["dim"],20,158)
        draw_text(surf,f"Argent: {self.player.money}$",F["sm"],COL["green"],20,184)
        hud_y=204
        if self.deck.has_wildcard():
            wt=self.deck._wildcard
            wc_col=COL["troll"] if wt and wt.is_troll else COL["mystique"]
            draw_text(surf,"[TROLL] deck!" if (wt and wt.is_troll) else "[WILD] deck",F["xs"],wc_col,20,hud_y); hud_y+=16
        if self.player.has_bob:
            draw_text(surf,f"[BOB] slots:{self.player.max_jokers}",F["xs"],COL["gold"],20,hud_y); hud_y+=16
        if self.player.bonus_hands or self.player.bonus_discards:
            draw_text(surf,f"+{self.player.bonus_hands}M +{self.player.bonus_discards}D/round",F["xs"],COL["green"],20,hud_y)

        if self.player.jokers:
            jx=320; sw=90; pw=len(self.player.jokers)*sw+10
            draw_rect_rounded(surf,COL["panel"],(jx,10,pw,100),10,180)
            for k,j in enumerate(self.player.jokers):
                bx=jx+8+k*sw; bw,bh=82,88
                draw_rect_rounded(surf,COL["joker_c"],(bx,15,bw,bh),8)
                draw_border(surf,j.color,(bx,15,bw,bh),1,8)
                draw_text(surf,"[J]",load_font(18),COL["white"],bx+bw//2,35,center=True)
                draw_text(surf,j.name,F["xs"],COL["white"],bx+bw//2,78,center=True)

        draw_rect_rounded(surf,COL["panel"],(W-170,10,160,60),10,200)
        draw_border(surf,COL["orange"],(W-170,10,160,60),1,10)
        draw_text(surf,f"Ante {self.ante+1}/4",F["sm"],COL["orange"],W-90,26,center=True)
        draw_text(surf,f"Blind {self.blind_idx+1}/3",F["xs"],COL["dim"],W-90,50,center=True)

        for p in self.discard_particles: p.draw(surf)
        for p in self.particles: p.draw(surf)

        card_x0=(W-(self.HAND_SIZE*82))//2
        for i,card in enumerate(self.hand): card.draw(surf,card_x0+i*82,H-160)

        self.btn_play.draw(surf); self.btn_disc.draw(surf)
        draw_text(surf,"Entree=Jouer | D=Defausser | 1-8=Selectionner | F11=Plein ecran",
                  F["xs"],COL["dim"],W//2,H-18,center=True)

        if self.msg_timer>0:
            alpha=min(255,self.msg_timer*4)
            s=F["med"].render(self.msg,True,COL["gold"]); s.set_alpha(alpha)
            surf.blit(s,s.get_rect(center=(W//2,H//2+40)))

        if self.result_timer>0 or self.state=="result":
            cx_r,cy_r=W//2,240; pw,ph=540,110
            draw_rect_rounded(surf,COL["panel"],(cx_r-pw//2,cy_r-ph//2,pw,ph),12,220)
            draw_border(surf,COL["gold"],(cx_r-pw//2,cy_r-ph//2,pw,ph),2,12)
            draw_text(surf,self.result_msg,F["big"],COL["gold"],cx_r,cy_r-26,center=True)
            draw_text(surf,self.result_hand,F["sm"],COL["white"],cx_r,cy_r+10,center=True)
            draw_text(surf,f"+{self.result_pts:,} pts",F["med"],COL["green"],cx_r,cy_r+36,center=True)
            if self.state=="result":
                draw_text(surf,"Cliquez pour continuer",F["xs"],COL["dim"],cx_r,cy_r+ph//2+14,center=True)

    def _draw_welcome(self,surf):
        for off in [(2,2),(-2,-2),(2,-2),(-2,2)]:
            draw_text(surf,"BALTROU",F["title"],(60,10,80),W//2+off[0],H//2-80+off[1],center=True)
        draw_text(surf,"BALTROU",F["title"],COL["gold"],W//2,H//2-80,center=True)
        draw_text(surf,"Poker Roguelite",F["big"],COL["purple"],W//2,H//2-22,center=True)
        draw_rect_rounded(surf,COL["panel"],(W//2-310,H//2+20,620,145),14,210)
        draw_border(surf,COL["dim"],(W//2-310,H//2+20,620,145),1,14)
        draw_text(surf,"Cliquez ou appuyez sur une touche pour commencer",
                  F["med"],COL["white"],W//2,H//2+55,center=True)
        draw_text(surf,"Selectionnez jusqu a 5 cartes  |  Touches 1-8 pour selectionner",
                  F["xs"],COL["dim"],W//2,H//2+88,center=True)
        draw_text(surf,"La Roulette (MYSTIQUE) et BOB (LEGENDAIRE) apparaissent dans la boutique !",
                  F["xs"],COL["mystique"],W//2,H//2+110,center=True)
        draw_text(surf,"Entree=Jouer  |  D=Defausser  |  F11=Plein ecran",
                  F["xs"],COL["dim"],W//2,H//2+132,center=True)

    def _draw_gameover(self,surf):
        draw_rect_rounded(surf,(10,6,18),(0,0,W,H),0,200)
        draw_text(surf,"GAME OVER",F["title"],COL["red"],W//2,H//2-60,center=True)
        draw_text(surf,f"Score final : {self.score:,}",F["big"],COL["white"],W//2,H//2+10,center=True)
        draw_text(surf,f"Ante {self.ante+1} - Blind {self.blind_idx+1}",F["sm"],COL["dim"],W//2,H//2+50,center=True)
        draw_rect_rounded(surf,COL["btn"],(W//2-110,H//2+90,220,50),10)
        draw_border(surf,COL["red"],(W//2-110,H//2+90,220,50),2,10)
        draw_text(surf,"Recommencer",F["med"],COL["white"],W//2,H//2+115,center=True)

    def _draw_victory(self,surf):
        draw_rect_rounded(surf,(6,18,10),(0,0,W,H),0,200)
        draw_text(surf,"VICTOIRE !",F["title"],COL["green"],W//2,H//2-60,center=True)
        draw_text(surf,f"Score final : {self.score:,}",F["big"],COL["gold"],W//2,H//2+10,center=True)
        draw_text(surf,"Vous avez vaincu le ROI !",F["sm"],COL["white"],W//2,H//2+50,center=True)
        draw_rect_rounded(surf,COL["btn_play"],(W//2-110,H//2+90,220,50),10)
        draw_border(surf,COL["green"],(W//2-110,H//2+90,220,50),2,10)
        draw_text(surf,"Rejouer",F["med"],COL["white"],W//2,H//2+115,center=True)


if __name__=="__main__":
    game=GameScreen()
    running=True
    while running:
        for event in pygame.event.get():
            if event.type==pygame.QUIT: running=False; break
            if event.type==pygame.KEYDOWN:
                if event.key==pygame.K_F11 or (event.key==pygame.K_RETURN and event.mod & pygame.KMOD_ALT):
                    toggle_fullscreen(); continue
            if event.type==pygame.VIDEORESIZE and not fullscreen:
                screen=pygame.display.set_mode((event.w,event.h),pygame.RESIZABLE); continue
            event=_patch_event_pos(event)
            game.handle(event)
        game.update()
        game.draw(render_surf)
        scale,ox,oy=get_scale_offset()
        scaled=pygame.transform.smoothscale(render_surf,(int(W*scale),int(H*scale)))
        screen.fill((0,0,0)); screen.blit(scaled,(int(ox),int(oy)))
        pygame.display.flip()
        clock.tick(FPS)
    pygame.quit(); sys.exit()
