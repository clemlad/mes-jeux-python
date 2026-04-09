import random
from collections import Counter

MIN_PLAYERS = 4
MAX_PLAYERS = 12
AVAILABLE_ROLES = ["Loup-garou", "Voyante", "Sorciere", "Villageois"]
ROLES_ORDER = ["Loup-garou", "Voyante", "Sorciere", "Villageois"]
DEFAULT_ROLE_CONFIG = {
    "Loup-garou": 1,
    "Voyante": 1,
    "Sorciere": 1,
}


def normalize_role_config(role_config=None):
    config = dict(DEFAULT_ROLE_CONFIG)
    if role_config:
        for role in DEFAULT_ROLE_CONFIG:
            value = int(role_config.get(role, config[role]))
            if role == "Loup-garou":
                config[role] = max(1, min(3, value))
            else:
                config[role] = max(0, min(1, value))
    return config


def build_roles(player_count, role_config=None):
    if player_count < MIN_PLAYERS:
        raise ValueError(f"Il faut au moins {MIN_PLAYERS} joueurs.")

    config = normalize_role_config(role_config)
    roles = []
    roles.extend(["Loup-garou"] * config["Loup-garou"])
    if config["Voyante"]:
        roles.append("Voyante")
    if config["Sorciere"]:
        roles.append("Sorciere")

    if len(roles) >= player_count:
        raise ValueError("Trop de rôles spéciaux pour ce nombre de joueurs.")

    while len(roles) < player_count:
        roles.append("Villageois")
    random.shuffle(roles)
    return roles


def role_config_label(role_config):
    config = normalize_role_config(role_config)
    parts = [f"{config['Loup-garou']} loup(s)"]
    if config["Voyante"]:
        parts.append("voyante")
    if config["Sorciere"]:
        parts.append("sorcière")
    return ", ".join(parts)


def count_alive_by_role(players):
    counter = Counter()
    for p in players:
        if p["alive"]:
            counter[p["role"]] += 1
    return counter


def check_winner(players):
    alive_wolves = sum(1 for p in players if p["alive"] and p["role"] == "Loup-garou")
    alive_villagers = sum(1 for p in players if p["alive"] and p["role"] != "Loup-garou")
    if alive_wolves == 0:
        return "Village"
    if alive_wolves >= alive_villagers:
        return "Loups"
    return None


def serialize_players_for(player_id, players, reveal_all=False):
    data = []
    for p in players:
        entry = {
            "id": p["id"],
            "name": p["name"],
            "alive": p["alive"],
            "revealed_role": p.get("revealed_role"),
        }
        if reveal_all or p["id"] == player_id:
            entry["role"] = p["role"]
        elif p["role"] == "Loup-garou" and players[player_id]["role"] == "Loup-garou":
            entry["role"] = "Loup-garou"
        data.append(entry)
    return data
