import random
from collections import Counter

MIN_PLAYERS = 3
MAX_PLAYERS = 12

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
        "description": "Lorsque vous mourrez, vous pouvez éliminer un autre joueur. Dans cette version, le rôle est affiché mais la riposte n'est pas encore jouable.",
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
    "Pyroman": {
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

AVAILABLE_ROLES = [role for role in ROLE_CATALOG.keys() if role != "Villageois"]
ROLES_ORDER = list(AVAILABLE_ROLES) + ["Villageois"]
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
    "Pyroman",
]
DEFAULT_ROLE_CONFIG = {
    "Loup-garou": 1,
    "Voyante": 1,
    "Sorcière": 1,
}


def role_details(role_name):
    return ROLE_CATALOG.get(role_name, ROLE_CATALOG["Villageois"])


def is_wolf_role(role_name):
    return role_name in {"Loup-garou", "Infect Père des Loups"}


def normalize_role_config(role_config=None):
    config = {role: 0 for role in AVAILABLE_ROLES}
    for role, value in DEFAULT_ROLE_CONFIG.items():
        config[role] = value
    if role_config:
        for role in AVAILABLE_ROLES:
            value = int(role_config.get(role, config.get(role, 0)))
            max_count = ROLE_CATALOG[role]["max"]
            if role == "Loup-garou":
                config[role] = max(1, min(max_count, value))
            else:
                config[role] = max(0, min(max_count, value))
    return config


def configured_special_roles(role_config=None):
    config = normalize_role_config(role_config)
    roles = []
    for role in AVAILABLE_ROLES:
        roles.extend([role] * config.get(role, 0))
    return roles


def min_players_for_config(role_config=None):
    return max(MIN_PLAYERS, len(configured_special_roles(role_config)) + 1)


def role_config_error(player_count, role_config=None):
    required = min_players_for_config(role_config)
    if player_count < required:
        return f"Il faut au moins {required} joueurs pour cette composition."
    return None


def camp_balance(player_count, role_config=None):
    config = normalize_role_config(role_config)
    wolves = config.get("Loup-garou", 0) + config.get("Infect Père des Loups", 0)
    others = sum(config.values()) - wolves
    village = max(0, player_count - wolves)
    if player_count <= 0:
        return {"village_ratio": 0.5, "wolves_ratio": 0.5, "counts": {"Villageois": 0, "Loups": 0}}
    return {
        "village_ratio": village / player_count,
        "wolves_ratio": wolves / player_count,
        "counts": {"Villageois": village, "Loups": wolves, "Specials": others},
    }


def build_roles(player_count, role_config=None):
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
    config = normalize_role_config(role_config)
    parts = []
    for role in AVAILABLE_ROLES:
        count = config.get(role, 0)
        if count:
            parts.append(role if count == 1 else f"{role} x{count}")
    return ", ".join(parts) if parts else "Villageois uniquement"


def count_alive_by_role(players):
    counter = Counter()
    for p in players:
        if p["alive"]:
            counter[p["role"]] += 1
    return counter


def check_winner(players):
    alive_wolves = sum(1 for p in players if p["alive"] and is_wolf_role(p["role"]))
    alive_non_wolves = sum(1 for p in players if p["alive"] and not is_wolf_role(p["role"]))
    if alive_wolves == 0:
        return "Village"
    if alive_wolves >= alive_non_wolves:
        return "Loups"
    return None


def serialize_players_for(player_id, players, reveal_all=False):
    data = []
    current_role = players[player_id]["role"] if 0 <= player_id < len(players) else None
    for p in players:
        entry = {
            "id": p["id"],
            "name": p["name"],
            "alive": p["alive"],
            "revealed_role": p.get("revealed_role"),
        }
        if reveal_all or p["id"] == player_id:
            entry["role"] = p["role"]
        elif is_wolf_role(p["role"]) and is_wolf_role(current_role):
            entry["role"] = p["role"]
        data.append(entry)
    return data
