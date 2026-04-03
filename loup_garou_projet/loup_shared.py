import random
from collections import Counter

MIN_PLAYERS = 4
MAX_PLAYERS = 12
ROLES_ORDER = ["Loup-garou", "Voyante", "Sorciere", "Villageois"]


def build_roles(player_count):
    if player_count < 4:
        raise ValueError("Il faut au moins 4 joueurs.")
    wolves = 1 if player_count <= 5 else 2 if player_count <= 8 else 3
    roles = ["Loup-garou"] * wolves + ["Voyante", "Sorciere"]
    while len(roles) < player_count:
        roles.append("Villageois")
    random.shuffle(roles)
    return roles


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
