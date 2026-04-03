import pygame
import sys
import random
import json
import socket
import threading

# ========================
# CONFIGURATION PYGAME
# ========================
pygame.init()
WIDTH, HEIGHT = 1000, 650
WIN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("🐺 Loup-Garou - Woolfy Style")

FONT       = pygame.font.SysFont("georgia", 22)
FONT_SMALL = pygame.font.SysFont("georgia", 17)
BIG_FONT   = pygame.font.SysFont("georgia", 42, bold=True)
MED_FONT   = pygame.font.SysFont("georgia", 28, bold=True)
FPS = 60

# ========================
# COULEURS
# ========================
BG_DARK      = (18, 14, 28)
BG_PANEL     = (30, 24, 46)
ACCENT_RED   = (180, 40, 40)
ACCENT_GOLD  = (210, 170, 60)
ACCENT_BLUE  = (60, 100, 200)
CARD_BG      = (38, 30, 58)
CARD_BORDER  = (80, 60, 110)
WHITE        = (245, 240, 255)
GRAY_LIGHT   = (180, 170, 200)
GRAY_DARK    = (80, 70, 100)
BLACK        = (0, 0, 0)
GREEN        = (50, 180, 80)
INPUT_BG     = (28, 22, 42)
INPUT_ACTIVE = (50, 40, 80)

# ========================
# CLASSES DE BASE
# ========================
class Joueur:
    def __init__(self, nom):
        self.nom    = nom
        self.role   = None
        self.vivant = True

    def __str__(self):
        return f"{self.nom} ({'Vivant' if self.vivant else 'Mort'}) - {self.role.nom if self.role else 'Aucun'}"


class Role:
    def __init__(self, nom, description, pouvoir="aucun"):
        self.nom         = nom
        self.description = description
        self.pouvoir     = pouvoir   # "tuer", "voir", "soigner", "aucun"

    def action_nuit(self, jeu, joueur):
        pass


class LoupGarou(Role):
    def __init__(self):
        super().__init__("Loup-Garou", "Chaque nuit, les loups choisissent une victime à dévorer.", "tuer")

    def action_nuit(self, jeu, joueur):
        vivants = [j for j in jeu.joueurs if j.vivant and j != joueur]
        if vivants:
            cible = random.choice(vivants)
            cible.vivant = False


class Villageois(Role):
    def __init__(self):
        super().__init__("Villageois", "Aucune capacité spéciale. Sa force : observer et voter.", "aucun")


class Voyante(Role):
    def __init__(self):
        super().__init__("Voyante", "Peut découvrir le rôle secret d'un joueur chaque nuit.", "voir")

    def action_nuit(self, jeu, joueur):
        vivants = [j for j in jeu.joueurs if j != joueur]
        if vivants:
            cible = random.choice(vivants)
            print(f"La voyante voit que {cible.nom} est {cible.role.nom}")


class Sorciere(Role):
    def __init__(self):
        super().__init__("Sorcière", "Possède une potion de vie et une potion de mort (usage unique).", "soigner")
        self.potion_vie  = True
        self.potion_mort = True


class Chasseur(Role):
    def __init__(self):
        super().__init__("Chasseur", "À sa mort, il désigne immédiatement un joueur à éliminer.", "tuer")
        self.peut_tirer = True


# ========================
# CLASSE BOUTON
# ========================
class Bouton:
    def __init__(self, x, y, w, h, text,
                 couleur=BG_PANEL, hover=ACCENT_BLUE,
                 text_color=WHITE, border=CARD_BORDER,
                 fonction=None, icon=""):
        self.rect       = pygame.Rect(x, y, w, h)
        self.text       = text
        self.icon       = icon
        self.couleur    = couleur
        self.hover      = hover
        self.text_color = text_color
        self.border     = border
        self.fonction   = fonction
        self._hovered   = False

    def draw(self, win):
        mouse_pos = pygame.mouse.get_pos()
        self._hovered = self.rect.collidepoint(mouse_pos)
        col = self.hover if self._hovered else self.couleur

        pygame.draw.rect(win, col, self.rect, border_radius=10)
        pygame.draw.rect(win, self.border if not self._hovered else ACCENT_GOLD,
                         self.rect, 2, border_radius=10)

        label = f"{self.icon} {self.text}" if self.icon else self.text
        text_surf = FONT.render(label, True, self.text_color)
        win.blit(text_surf, (
            self.rect.x + self.rect.w // 2 - text_surf.get_width() // 2,
            self.rect.y + self.rect.h // 2 - text_surf.get_height() // 2
        ))

    def clic(self, pos):
        if self.rect.collidepoint(pos) and self.fonction:
            self.fonction()


# ========================
# CHAMP TEXTE
# ========================
class ChampTexte:
    def __init__(self, x, y, w, h, placeholder=""):
        self.rect        = pygame.Rect(x, y, w, h)
        self.texte       = ""
        self.placeholder = placeholder
        self.active      = False

    def draw(self, win):
        col = INPUT_ACTIVE if self.active else INPUT_BG
        pygame.draw.rect(win, col, self.rect, border_radius=8)
        border_col = ACCENT_GOLD if self.active else CARD_BORDER
        pygame.draw.rect(win, border_col, self.rect, 2, border_radius=8)

        if self.texte:
            surf = FONT.render(self.texte, True, WHITE)
        else:
            surf = FONT_SMALL.render(self.placeholder, True, GRAY_DARK)

        win.blit(surf, (self.rect.x + 10,
                        self.rect.y + self.rect.h // 2 - surf.get_height() // 2))

        # Curseur clignotant
        if self.active and (pygame.time.get_ticks() // 500) % 2 == 0:
            cx = self.rect.x + 10 + FONT.size(self.texte)[0] + 2
            cy = self.rect.y + 6
            pygame.draw.line(win, ACCENT_GOLD, (cx, cy), (cx, self.rect.y + self.rect.h - 6), 2)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.texte = self.texte[:-1]
            elif event.key not in (pygame.K_RETURN, pygame.K_TAB):
                self.texte += event.unicode


# ========================
# UTILITAIRES GRAPHIQUES
# ========================
def draw_bg(win):
    """Fond sombre avec légère texture."""
    win.fill(BG_DARK)
    # Lignes décoratives discrètes
    for i in range(0, HEIGHT, 80):
        pygame.draw.line(win, (25, 20, 38), (0, i), (WIDTH, i), 1)

def draw_title(win, text, y=30, color=ACCENT_GOLD):
    surf = BIG_FONT.render(text, True, color)
    win.blit(surf, (WIDTH // 2 - surf.get_width() // 2, y))

def draw_subtitle(win, text, y, color=GRAY_LIGHT):
    surf = MED_FONT.render(text, True, color)
    win.blit(surf, (WIDTH // 2 - surf.get_width() // 2, y))

def draw_card(win, x, y, w, h, title, desc, color=ACCENT_RED, pouvoir=""):
    """Carte visuelle pour un rôle."""
    pygame.draw.rect(win, CARD_BG, (x, y, w, h), border_radius=12)
    pygame.draw.rect(win, color, (x, y, w, 6), border_radius=12)
    pygame.draw.rect(win, CARD_BORDER, (x, y, w, h), 2, border_radius=12)

    # Titre
    t = MED_FONT.render(title, True, color)
    win.blit(t, (x + 12, y + 14))

    # Séparateur
    pygame.draw.line(win, CARD_BORDER, (x + 10, y + 46), (x + w - 10, y + 46), 1)

    # Description (wrap simple)
    words = desc.split()
    line, lines = "", []
    for w_word in words:
        test = line + w_word + " "
        if FONT_SMALL.size(test)[0] < w - 24:
            line = test
        else:
            lines.append(line)
            line = w_word + " "
    lines.append(line)

    for i, ln in enumerate(lines[:3]):
        s = FONT_SMALL.render(ln.strip(), True, GRAY_LIGHT)
        win.blit(s, (x + 12, y + 54 + i * 20))

    # Pouvoir
    if pouvoir and pouvoir != "aucun":
        ps = FONT_SMALL.render(f"⚡ {pouvoir}", True, ACCENT_GOLD)
        win.blit(ps, (x + 12, y + h - 26))

def draw_panel(win, x, y, w, h):
    pygame.draw.rect(win, BG_PANEL, (x, y, w, h), border_radius=14)
    pygame.draw.rect(win, CARD_BORDER, (x, y, w, h), 2, border_radius=14)

def draw_msg(win, text, y, color=WHITE):
    surf = FONT.render(text, True, color)
    win.blit(surf, (WIDTH // 2 - surf.get_width() // 2, y))


# ========================
# RÉSEAU
# ========================
PORT = 5566
parties_trouvees = []   # list of (ip, name)
client_socket    = None
server_socket    = None
clients_list     = []
is_host          = False

def broadcast(msg: str):
    data = msg.encode("utf-8")
    for c in clients_list[:]:
        try:
            c.send(data)
        except:
            clients_list.remove(c)

def handle_client(conn, addr):
    try:
        nom = conn.recv(1024).decode("utf-8")
        clients_list.append(conn)
        broadcast(f"JOINED:{nom}")
    except:
        pass

def start_server_thread(nom_partie: str):
    global server_socket, is_host
    is_host = True
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("0.0.0.0", PORT))
    server_socket.listen(10)

    # Broadcast UDP pour annonce
    def announce():
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while is_host:
            try:
                udp.sendto(f"LOUPGAROU:{nom_partie}".encode(), ("<broadcast>", PORT + 1))
                pygame.time.wait(1000)
            except:
                break
        udp.close()

    threading.Thread(target=announce, daemon=True).start()

    def accept_loop():
        while is_host:
            try:
                conn, addr = server_socket.accept()
                threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
            except:
                break

    threading.Thread(target=accept_loop, daemon=True).start()

def scan_reseau():
    """Écoute les broadcasts UDP pour trouver des parties."""
    global parties_trouvees
    parties_trouvees = []
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp.bind(("", PORT + 1))
    udp.settimeout(2.0)
    try:
        while True:
            data, addr = udp.recvfrom(1024)
            msg = data.decode()
            if msg.startswith("LOUPGAROU:"):
                nom = msg[len("LOUPGAROU:"):]
                entry = (addr[0], nom)
                if entry not in parties_trouvees:
                    parties_trouvees.append(entry)
    except socket.timeout:
        pass
    udp.close()

def join_server(ip: str, nom_joueur: str):
    global client_socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((ip, PORT))
    client_socket.send(nom_joueur.encode("utf-8"))


# ========================
# CLASSE JEU
# ========================
class Jeu:
    def __init__(self):
        self.joueurs           = []
        self.roles_disponibles = [
            LoupGarou(), Villageois(), Voyante(), Sorciere(), Chasseur()
        ]
        self.roles_custom      = []
        self.etat              = "menu_reseau"
        self.boutons           = []
        self.champs            = []
        self.message           = ""
        self.scroll_roles      = 0
        self.scroll_config     = 0
        self.scan_en_cours     = False
        self.nom_partie        = ""

        # Champs
        self.champ_nom_role  = ChampTexte(200, 220, 600, 42, "Nom du rôle...")
        self.champ_desc_role = ChampTexte(200, 310, 600, 42, "Description du rôle...")
        self.champ_pvr_role  = ChampTexte(200, 400, 600, 42, "Pouvoir : tuer / voir / soigner / aucun")
        self.champ_joueur    = ChampTexte(200, 280, 600, 42, "Nom du joueur...")
        self.champ_ip        = ChampTexte(200, 300, 500, 42, "Adresse IP du serveur...")
        self.champ_partie    = ChampTexte(200, 280, 600, 42, "Nom de votre partie...")

        # Configuration des rôles pour la partie
        # {nom_role: {"actif": bool, "quantite": int}}
        self.config_roles = {}

        self.charger_roles()
        self._init_config_roles()
        self._set_menu_reseau()

    def _init_config_roles(self):
        """Initialise la config avec tous les rôles disponibles."""
        for role in self.roles_disponibles:
            if role.nom not in self.config_roles:
                # Loup-Garou actif par défaut avec 1, Villageois actif avec 2, reste désactivé
                if role.nom == "Loup-Garou":
                    self.config_roles[role.nom] = {"actif": True,  "quantite": 1}
                elif role.nom == "Villageois":
                    self.config_roles[role.nom] = {"actif": True,  "quantite": 2}
                else:
                    self.config_roles[role.nom] = {"actif": False, "quantite": 1}

    # ── Rôles ───────────────────────────────────────────
    def ajouter_role_custom(self):
        nom  = self.champ_nom_role.texte.strip()
        desc = self.champ_desc_role.texte.strip()
        pvr  = self.champ_pvr_role.texte.strip().lower() or "aucun"
        if not nom or not desc:
            self.message = "⚠ Remplis le nom et la description !"
            return
        role = Role(nom, desc, pvr)
        self.roles_custom.append(role)
        self.roles_disponibles.append(role)
        self.sauvegarder_roles()
        self.champ_nom_role.texte  = ""
        self.champ_desc_role.texte = ""
        self.champ_pvr_role.texte  = ""
        self.message = f"✔ Rôle « {nom} » ajouté !"

    def sauvegarder_roles(self):
        data = [{"nom": r.nom, "description": r.description, "pouvoir": r.pouvoir}
                for r in self.roles_disponibles]
        with open("roles.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def charger_roles(self):
        try:
            with open("roles.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            noms_de_base = {"Loup-Garou", "Villageois", "Voyante", "Sorcière", "Chasseur"}
            for r in data:
                if r["nom"] not in noms_de_base and \
                   r["nom"] not in [x.nom for x in self.roles_disponibles]:
                    self.roles_disponibles.append(
                        Role(r["nom"], r["description"], r.get("pouvoir", "aucun"))
                    )
        except FileNotFoundError:
            pass
        self._init_config_roles()

    # ── Navigation ──────────────────────────────────────
    def changer_etat(self, etat):
        self.etat    = etat
        self.message = ""
        self.champs  = []
        if   etat == "menu_reseau":      self._set_menu_reseau()
        elif etat == "creer_serveur":    self._set_creer_serveur()
        elif etat == "rejoindre":        self._set_rejoindre()
        elif etat == "scan_parties":     self._set_scan()
        elif etat == "menu_principal":   self._set_menu_principal()
        elif etat == "ajouter_joueur":   self._set_ajouter_joueur()
        elif etat == "voir_roles":       self._set_voir_roles()
        elif etat == "ajouter_role":     self._set_ajouter_role()
        elif etat == "config_roles":     self._set_config_roles()
        elif etat == "partie":           self._set_partie()

    def _btn(self, x, y, w, h, txt, cible=None, fn=None, icon="", color=BG_PANEL, hover=ACCENT_BLUE):
        if fn is None and cible is not None:
            fn = lambda c=cible: self.changer_etat(c)
        return Bouton(x, y, w, h, txt, couleur=color, hover=hover,
                      fonction=fn, icon=icon)

    def _btn_retour(self, cible="menu_principal"):
        return self._btn(30, HEIGHT - 70, 160, 44, "← Retour", cible,
                         color=GRAY_DARK, hover=(100, 80, 130))

    # ── Menus ────────────────────────────────────────────
    def _set_menu_reseau(self):
        cx = WIDTH // 2 - 175
        self.boutons = [
            self._btn(cx, 220, 350, 60, "Créer un serveur", "creer_serveur",
                      icon="🖥", color=(60, 40, 80), hover=ACCENT_RED),
            self._btn(cx, 310, 350, 60, "Rejoindre une partie", "rejoindre",
                      icon="🌐", color=(40, 55, 80), hover=ACCENT_BLUE),
            self._btn(cx, 400, 350, 60, "Quitter",
                      fn=lambda: sys.exit(), icon="✕",
                      color=(60, 30, 30), hover=(160, 40, 40)),
        ]

    def _set_creer_serveur(self):
        self.champs = [self.champ_partie]
        self.champ_partie.texte = ""

        def lancer():
            nom = self.champ_partie.texte.strip() or "Partie sans nom"
            self.nom_partie = nom
            threading.Thread(target=start_server_thread, args=(nom,), daemon=True).start()
            self.message = f"✔ Serveur lancé : « {nom} »"
            self.changer_etat("menu_principal")

        self.boutons = [
            self._btn(WIDTH // 2 - 120, 380, 240, 50, "Lancer le serveur",
                      fn=lancer, icon="🚀", color=(60, 40, 80), hover=ACCENT_RED),
            self._btn_retour("menu_reseau"),
        ]

    def _set_rejoindre(self):
        self.champs = [self.champ_ip]
        self.champ_ip.texte = ""

        def scanner():
            self.changer_etat("scan_parties")

        def connexion_manuelle():
            ip  = self.champ_ip.texte.strip()
            nom = "Joueur"
            if ip:
                try:
                    join_server(ip, nom)
                    self.message = f"✔ Connecté à {ip}"
                    self.changer_etat("menu_principal")
                except Exception as e:
                    self.message = f"❌ Impossible de se connecter : {e}"

        self.boutons = [
            self._btn(WIDTH // 2 - 210, 400, 200, 50, "Scanner réseau",
                      fn=scanner, icon="📡", color=(40, 55, 80), hover=ACCENT_BLUE),
            self._btn(WIDTH // 2 + 20, 400, 200, 50, "Se connecter",
                      fn=connexion_manuelle, icon="→", color=(60, 40, 80), hover=GREEN),
            self._btn_retour("menu_reseau"),
        ]

    def _set_scan(self):
        self.message = "🔍 Scan du réseau local..."
        self.boutons = [self._btn_retour("rejoindre")]

        def do_scan():
            scan_reseau()
            self._refresh_scan_buttons()

        threading.Thread(target=do_scan, daemon=True).start()

    def _refresh_scan_buttons(self):
        self.boutons = [self._btn_retour("rejoindre")]
        if not parties_trouvees:
            self.message = "❌ Aucune partie trouvée."
            return
        self.message = f"✔ {len(parties_trouvees)} partie(s) trouvée(s)"
        for i, (ip, nom) in enumerate(parties_trouvees):
            def make_fn(addr, joueur_nom="Joueur"):
                def fn():
                    try:
                        join_server(addr, joueur_nom)
                        self.message = f"✔ Connecté à {addr}"
                        self.changer_etat("menu_principal")
                    except Exception as e:
                        self.message = f"❌ Erreur : {e}"
                return fn
            self.boutons.append(
                self._btn(WIDTH // 2 - 200, 180 + i * 70, 400, 56,
                          f"{nom}  [{ip}]", fn=make_fn(ip),
                          icon="🎮", color=(40, 55, 80), hover=ACCENT_BLUE)
            )

    def _set_menu_principal(self):
        cx = WIDTH // 2 - 175
        self.boutons = [
            self._btn(cx, 155, 350, 52, "Ajouter un joueur", "ajouter_joueur", icon="👤"),
            self._btn(cx, 220, 350, 52, "Voir les rôles",    "voir_roles",     icon="📜"),
            self._btn(cx, 285, 350, 52, "Ajouter un rôle",   "ajouter_role",   icon="✚",
                      color=(40, 60, 40), hover=GREEN),
            self._btn(cx, 350, 350, 52, "Configurer les rôles", "config_roles", icon="⚙",
                      color=(50, 45, 20), hover=(150, 120, 20)),
            self._btn(cx, 415, 350, 52, "Lancer la partie",  "partie",
                      icon="▶", color=(70, 30, 30), hover=ACCENT_RED),
            self._btn(cx, 480, 350, 52, "← Menu réseau", "menu_reseau",
                      color=GRAY_DARK, hover=(100, 80, 130)),
        ]

    def _set_ajouter_joueur(self):
        self.champs = [self.champ_joueur]
        self.champ_joueur.texte = ""

        def ajouter():
            nom = self.champ_joueur.texte.strip()
            if nom:
                self.joueurs.append(Joueur(nom))
                self.message = f"✔ {nom} ajouté !"
                self.champ_joueur.texte = ""
            else:
                self.message = "⚠ Saisis un nom."

        self.boutons = [
            self._btn(WIDTH // 2 - 100, 380, 200, 50, "Ajouter",
                      fn=ajouter, icon="✔", color=(40, 60, 40), hover=GREEN),
            self._btn_retour(),
        ]

    def _set_config_roles(self):
        """Écran de configuration : activer/désactiver les rôles et régler les quantités."""
        self._init_config_roles()
        self.scroll_config = 0
        self._rebuild_config_buttons()

    def _rebuild_config_buttons(self):
        """Reconstruit les boutons de config selon l'état actuel."""
        self.boutons = [self._btn_retour()]
        self.boutons.append(
            self._btn(WIDTH - 220, HEIGHT - 70, 190, 44, "Valider ✔",
                      fn=lambda: self.changer_etat("menu_principal"),
                      color=(40, 60, 40), hover=GREEN)
        )

        row_h   = 62
        start_y = 120 + self.scroll_config
        panel_x = 80

        for i, role in enumerate(self.roles_disponibles):
            y    = start_y + i * row_h
            cfg  = self.config_roles[role.nom]
            actif = cfg["actif"]

            # Bouton ON/OFF
            def make_toggle(rnom=role.nom):
                def fn():
                    self.config_roles[rnom]["actif"] = not self.config_roles[rnom]["actif"]
                    self._rebuild_config_buttons()
                return fn

            btn_col   = GREEN if actif else (80, 60, 60)
            btn_hover = (40, 160, 60) if actif else ACCENT_RED
            btn_label = "ON" if actif else "OFF"
            self.boutons.append(
                Bouton(panel_x + 540, y + 10, 80, 38, btn_label,
                       couleur=btn_col, hover=btn_hover, fonction=make_toggle())
            )

            # Bouton − quantité
            def make_minus(rnom=role.nom):
                def fn():
                    if self.config_roles[rnom]["quantite"] > 1:
                        self.config_roles[rnom]["quantite"] -= 1
                    self._rebuild_config_buttons()
                return fn

            # Bouton + quantité
            def make_plus(rnom=role.nom):
                def fn():
                    self.config_roles[rnom]["quantite"] += 1
                    self._rebuild_config_buttons()
                return fn

            if actif:
                self.boutons.append(
                    Bouton(panel_x + 640, y + 10, 36, 38, "−",
                           couleur=GRAY_DARK, hover=(120, 60, 60), fonction=make_minus())
                )
                self.boutons.append(
                    Bouton(panel_x + 720, y + 10, 36, 38, "+",
                           couleur=GRAY_DARK, hover=(40, 100, 40), fonction=make_plus())
                )

    def _set_voir_roles(self):
        self.scroll_roles = 0
        self.boutons = [self._btn_retour()]

    def _set_ajouter_role(self):
        self.champs = [self.champ_nom_role, self.champ_desc_role, self.champ_pvr_role]

        self.boutons = [
            self._btn(WIDTH // 2 - 110, 480, 220, 50, "Ajouter le rôle",
                      fn=self.ajouter_role_custom, icon="✔",
                      color=(40, 60, 40), hover=GREEN),
            self._btn_retour(),
        ]

    def _set_partie(self):
        if len(self.joueurs) < 3:
            self.message = "⚠ Minimum 3 joueurs requis !"
            self.changer_etat("menu_principal")
            return
        self._distribuer_roles()
        self.boutons = [
            self._btn(WIDTH - 200, HEIGHT - 70, 170, 44, "Fin de partie",
                      fn=lambda: self.changer_etat("menu_principal"),
                      color=(60, 30, 30), hover=ACCENT_RED)
        ]

    def _distribuer_roles(self):
        nb   = len(self.joueurs)
        pile = []

        # Classes de base par nom
        classes_base = {
            "Loup-Garou": LoupGarou, "Villageois": Villageois,
            "Voyante": Voyante, "Sorcière": Sorciere, "Chasseur": Chasseur,
        }

        for role in self.roles_disponibles:
            cfg = self.config_roles.get(role.nom, {"actif": False, "quantite": 1})
            if cfg["actif"]:
                cls = classes_base.get(role.nom)
                for _ in range(cfg["quantite"]):
                    if cls:
                        pile.append(cls())
                    else:
                        pile.append(Role(role.nom, role.description, role.pouvoir))

        # S'il n'y a pas assez de rôles actifs, on complète avec des Villageois
        while len(pile) < nb:
            pile.append(Villageois())

        # Si trop, on tronque (on garde les premiers)
        pile = pile[:nb]
        random.shuffle(pile)
        for j, r in zip(self.joueurs, pile):
            j.role = r

    # ── Affichage ───────────────────────────────────────
    def draw(self):
        draw_bg(WIN)

        if self.etat == "menu_reseau":
            self._draw_menu_reseau()
        elif self.etat == "creer_serveur":
            self._draw_creer_serveur()
        elif self.etat == "rejoindre":
            self._draw_rejoindre()
        elif self.etat == "scan_parties":
            self._draw_scan()
        elif self.etat == "menu_principal":
            self._draw_menu_principal()
        elif self.etat == "ajouter_joueur":
            self._draw_ajouter_joueur()
        elif self.etat == "voir_roles":
            self._draw_voir_roles()
        elif self.etat == "ajouter_role":
            self._draw_ajouter_role()
        elif self.etat == "config_roles":
            self._draw_config_roles()
        elif self.etat == "partie":
            self._draw_partie()

        # Boutons
        for b in self.boutons:
            b.draw(WIN)

        # Champs
        for c in self.champs:
            c.draw(WIN)

        # Message
        if self.message:
            col = GREEN if self.message.startswith("✔") else ACCENT_GOLD
            draw_msg(WIN, self.message, HEIGHT - 38, col)

        pygame.display.update()

    def _draw_menu_reseau(self):
        draw_title(WIN, "🐺  LOUP-GAROU  🐺", 70, ACCENT_RED)
        draw_subtitle(WIN, "Woolfy Style — Multijoueur réseau", 130, GRAY_LIGHT)

    def _draw_creer_serveur(self):
        draw_title(WIN, "Créer un serveur", 60)
        draw_panel(WIN, 150, 220, 700, 160)
        lbl = MED_FONT.render("Nom de la partie :", True, GRAY_LIGHT)
        WIN.blit(lbl, (200, 240))

    def _draw_rejoindre(self):
        draw_title(WIN, "Rejoindre une partie", 60)
        draw_panel(WIN, 150, 200, 700, 180)
        lbl = MED_FONT.render("IP du serveur (ou scanner) :", True, GRAY_LIGHT)
        WIN.blit(lbl, (200, 245))

    def _draw_scan(self):
        draw_title(WIN, "Scan du réseau local 📡", 60)

    def _draw_menu_principal(self):
        draw_title(WIN, "Menu Principal", 70)
        # Joueurs
        draw_panel(WIN, 680, 140, 290, HEIGHT - 200)
        lbl = MED_FONT.render(f"Joueurs ({len(self.joueurs)})", True, ACCENT_GOLD)
        WIN.blit(lbl, (695, 155))
        for i, j in enumerate(self.joueurs[:14]):
            s = FONT_SMALL.render(f"• {j.nom}", True, WHITE)
            WIN.blit(s, (700, 195 + i * 24))

    def _draw_ajouter_joueur(self):
        draw_title(WIN, "Ajouter un joueur", 70)
        draw_panel(WIN, 150, 240, 700, 120)
        lbl = MED_FONT.render("Nom du joueur :", True, GRAY_LIGHT)
        WIN.blit(lbl, (200, 258))
        # Liste
        draw_panel(WIN, 150, 420, 700, 160)
        lbl2 = FONT.render(f"Joueurs enregistrés ({len(self.joueurs)}) :", True, ACCENT_GOLD)
        WIN.blit(lbl2, (165, 430))
        for i, j in enumerate(self.joueurs[-7:]):
            s = FONT_SMALL.render(f"  • {j.nom}", True, WHITE)
            WIN.blit(s, (165, 455 + i * 19))

    def _draw_voir_roles(self):
        draw_title(WIN, "Rôles disponibles", 20)
        # Cartes
        cols, card_w, card_h = 3, 290, 130
        gap_x, gap_y = 30, 18
        start_x = (WIDTH - (cols * card_w + (cols - 1) * gap_x)) // 2
        start_y = 90 + self.scroll_roles

        colors = [ACCENT_RED, (60, 120, 180), (140, 60, 180),
                  (40, 150, 140), (190, 130, 30), (100, 60, 40)]

        for i, role in enumerate(self.roles_disponibles):
            col_i = i % cols
            row_i = i // cols
            x = start_x + col_i * (card_w + gap_x)
            y = start_y + row_i * (card_h + gap_y)
            col = colors[i % len(colors)]
            draw_card(WIN, x, y, card_w, card_h,
                      role.nom, role.description, col, role.pouvoir)

    def _draw_ajouter_role(self):
        draw_title(WIN, "Créer un nouveau rôle", 50)
        draw_panel(WIN, 150, 200, 700, 270)

        labels = [
            (200, 225, "Nom du rôle :"),
            (200, 315, "Description :"),
            (200, 405, "Pouvoir :"),
        ]
        for x, y, txt in labels:
            s = FONT.render(txt, True, GRAY_LIGHT)
            WIN.blit(s, (x, y))

    def _draw_config_roles(self):
        draw_title(WIN, "⚙  Configuration des rôles", 20, ACCENT_GOLD)

        COLORS = [ACCENT_RED, (60, 120, 180), (140, 60, 180),
                  (40, 150, 140), (190, 130, 30), (100, 60, 40)]

        row_h   = 62
        start_y = 120 + self.scroll_config
        panel_x = 80

        for i, role in enumerate(self.roles_disponibles):
            y    = start_y + i * row_h
            cfg  = self.config_roles[role.nom]
            actif = cfg["actif"]
            qty   = cfg["quantite"]
            col  = COLORS[i % len(COLORS)]

            # Fond de ligne
            alpha_col = col if actif else GRAY_DARK
            pygame.draw.rect(WIN, BG_PANEL, (panel_x, y, 820, row_h - 4), border_radius=10)
            pygame.draw.rect(WIN, alpha_col, (panel_x, y, 6, row_h - 4), border_radius=4)
            pygame.draw.rect(WIN, CARD_BORDER if actif else (50, 45, 60),
                             (panel_x, y, 820, row_h - 4), 1, border_radius=10)

            # Nom du rôle
            name_col = WHITE if actif else GRAY_DARK
            ns = MED_FONT.render(role.nom, True, name_col)
            WIN.blit(ns, (panel_x + 16, y + 10))

            # Description courte
            short_desc = role.description[:55] + ("…" if len(role.description) > 55 else "")
            ds = FONT_SMALL.render(short_desc, True, GRAY_DARK if not actif else GRAY_LIGHT)
            WIN.blit(ds, (panel_x + 16, y + 38))

            # Quantité (si actif)
            if actif:
                qty_surf = MED_FONT.render(str(qty), True, ACCENT_GOLD)
                WIN.blit(qty_surf, (panel_x + 686, y + 12))

        # Total
        total = sum(cfg["quantite"] for cfg in self.config_roles.values() if cfg["actif"])
        nb_j  = len(self.joueurs)
        col_total = GREEN if total == nb_j else ACCENT_RED
        msg = f"Total rôles actifs : {total}  /  Joueurs : {nb_j}"
        ts = FONT.render(msg, True, col_total)
        WIN.blit(ts, (WIDTH // 2 - ts.get_width() // 2, 78))

        if total != nb_j:
            hint = "(ajuste les quantités pour que le total = nombre de joueurs)"
            hs = FONT_SMALL.render(hint, True, ACCENT_GOLD)
            WIN.blit(hs, (WIDTH // 2 - hs.get_width() // 2, 100))

    def _draw_partie(self):
        draw_title(WIN, "☀️  Partie en cours  🌙", 20)
        draw_subtitle(WIN, f"{len(self.joueurs)} joueurs — Phase de discussion", 80, GRAY_LIGHT)

        # Joueurs en cercle
        import math
        cx, cy, rayon = WIDTH // 2, 360, 220
        n = len(self.joueurs)
        for i, j in enumerate(self.joueurs):
            angle = math.radians(i * 360 / n - 90)
            px = int(cx + rayon * math.cos(angle))
            py = int(cy + rayon * math.sin(angle))

            # Cercle joueur
            col = ACCENT_RED if isinstance(j.role, LoupGarou) else ACCENT_BLUE
            if not j.vivant:
                col = GRAY_DARK
            pygame.draw.circle(WIN, col, (px, py), 32)
            pygame.draw.circle(WIN, ACCENT_GOLD if j.vivant else GRAY_DARK, (px, py), 32, 3)

            # Initiales
            init = j.nom[:2].upper()
            s = MED_FONT.render(init, True, WHITE)
            WIN.blit(s, (px - s.get_width() // 2, py - s.get_height() // 2))

            # Nom
            ns = FONT_SMALL.render(j.nom, True, WHITE if j.vivant else GRAY_DARK)
            WIN.blit(ns, (px - ns.get_width() // 2, py + 38))

            # Rôle (si vivant, affiché seulement en mode hôte)
            if j.role and is_host:
                rs = FONT_SMALL.render(j.role.nom, True, col)
                WIN.blit(rs, (px - rs.get_width() // 2, py + 56))

        # Légende
        pygame.draw.circle(WIN, ACCENT_RED,  (40, HEIGHT - 90), 8)
        WIN.blit(FONT_SMALL.render("Loup-Garou", True, GRAY_LIGHT), (55, HEIGHT - 97))
        pygame.draw.circle(WIN, ACCENT_BLUE, (40, HEIGHT - 68), 8)
        WIN.blit(FONT_SMALL.render("Village",    True, GRAY_LIGHT), (55, HEIGHT - 75))


# ========================
# BOUCLE PRINCIPALE
# ========================
jeu   = Jeu()
clock = pygame.time.Clock()

while True:
    clock.tick(FPS)
    jeu.draw()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

        # Scroll dans la vue des rôles
        if event.type == pygame.MOUSEWHEEL and jeu.etat == "voir_roles":
            jeu.scroll_roles += event.y * 30
            jeu.scroll_roles = min(0, jeu.scroll_roles)

        # Scroll dans la config des rôles
        if event.type == pygame.MOUSEWHEEL and jeu.etat == "config_roles":
            jeu.scroll_config += event.y * 30
            jeu.scroll_config = min(0, jeu.scroll_config)
            jeu._rebuild_config_buttons()

        # Clics boutons
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for b in jeu.boutons:
                b.clic(event.pos)

        # Champs texte
        for c in jeu.champs:
            c.handle_event(event)

        # Tab pour naviguer entre champs
        if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB and jeu.champs:
            actifs = [i for i, c in enumerate(jeu.champs) if c.active]
            if actifs:
                idx = (actifs[0] + 1) % len(jeu.champs)
                for c in jeu.champs:
                    c.active = False
                jeu.champs[idx].active = True