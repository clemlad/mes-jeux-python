"""
loup_shared.py – Logique de jeu partagée entre le mode solo et le mode en ligne.

Contient le catalogue des rôles, les fonctions de construction de parties
et les fonctions de vérification de victoire. Ce module ne dépend pas de
pygame et peut être importé côté serveur comme côté client.
"""
import random
from collections import Counter

MIN_PLAYERS = 3
MAX_PLAYERS = 12

# Catalogue complet des rôles : chaque entrée définit le camp, l'aura,
# le nombre maximum autorisé, et si le rôle agit la nuit.
ROLE_CATALOG = {
    "Loup-garou": {
        "camp": "Loups",
        "aura": "Sombre",
        "max": 11,
        "night_action": True,
        "description": "Chaque nuit, les loups-garous choisissent ensemble une victime parmi les autres joueurs vivants.",
        "ui_icon": "LG",
    },
    "Infect Père des Loups": {
        "camp": "Loups",
        "aura": "Sombre",
        "max": 1,
        "night_action": False,
        "description": "Rôle de loup spécial. Dans cette version, il compte comme un loup supplémentaire dans le camp des loups.",
        "ui_icon": "IP",
    },
    "Voyante": {
        "camp": "Village",
        "aura": "Claire",
        "max": 1,
        "night_action": True,
        "description": "Chaque nuit, vous pouvez choisir un joueur pour découvrir son rôle.",
        "ui_icon": "VO",
    },
    "Cupidon": {
        "camp": "Village",
        "aura": "Claire",
        "max": 1,
        "night_action": False,
        "description": "Lors de la première nuit, vous pouvez former un couple amoureux. Dans cette version, le rôle est attribué et affiché, mais son pouvoir n'est pas encore jouable.",
        "ui_icon": "CU",
    },
    "Sorcière": {
        "camp": "Village",
        "aura": "Claire",
        "max": 1,
        "night_action": True,
        "description": "Vous avez une potion de soin et une potion de mort. Vous pouvez sauver la victime des loups ou empoisonner un joueur.",
        "ui_icon": "SO",
    },
    "Chasseur": {
        "camp": "Village",
        "aura": "Claire",
        "max": 1,
        "night_action": False,
        "description": "Lorsque vous mourrez, vous pouvez éliminer un autre joueur.",
        "ui_icon": "CH",
    },
    "Sniper": {
        "camp": "Solo",
        "aura": "Inconnue",
        "max": 1,
        "night_action": False,
        "description": "Une cible vous est attribuée. Vous gagnez si elle est éliminée par le vote du village avant votre mort. Condition spéciale non encore jouable dans cette version.",
        "ui_icon": "SN",
    },
    "Salvateur": {
        "camp": "Village",
        "aura": "Claire",
        "max": 1,
        "night_action": False,
        "description": "Chaque nuit, il protège une personne différente. Dans cette version, le rôle est attribué mais le pouvoir n'est pas encore jouable.",
        "ui_icon": "SA",
    },
    "Renard": {
        "camp": "Village",
        "aura": "Claire",
        "max": 1,
        "night_action": False,
        "description": "Il peut sentir parmi trois personnes si un loup se cache entre elles. Dans cette version, le rôle est attribué mais le pouvoir n'est pas encore jouable.",
        "ui_icon": "RE",
    },
    "Enfant sauvage": {
        "camp": "Village / Loups",
        "aura": "Claire",
        "max": 1,
        "night_action": False,
        "description": "Il choisit un mentor en début de partie et devient loup si ce mentor meurt. Dans cette version, le rôle est attribué mais le basculement n'est pas encore jouable.",
        "ui_icon": "ES",
    },
    "Villageois Maudit": {
        "camp": "Village / Loups",
        "aura": "Claire",
        "max": 1,
        "night_action": False,
        "description": "Villageois au départ, il devient loup si les loups tentent de le tuer. Dans cette version, le rôle est attribué mais la conversion n'est pas encore jouable.",
        "ui_icon": "VM",
    },
    "Sirène": {
        "camp": "Solo",
        "aura": "Inconnue",
        "max": 1,
        "night_action": False,
        "description": "La sirène envoûte des joueurs puis peut les tuer. Dans cette version, le rôle est attribué mais le pouvoir complet n'est pas encore jouable.",
        "ui_icon": "SI",
    },
    "Pyromane": {
        "camp": "Solo",
        "aura": "Inconnue",
        "max": 1,
        "night_action": False,
        "description": "Chaque nuit, il peut recouvrir des joueurs d'essence ou brûler ceux déjà marqués. Dans cette version, le rôle est attribué mais le pouvoir complet n'est pas encore jouable.",
        "ui_icon": "PY",
    },
    "Villageois": {
        "camp": "Village",
        "aura": "Claire",
        "max": 99,
        "night_action": False,
        "description": "Le villageois n'a pas de pouvoir spécial et vote le jour pour éliminer les loups.",
        "ui_icon": "VI",
    },
}

# "Villageois" est exclu de AVAILABLE_ROLES car il se place automatiquement
# en remplissage — on n'en configure jamais le nombre manuellement.
AVAILABLE_ROLES = [role for role in ROLE_CATALOG.keys() if role != "Villageois"]
ROLES_ORDER = list(AVAILABLE_ROLES) + ["Villageois"]

# Séparation UI : rôles affichés dans la section "classiques" vs "spéciaux"
CLASSIC_ROLE_NAMES = ["Loup-garou", "Voyante", "Sorcière"]
SPECIAL_ROLE_NAMES = [
    "Infect Père des Loups",
    "Cupidon",
    "Chasseur",
    "Salvateur",
    "Renard",
    "Enfant sauvage",
    "Villageois Maudit",
    "Sniper",
    "Sirène",
    "Pyromane",
]

# Configuration minimale par défaut : 1 loup, 1 voyante, 1 sorcière.
DEFAULT_ROLE_CONFIG = {
    "Loup-garou": 1,
    "Voyante": 1,
    "Sorcière": 1,
}


def role_details(role_name):
    """Retourne le dictionnaire de détails d'un rôle (ou Villageois par défaut)."""
    return ROLE_CATALOG.get(role_name, ROLE_CATALOG["Villageois"])


def is_wolf_role(role_name):
    """Retourne True si le rôle appartient au camp des loups."""
    return role_name in {"Loup-garou", "Infect Père des Loups"}


def normalize_role_config(role_config=None):
    """
    Retourne un dictionnaire complet {rôle: nombre} en partant de DEFAULT_ROLE_CONFIG
    et en appliquant role_config par-dessus. Contraint chaque valeur entre 0 et max.
    """
    config = {role: 0 for role in AVAILABLE_ROLES}
    for role, value in DEFAULT_ROLE_CONFIG.items():
        config[role] = value
    if role_config:
        for role in AVAILABLE_ROLES:
            value = int(role_config.get(role, config.get(role, 0)))
            max_count = ROLE_CATALOG[role]["max"]
            # Au moins 1 loup obligatoire, les autres peuvent être à 0
            if role == "Loup-garou":
                config[role] = max(1, min(max_count, value))
            else:
                config[role] = max(0, min(max_count, value))
    return config


def configured_special_roles(role_config=None):
    """Retourne la liste aplatie des rôles spéciaux selon la configuration."""
    config = normalize_role_config(role_config)
    roles = []
    for role in AVAILABLE_ROLES:
        roles.extend([role] * config.get(role, 0))
    return roles


def min_players_for_config(role_config=None):
    """Nombre minimum de joueurs requis : rôles spéciaux + au moins 1 villageois."""
    return max(MIN_PLAYERS, len(configured_special_roles(role_config)) + 1)


def role_config_error(player_count, role_config=None):
    """Retourne un message d'erreur si la config est incompatible avec player_count, sinon None."""
    required = min_players_for_config(role_config)
    if player_count < required:
        return f"Il faut au moins {required} joueurs pour cette composition."
    return None


def camp_balance(player_count, role_config=None):
    """Calcule le ratio village/loups pour l'UI d'équilibre du lobby."""
    config = normalize_role_config(role_config)
    wolves = config.get("Loup-garou", 0) + config.get("Infect Père des Loups", 0)
    others = sum(config.values()) - wolves
    village = max(0, player_count - wolves)
    if player_count <= 0:
        return {"village_ratio": 0.5, "wolves_ratio": 0.5, "counts": {"Villageois": 0, "Loups": 0}}
    return {
        "village_ratio": village / player_count,
        "wolves_ratio":  wolves / player_count,
        "counts": {"Villageois": village, "Loups": wolves, "Specials": others},
    }


def build_roles(player_count, role_config=None):
    """
    Construit et mélange la liste des rôles pour une partie.
    Remplit avec des Villageois jusqu'à atteindre player_count.
    """
    if player_count < MIN_PLAYERS:
        raise ValueError(f"Il faut au moins {MIN_PLAYERS} joueurs.")
    roles = configured_special_roles(role_config)
    if len(roles) >= player_count:
        raise ValueError("Trop de rôles spéciaux pour ce nombre de joueurs.")
    while len(roles) < player_count:
        roles.append("Villageois")
    random.shuffle(roles)
    return roles


def role_config_label(role_config):
    """Retourne une chaîne lisible de la composition (ex : 'Loup-garou, Voyante x2')."""
    config = normalize_role_config(role_config)
    parts = []
    for role in AVAILABLE_ROLES:
        count = config.get(role, 0)
        if count:
            parts.append(role if count == 1 else f"{role} x{count}")
    return ", ".join(parts) if parts else "Villageois uniquement"


def count_alive_by_role(players):
    """Retourne un Counter {rôle: nombre de joueurs vivants}."""
    counter = Counter()
    for p in players:
        if p["alive"]:
            counter[p["role"]] += 1
    return counter


def check_winner(players):
    """
    Vérifie si une équipe a gagné.
    Les loups gagnent dès qu'ils sont au moins aussi nombreux que les non-loups.
    Retourne "Village", "Loups", ou None si la partie continue.
    """
    alive_wolves     = sum(1 for p in players if p["alive"] and is_wolf_role(p["role"]))
    alive_non_wolves = sum(1 for p in players if p["alive"] and not is_wolf_role(p["role"]))
    if alive_wolves == 0:
        return "Village"
    if alive_wolves >= alive_non_wolves:
        return "Loups"
    return None


def serialize_players_for(player_id, players, reveal_all=False):
    """
    Sérialise la liste des joueurs du point de vue de player_id.
    Un joueur voit son propre rôle et celui des loups s'il est loup.
    En fin de partie (reveal_all=True), tous les rôles sont visibles.
    """
    data = []
    current_role = players[player_id]["role"] if 0 <= player_id < len(players) else None
    for p in players:
        entry = {
            "id":            p["id"],
            "name":          p["name"],
            "alive":         p["alive"],
            "revealed_role": p.get("revealed_role"),
        }
        if reveal_all or p["id"] == player_id:
            entry["role"] = p["role"]
        elif is_wolf_role(p["role"]) and is_wolf_role(current_role):
            # Les loups se connaissent entre eux
            entry["role"] = p["role"]
        data.append(entry)
    return data
