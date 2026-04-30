"""
loup_ui_theme.py – Thème visuel partagé Loup-Garou (gothique nocturne)
CORRECTIONS :
  - clear_font_cache() pour réinitialiser après pygame.quit()/init()
  - Guards contre width/height <= 0 dans draw_glass_panel, draw_moon, draw_tree_silhouette
  - Particle: utilise age entier (plus léger)
  - wrap_text: gère max_chars <= 0
"""
import math
import random
import pygame

# ── Palette ──────────────────────────────────────────────────────────────────
BG_DEEP       = (6,   4,  14)
BG_TOP        = (10,  8,  22)
BG_MID        = (22, 14,  38)
BG_BOTTOM     = (38, 20,  56)
NIGHT_BLUE    = (14, 20,  52)
MOON_SILVER   = (210, 218, 235)
MOON_GLOW     = (180, 200, 240)
WOLF_RED      = (180,  40,  50)
WOLF_RED_DK   = (100,  20,  28)
BLOOD_RED     = (140,  20,  30)
MIST_PURPLE   = (80,   52, 110)
MIST_LIGHT    = (120,  88, 160)
GOLD_WARM     = (220, 178,  80)
GOLD_PALE     = (200, 168, 100)
CYAN_COOL     = (100, 190, 220)
WHITE_SOFT    = (230, 228, 238)
GREY_DIM      = (100,  96, 118)
GREY_DARK     = (44,   40,  58)
PANEL_BORDER  = (90,  70, 130, 140)
BTN_PRIMARY   = (70,  44, 110)
BTN_PRIMARY_H = (96,  62, 148)
BTN_DANGER    = (110, 28,  40)
BTN_DANGER_H  = (145, 38,  52)
BTN_SUCCESS   = (28,  90,  52)
BTN_SUCCESS_H = (38, 115,  68)
BTN_NEUTRAL   = (40,  36,  72)
BTN_NEUTRAL_H = (58,  52, 100)
BTN_BORDER    = (160, 130, 210)
BTN_BORDER_DIM = (80,  70, 110)
ROLE_WOLF_CLR    = (148, 28,  42)
ROLE_VILLAGE_CLR = (32,  90, 160)
ROLE_NEUTRAL_CLR = (80,  52, 120)

# ── Fonts ─────────────────────────────────────────────────────────────────────
_font_cache: dict = {}


def clear_font_cache():
    """À appeler après chaque pygame.init() pour invalider les anciennes fonts."""
    global _font_cache
    _font_cache = {}


def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    key = (size, bold)
    if key not in _font_cache:
        for name in ("Georgia", "Times New Roman", "Palatino Linotype", "serif"):
            try:
                f = pygame.font.SysFont(name, size, bold=bold)
                _font_cache[key] = f
                break
            except Exception:
                pass
        else:
            _font_cache[key] = pygame.font.Font(None, size)
    return _font_cache[key]


def scaled_fonts(sw: int, sh: int, bw: int, bh: int) -> dict:
    s = min(sw / bw, sh / bh)
    return {
        "xs":     get_font(max(13, int(15 * s))),
        "small":  get_font(max(15, int(18 * s))),
        "medium": get_font(max(20, int(24 * s))),
        "big":    get_font(max(28, int(36 * s)), bold=True),
        "title":  get_font(max(38, int(52 * s)), bold=True),
        "huge":   get_font(max(48, int(66 * s)), bold=True),
    }


# ── Dessin ────────────────────────────────────────────────────────────────────

def draw_gradient_bg(surface: pygame.Surface, top=BG_TOP, bottom=BG_BOTTOM):
    w, h = surface.get_size()
    for y in range(h):
        t = y / max(1, h - 1)
        c = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        pygame.draw.line(surface, c, (0, y), (w, y))


def draw_glass_panel(surface: pygame.Surface, rect: pygame.Rect,
                     radius: int = 18, alpha_fill: int = 210,
                     border_color=PANEL_BORDER, highlight: bool = True):
    r = pygame.Rect(rect)
    if r.width <= 0 or r.height <= 0:
        return
    panel = pygame.Surface((r.width, r.height), pygame.SRCALPHA)
    pygame.draw.rect(panel, (*BG_MID, alpha_fill), (0, 0, r.width, r.height), border_radius=radius)
    bc3 = border_color[:3]
    ba  = border_color[3] if len(border_color) == 4 else 180
    pygame.draw.rect(panel, (*bc3, ba), (0, 0, r.width, r.height), width=1, border_radius=radius)
    if highlight and r.height > 6:
        hl_h = max(2, r.height // 3)
        hl_w = max(1, r.width - 4)
        hl = pygame.Surface((hl_w, hl_h), pygame.SRCALPHA)
        for row in range(hl.get_height()):
            a = int(26 * (1 - row / hl.get_height()))
            pygame.draw.line(hl, (255, 255, 255, a), (2, row), (hl_w - 2, row))
        panel.blit(hl, (2, 2))
    surface.blit(panel, r.topleft)


def draw_text(surface: pygame.Surface, text: str, font: pygame.font.Font,
              color, center=None, topleft=None, shadow: bool = False) -> pygame.Rect:
    if shadow:
        sh = font.render(text, True, (0, 0, 0))
        sr = sh.get_rect()
        if center:
            sr.center = (center[0] + 2, center[1] + 2)
        elif topleft:
            sr.topleft = (topleft[0] + 2, topleft[1] + 2)
        surface.blit(sh, sr)
    img = font.render(text, True, color)
    r = img.get_rect()
    if center is not None:
        r.center = center
    if topleft is not None:
        r.topleft = topleft
    surface.blit(img, r)
    return r


def wrap_text(text: str, max_chars: int) -> list:
    if max_chars <= 0:
        return [text] if text else []
    words = text.split()
    if not words:
        return []
    lines, cur = [], ""
    for w in words:
        test = w if not cur else cur + " " + w
        if len(test) <= max_chars:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_moon(surface: pygame.Surface, cx: int, cy: int, radius: int, t: float = 0.0):
    if radius <= 0:
        return
    halo_r = int(radius * (1.05 + 0.04 * math.sin(t * 1.5)))
    sz = halo_r * 2 + 20
    halo = pygame.Surface((sz, sz), pygame.SRCALPHA)
    for step in range(8):
        hr = halo_r + step * 3
        a = max(0, 28 - step * 4)
        pygame.draw.circle(halo, (200, 210, 255, a), (sz // 2, sz // 2), hr)
    surface.blit(halo, (cx - sz // 2, cy - sz // 2))
    pygame.draw.circle(surface, (195, 205, 230), (cx, cy), radius)
    pygame.draw.circle(surface, (175, 185, 215), (cx, cy), radius, 2)
    for ox, oy, r2 in [(-radius // 4, -radius // 5, max(1, radius // 8)),
                        (radius // 5,  radius // 4,  max(1, radius // 10)),
                        (-radius // 6, radius // 5,  max(1, radius // 12))]:
        pygame.draw.circle(surface, (170, 180, 210), (cx + ox, cy + oy), r2)
        pygame.draw.circle(surface, (155, 165, 195), (cx + ox, cy + oy), r2, 1)


def draw_tree_silhouette(surface: pygame.Surface, x: int, bottom: int,
                          height: int, color=(8, 12, 24)):
    if height <= 4:
        return
    tw = max(3, height // 12)
    th = max(3, height // 5)
    pygame.draw.rect(surface, color, (x - tw // 2, bottom - th, tw, th))
    for i, (w, h2) in enumerate([(height // 2, height * 2 // 3),
                                   (height * 2 // 5, height // 2),
                                   (height // 3, height // 3)]):
        if w <= 0 or h2 <= 0:
            continue
        base_y = bottom - th - h2 * i // 3
        pygame.draw.polygon(surface, color, [
            (x - w // 2, base_y),
            (x + w // 2, base_y),
            (x, base_y - h2),
        ])


# ── Particules ────────────────────────────────────────────────────────────────

class Particle:
    __slots__ = ("x", "y", "vx", "vy", "size", "alpha", "color", "age", "max_age", "_w", "_h")

    def __init__(self, w: int, h: int):
        self._w, self._h = w, h
        self.x = self.y = 0.0
        self.vx = self.vy = 0.0
        self.size = 1.5
        self.alpha = 150
        self.color = (220, 200, 100)
        self.age = 0
        self.max_age = 300
        self.reset(init=True)

    def reset(self, init: bool = False):
        self.x = random.uniform(0, self._w)
        self.y = random.uniform(0, self._h) if init else float(self._h + 5)
        self.vy = random.uniform(-0.4, -0.12)
        self.vx = random.uniform(-0.12, 0.12)
        self.size = random.uniform(1.2, 2.8)
        self.alpha = random.randint(120, 200)
        self.color = random.choice([(220, 200, 100), (180, 220, 255),
                                    (160, 100, 220), (200, 220, 180)])
        self.max_age = random.randint(200, 420)
        self.age = 0

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.age += 1
        if self.y < -10 or self.age >= self.max_age:
            self.reset()

    def draw(self, surface: pygame.Surface):
        a = int(self.alpha * max(0.0, 1.0 - self.age / self.max_age))
        if a < 8:
            return
        r = max(1, int(self.size))
        sz = r * 4
        s = pygame.Surface((sz, sz), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, a), (sz // 2, sz // 2), r)
        surface.blit(s, (int(self.x) - sz // 2, int(self.y) - sz // 2))


class ParticleSystem:
    def __init__(self, w: int, h: int, count: int = 40):
        self.w, self.h = w, h
        self.particles = [Particle(w, h) for _ in range(count)]

    def resize(self, w: int, h: int):
        self.w, self.h = w, h
        for p in self.particles:
            p._w, p._h = w, h

    def update(self):
        for p in self.particles:
            p.update()

    def draw(self, surface: pygame.Surface):
        for p in self.particles:
            p.draw(surface)


# ── Widgets ───────────────────────────────────────────────────────────────────

class Button:
    def __init__(self, text: str, color=BTN_PRIMARY, hover=BTN_PRIMARY_H, icon: str = ""):
        self.text = text
        self.icon = icon
        self.color = color
        self.hover = hover
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.enabled = True

    def set_rect(self, rect):
        self.rect = pygame.Rect(rect)

    def draw(self, surface: pygame.Surface, font: pygame.font.Font,
             mouse_pos, enabled: bool = True):
        self.enabled = enabled
        hov = enabled and self.rect.collidepoint(mouse_pos)
        col = self.hover if hov else self.color
        if not enabled:
            col = tuple(max(0, c - 40) for c in col[:3])
        # Shadow
        sh = pygame.Surface((self.rect.w, self.rect.h), pygame.SRCALPHA)
        pygame.draw.rect(sh, (0, 0, 0, 65), (3, 4, self.rect.w, self.rect.h), border_radius=14)
        surface.blit(sh, self.rect.topleft)
        pygame.draw.rect(surface, col, self.rect, border_radius=14)
        if hov:
            hl = pygame.Surface((self.rect.w, max(1, self.rect.h // 2)), pygame.SRCALPHA)
            pygame.draw.rect(hl, (255, 255, 255, 18),
                             (0, 0, self.rect.w, self.rect.h // 2), border_radius=14)
            surface.blit(hl, self.rect.topleft)
        pygame.draw.rect(surface, BTN_BORDER if enabled else BTN_BORDER_DIM,
                         self.rect, 2, border_radius=14)
        label = (self.icon + "  " + self.text).strip() if self.icon else self.text
        draw_text(surface, label, font, WHITE_SOFT if enabled else GREY_DIM,
                  center=self.rect.center, shadow=True)

    def is_clicked(self, pos) -> bool:
        return self.enabled and self.rect.collidepoint(pos)


class InputBox:
    def __init__(self, placeholder: str = "", max_len: int = 20):
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.text = ""
        self.active = False
        self.placeholder = placeholder
        self.max_len = max_len
        self._tick = 0

    def set_rect(self, rect):
        self.rect = pygame.Rect(rect)

    def draw(self, surface: pygame.Surface, font: pygame.font.Font):
        self._tick += 1
        pygame.draw.rect(surface, (28, 20, 48) if self.active else (18, 14, 36),
                         self.rect, border_radius=12)
        pygame.draw.rect(surface, CYAN_COOL if self.active else (70, 60, 100),
                         self.rect, 2, border_radius=12)
        display = self.text if self.text else self.placeholder
        col = WHITE_SOFT if self.text else (120, 110, 145)
        cursor = "|" if self.active and (self._tick // 30) % 2 == 0 else ""
        img = font.render(display + cursor, True, col)
        max_w = self.rect.width - 28
        if img.get_width() > max_w:
            # show end of text
            display = display[-max(1, len(display) * max_w // (img.get_width() + 1)):]
            img = font.render(display + cursor, True, col)
        surface.blit(img, (self.rect.x + 14, self.rect.centery - img.get_height() // 2))

    def handle_event(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_RETURN:
                return True
            elif len(self.text) < self.max_len and event.unicode.isprintable():
                self.text += event.unicode
        return False

    def consume(self) -> str:
        t = self.text.strip()
        self.text = ""
        return t


class Stepper:
    def __init__(self, label: str, value: int, minimum: int, maximum: int):
        self.label = label
        self.value = value
        self.minimum = minimum
        self.maximum = maximum
        self._minus = pygame.Rect(0, 0, 0, 0)
        self._plus  = pygame.Rect(0, 0, 0, 0)
        self._disp  = pygame.Rect(0, 0, 0, 0)

    def set_layout(self, x: int, y: int, width: int):
        bw = 44
        self._minus = pygame.Rect(x, y, bw, 44)
        self._disp  = pygame.Rect(x + bw + 8, y, max(1, width - bw * 2 - 16), 44)
        self._plus  = pygame.Rect(x + width - bw, y, bw, 44)

    def draw(self, surface: pygame.Surface, font, small_font, mouse_pos):
        draw_text(surface, self.label, small_font, GOLD_PALE,
                  topleft=(self._minus.x, self._minus.y - 22))
        for btn, sym, col, hcol in [
            (self._minus, "-", BTN_DANGER,  BTN_DANGER_H),
            (self._plus,  "+", BTN_SUCCESS, BTN_SUCCESS_H),
        ]:
            c = hcol if btn.collidepoint(mouse_pos) else col
            pygame.draw.rect(surface, c, btn, border_radius=12)
            pygame.draw.rect(surface, BTN_BORDER, btn, 2, border_radius=12)
            draw_text(surface, sym, font, WHITE_SOFT, center=btn.center)
        pygame.draw.rect(surface, (18, 14, 34), self._disp, border_radius=12)
        pygame.draw.rect(surface, MIST_LIGHT, self._disp, 2, border_radius=12)
        draw_text(surface, str(self.value), font, MOON_SILVER, center=self._disp.center)

    def handle_click(self, pos) -> bool:
        if self._minus.collidepoint(pos):
            self.value = max(self.minimum, self.value - 1)
            return True
        if self._plus.collidepoint(pos):
            self.value = min(self.maximum, self.value + 1)
            return True
        return False
