
import random
from collections import Counter

MIN_PLAYERS = 4
MAX_PLAYERS = 12

ROLE_DEFS = {
    "Loup-garou": {
        "camp": "Loups",
        "aura": "Sombre",
        "max_count": 3,
        "description": "Chaque nuit, tu votes avec les autres loups pour éliminer un joueur.",
        "category": "wolf",
        "night_targets": 1,
    },
    "Infect Père des Loups": {
        "camp": "Loups",
        "aura": "Sombre",
        "max_count": 1,
        "description": "Ton vote nocturne compte double. Pendant la journée, tu peux mieux coordonner les loups. Dans cette version, le vote double est actif.",
        "category": "wolf",
        "night_targets": 1,
    },
    "Villageois": {
        "camp": "Village",
        "aura": "Claire",
        "max_count": 99,
        "description": "Tu n'as pas de pouvoir particulier. Tu dois observer, discuter et voter contre les loups.",
        "category": "villager",
        "night_targets": 0,
    },
    "Voyante": {
        "camp": "Village",
        "aura": "Claire",
        "max_count": 1,
        "description": "Chaque nuit, tu peux choisir un joueur pour découvrir son rôle.",
        "category": "seer",
        "night_targets": 1,
    },
    "Cupidon": {
        "camp": "Village",
        "aura": "Claire",
        "max_count": 1,
        "description": "Lors de la première nuit, tu choisis deux amoureux. Si l'un meurt, l'autre meurt aussi. Tu gagnes avec le village, ou avec les amoureux si ce sont les derniers survivants.",
        "category": "cupid",
        "night_targets": 2,
        "first_night_only": True,
    },
    "Sorciere": {
        "camp": "Village",
        "aura": "Claire",
        "max_count": 1,
        "description": "Tu as deux potions : une pour sauver la victime des loups, une pour tuer. Tu ne peux pas tuer pendant la première nuit.",
        "category": "witch",
        "night_targets": 1,
    },
    "Chasseur": {
        "camp": "Village",
        "aura": "Claire",
        "max_count": 1,
        "description": "Quand tu meurs, tu élimines immédiatement un autre joueur.",
        "category": "hunter",
        "night_targets": 0,
    },
    "Sniper": {
        "camp": "Solo / Alliance du mal",
        "aura": "Inconnue",
        "max_count": 1,
        "description": "Une cible t'est attribuée au début de la partie. Si le village élimine cette cible pendant le vote avant ta mort, tu accomplis ton objectif personnel.",
        "category": "sniper",
        "night_targets": 0,
    },
    "Salvateur": {
        "camp": "Village",
        "aura": "Claire",
        "max_count": 1,
        "description": "Chaque nuit, tu protèges une personne. Elle ne peut pas mourir cette nuit-là. Tu ne peux pas protéger deux nuits de suite la même personne.",
        "category": "protector",
        "night_targets": 1,
    },
    "Renard": {
        "camp": "Village",
        "aura": "Claire",
        "max_count": 1,
        "description": "La nuit, tu peux sentir trois personnes. S'il y a au moins un loup parmi elles, tu gardes ton pouvoir pour la nuit suivante. Sinon tu perds ton flair et deviens simple villageois.",
        "category": "fox",
        "night_targets": 3,
    },
    "Enfant sauvage": {
        "camp": "Village / Loups",
        "aura": "Claire",
        "max_count": 1,
        "description": "Au début de la partie, tu choisis un mentor. Si ce mentor meurt, tu deviens un loup-garou.",
        "category": "wild_child",
        "night_targets": 1,
        "first_night_only": True,
    },
    "Villageois maudit": {
        "camp": "Village / Loups",
        "aura": "Claire",
        "max_count": 1,
        "description": "Tu es villageois jusqu'à ce que les loups tentent de te tuer. À ce moment-là, tu deviens un loup-garou.",
        "category": "cursed",
        "night_targets": 0,
    },
    "Sirène": {
        "camp": "Solo",
        "aura": "Inconnue",
        "max_count": 1,
        "description": "La nuit, tu peux envoûter trois joueurs. Ensuite, tu peux tuer jusqu'à deux joueurs déjà envoûtés, ou envoûter trois nouveaux joueurs. Si tu meurs, tous les joueurs envoûtés meurent aussi. Tu gagnes si tous les autres joueurs sont morts ou envoûtés.",
        "category": "siren",
        "night_targets": 3,
    },
    "Pyroman": {
        "camp": "Solo",
        "aura": "Inconnue",
        "max_count": 1,
        "description": "Chaque nuit, tu peux recouvrir deux joueurs d'essence, ou brûler les joueurs déjà recouverts pour les tuer.",
        "category": "pyro",
        "night_targets": 2,
    },
}

CONFIGURABLE_ROLES = [name for name in ROLE_DEFS if name != "Villageois"]
ROLES_ORDER = [
    "Loup-garou",
    "Infect Père des Loups",
    "Voyante",
    "Cupidon",
    "Sorciere",
    "Chasseur",
    "Sniper",
    "Salvateur",
    "Renard",
    "Enfant sauvage",
    "Villageois maudit",
    "Sirène",
    "Pyroman",
    "Villageois",
]
DEFAULT_ROLE_CONFIG = {
    "Loup-garou": 1,
    "Infect Père des Loups": 0,
    "Voyante": 1,
    "Cupidon": 0,
    "Sorciere": 1,
    "Chasseur": 0,
    "Sniper": 0,
    "Salvateur": 0,
    "Renard": 0,
    "Enfant sauvage": 0,
    "Villageois maudit": 0,
    "Sirène": 0,
    "Pyroman": 0,
}


def get_role_def(role_name):
    return ROLE_DEFS.get(role_name, ROLE_DEFS["Villageois"])


def normalize_role_config(role_config=None):
    config = dict(DEFAULT_ROLE_CONFIG)
    if role_config:
        for role in DEFAULT_ROLE_CONFIG:
            value = int(role_config.get(role, config[role]))
            max_count = ROLE_DEFS[role]["max_count"]
            min_count = 1 if role == "Loup-garou" else 0
            config[role] = max(min_count, min(max_count, value))
    return config


def special_roles_count(role_config=None):
    config = normalize_role_config(role_config)
    return sum(config.values())


def build_roles(player_count, role_config=None):
    if player_count < MIN_PLAYERS:
        raise ValueError(f"Il faut au moins {MIN_PLAYERS} joueurs.")

    config = normalize_role_config(role_config)
    roles = []
    for role in ROLES_ORDER:
        if role == "Villageois":
            continue
        roles.extend([role] * config.get(role, 0))

    if len(roles) >= player_count:
        raise ValueError("Trop de rôles spéciaux pour ce nombre de joueurs.")

    while len(roles) < player_count:
        roles.append("Villageois")
    random.shuffle(roles)
    return roles


def role_config_label(role_config):
    config = normalize_role_config(role_config)
    parts = []
    for role in ROLES_ORDER:
        if role == "Villageois":
            continue
        count = config.get(role, 0)
        if count:
            if count == 1:
                parts.append(role)
            else:
                parts.append(f"{count} x {role}")
    return ", ".join(parts[:6]) + ("..." if len(parts) > 6 else "")


def team_of(player):
    role = player["role"]
    if role in ("Loup-garou", "Infect Père des Loups"):
        return "Loups"
    if role == "Sirène":
        return "Sirène"
    if role == "Pyroman":
        return "Pyroman"
    return "Village"


def count_alive_by_team(players):
    counter = Counter()
    for p in players:
        if p["alive"]:
            counter[team_of(p)] += 1
    return counter


def check_winner(players):
    alive = [p for p in players if p["alive"]]
    if not alive:
        return "Personne"

    lovers_alive = [p for p in alive if p.get("lover_ids")]
    if lovers_alive and all(all(other["id"] in p.get("lover_ids", []) or other["id"] == p["id"] for other in alive) for p in lovers_alive):
        return "Amoureux"

    sirens_alive = [p for p in alive if p["role"] == "Sirène"]
    if sirens_alive:
        for siren in sirens_alive:
            others = [p for p in alive if p["id"] != siren["id"]]
            if others and all(p.get("charmed_by") == siren["id"] for p in others):
                return "Sirène"

    pyros_alive = [p for p in alive if p["role"] == "Pyroman"]
    if pyros_alive and len(alive) == 1:
        return "Pyroman"

    alive_wolves = sum(1 for p in alive if team_of(p) == "Loups")
    alive_villagers = sum(1 for p in alive if team_of(p) == "Village")
    if alive_wolves == 0 and not sirens_alive and not pyros_alive:
        return "Village"
    if alive_wolves >= alive_villagers and alive_wolves > 0:
        return "Loups"
    return None


def serialize_players_for(player_id, players, reveal_all=False):
    data = []
    current_role = players[player_id]["role"] if players and player_id < len(players) and players[player_id]["role"] else None
    wolf_roles = {"Loup-garou", "Infect Père des Loups"}
    for p in players:
        entry = {
            "id": p["id"],
            "name": p["name"],
            "alive": p["alive"],
            "revealed_role": p.get("revealed_role"),
            "lover": player_id in p.get("lover_ids", []),
            "doused": p.get("doused", False) if reveal_all or p["id"] == player_id else False,
            "charmed": bool(p.get("charmed_by") is not None) if reveal_all or p["id"] == player_id else False,
        }
        if reveal_all or p["id"] == player_id:
            entry["role"] = p["role"]
        elif p["role"] in wolf_roles and current_role in wolf_roles:
            entry["role"] = p["role"]
        data.append(entry)
    return data
