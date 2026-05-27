import random

GRID_SIZE = 10
SHIPS_CONFIG = [
    ("Porte-avion", 5),
    ("Cuirassé", 4),
    ("Croiseur", 3),
    ("Sous-marin T", 4),
    ("Torpilleur", 2),
]

SUBMARINE_ORIENTATIONS = ["haut", "bas", "gauche", "droite"]
LETTERS = "ABCDEFGHIJ"


class Ship:
    def __init__(self, name, size):
        """
        Initialise un bateau avec son nom et sa taille.

        :param name: Nom du bateau (str), ex : 'Porte-avion'.
        :param size: Nombre de cases occupées (int).
        """
        self.name = name
        self.size = size
        self.positions = []
        self.hits = set()
        self.known_sunk = False

    def place(self, positions):
        """
        Enregistre les cases occupées par le bateau et réinitialise ses touches.

        :param positions: Liste de tuples (row, col) représentant les cases (list[tuple[int, int]]).
        """
        self.positions = list(positions)
        self.hits = set()
        self.known_sunk = False

    def register_hit(self, pos):
        """
        Enregistre un tir touché sur le bateau et marque known_sunk s'il est coulé.

        :param pos: Coordonnées touchées sous forme de tuple (row, col) (tuple[int, int]).
        """
        if pos in self.positions:
            self.hits.add(pos)
            if self.is_sunk():
                self.known_sunk = True

    def is_sunk(self):
        """
        Retourne True si toutes les cases du bateau ont été touchées.

        :return: bool
        """
        if not self.positions:
            return self.known_sunk
        return len(self.hits) == len(self.positions)

    def to_dict(self, reveal_positions=True):
        """
        Sérialise le bateau en dictionnaire pour transmission réseau ou sauvegarde.

        :param reveal_positions: Si True, inclut les positions complètes du bateau (bool).
                                  Si False, ne les inclut que si le bateau est coulé.
        :return: dict avec les clés 'name', 'size', 'hits', 'is_sunk', 'positions'.
        """
        sunk = self.is_sunk()
        return {
            "name": self.name,
            "size": self.size,
            "hits": [list(p) for p in self.hits],
            "is_sunk": sunk,
            "positions": [list(p) for p in self.positions] if (reveal_positions or sunk) else [],
        }


class Board:
    def __init__(self):
        self.ships = []
        self.shots = {}

    def reset(self):
        """Supprime tous les bateaux et tous les tirs de la grille."""
        self.ships = []
        self.shots = {}

    def inside(self, row, col):
        """
        Retourne True si la case (row, col) est dans les limites de la grille.

        :param row: Ligne (int), 0 à GRID_SIZE-1.
        :param col: Colonne (int), 0 à GRID_SIZE-1.
        :return: bool
        """
        return 0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE

    def ship_at(self, row, col):
        """
        Retourne le bateau occupant la case (row, col), ou None si elle est libre.

        :param row: Ligne (int).
        :param col: Colonne (int).
        :return: Ship ou None.
        """
        for ship in self.ships:
            if (row, col) in ship.positions:
                return ship
        return None

    def ship_by_name(self, name):
        """
        Retourne le bateau dont le nom correspond, ou None s'il n'est pas trouvé.

        :param name: Nom du bateau recherché (str).
        :return: Ship ou None.
        """
        for ship in self.ships:
            if ship.name == name:
                return ship
        return None

    def neighborhood(self, row, col):
        """
        Génère toutes les cases adjacentes (y compris diagonales) à (row, col) dans la grille.

        :param row: Ligne centrale (int).
        :param col: Colonne centrale (int).
        :return: Générateur de tuples (row, col).
        """
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                nr = row + dr
                nc = col + dc
                if self.inside(nr, nc):
                    yield nr, nc

    def touches_existing_ship(self, positions):
        """
        Retourne True si l'une des cases proposées touche (adjacent ou diagonal) un bateau déjà placé.

        :param positions: Liste de tuples (row, col) à vérifier (list[tuple[int, int]]).
        :return: bool
        """
        occupied = {pos for ship in self.ships for pos in ship.positions}
        for row, col in positions:
            for neighbor in self.neighborhood(row, col):
                if neighbor in occupied and neighbor not in positions:
                    return True
        return False

    def can_place_ship(self, row, col, size, orientation, no_touching=False):
        """
        Vérifie si un bateau standard (ligne ou colonne) peut être placé à la position donnée.

        :param row: Ligne de départ (int).
        :param col: Colonne de départ (int).
        :param size: Nombre de cases du bateau (int).
        :param orientation: 'H' pour horizontal, 'V' pour vertical (str).
        :param no_touching: Si True, interdit le contact avec d'autres bateaux (bool).
        :return: Tuple (bool, list[tuple[int, int]]) : validité et liste des positions.
        """
        positions = []
        for i in range(size):
            r = row + i if orientation == "V" else row
            c = col + i if orientation == "H" else col
            if not self.inside(r, c) or self.ship_at(r, c) is not None:
                return False, []
            positions.append((r, c))
        if no_touching and self.touches_existing_ship(positions):
            return False, []
        return True, positions

    def can_place_submarine(self, row, col, orientation, no_touching=False):
        """
        Vérifie si le sous-marin en T peut être placé autour de la case centrale.

        :param row: Ligne de la case centrale (int).
        :param col: Colonne de la case centrale (int).
        :param orientation: Direction de la branche du T : 'haut', 'bas', 'gauche' ou 'droite' (str).
        :param no_touching: Si True, interdit le contact avec d'autres bateaux (bool).
        :return: Tuple (bool, list[tuple[int, int]]) : validité et liste des positions.
        """
        if orientation == "haut":
            positions = [(row, col - 1), (row, col), (row, col + 1), (row - 1, col)]
        elif orientation == "bas":
            positions = [(row, col - 1), (row, col), (row, col + 1), (row + 1, col)]
        elif orientation == "gauche":
            positions = [(row - 1, col), (row, col), (row + 1, col), (row, col - 1)]
        elif orientation == "droite":
            positions = [(row - 1, col), (row, col), (row + 1, col), (row, col + 1)]
        else:
            return False, []

        if len(positions) != len(set(positions)):
            return False, []

        for r, c in positions:
            if not self.inside(r, c) or self.ship_at(r, c) is not None:
                return False, []
        if no_touching and self.touches_existing_ship(positions):
            return False, []
        return True, positions

    def place_ship(self, ship, row, col, orientation, no_touching=False):
        """
        Tente de placer un bateau sur la grille ; retourne True si le placement est valide.

        :param ship: Instance de Ship à placer (Ship).
        :param row: Ligne de départ ou case centrale pour le sous-marin (int).
        :param col: Colonne de départ ou case centrale pour le sous-marin (int).
        :param orientation: 'H', 'V' pour bateaux normaux ; 'haut'/'bas'/'gauche'/'droite' pour le sous-marin (str).
        :param no_touching: Si True, interdit le contact avec d'autres bateaux (bool).
        :return: bool
        """
        if ship.name == "Sous-marin T":
            valid, positions = self.can_place_submarine(row, col, orientation, no_touching=no_touching)
        else:
            valid, positions = self.can_place_ship(row, col, ship.size, orientation, no_touching=no_touching)

        if not valid or len(positions) != len(set(positions)):
            return False

        ship.place(positions)
        self.ships.append(ship)
        return True

    def remove_ship_by_name(self, name):
        """
        Retire et retourne le bateau ayant le nom donné, ou None s'il n'existe pas.

        :param name: Nom du bateau à retirer (str).
        :return: Ship ou None.
        """
        for index, ship in enumerate(self.ships):
            if ship.name == name:
                return self.ships.pop(index)
        return None

    def remove_ship_at(self, row, col):
        """
        Retire et retourne le bateau occupant la case (row, col), ou None si la case est libre.

        :param row: Ligne (int).
        :param col: Colonne (int).
        :return: Ship ou None.
        """
        ship = self.ship_at(row, col)
        if ship is None:
            return None
        self.remove_ship_by_name(ship.name)
        return ship

    def place_all_from_layout(self, layout):
        """
        Réinitialise la grille et place tous les bateaux à partir d'un layout sérialisé.

        :param layout: Liste de dicts avec les clés 'name', 'size', 'positions' (list[dict]).
        """
        self.reset()
        for item in layout:
            ship = Ship(item["name"], item["size"])
            ship.place([tuple(p) for p in item["positions"]])
            self.ships.append(ship)

    def auto_place_all(self):
        """
        Place automatiquement tous les bateaux en choisissant la configuration avec le meilleur espacement.
        Tente 220 placements aléatoires et conserve celui qui maximise le score d'espacement.
        """
        best_layout = None
        best_score = None

        for _ in range(220):
            candidate = Board()
            success = True
            order = SHIPS_CONFIG[:]
            random.shuffle(order)

            for name, size in order:
                placed = False
                attempts = 0
                while not placed and attempts < 600:
                    attempts += 1
                    row = random.randint(0, GRID_SIZE - 1)
                    col = random.randint(0, GRID_SIZE - 1)
                    orientation = random.choice(SUBMARINE_ORIENTATIONS if name == "Sous-marin T" else ["H", "V"])
                    placed = candidate.place_ship(Ship(name, size), row, col, orientation, no_touching=True)
                if not placed:
                    success = False
                    break

            if not success:
                continue

            score = candidate.spacing_score()
            if best_score is None or score > best_score:
                best_score = score
                best_layout = layout_from_board(candidate)

        if best_layout is None:
            self.reset()
            for name, size in SHIPS_CONFIG:
                placed = False
                while not placed:
                    row = random.randint(0, GRID_SIZE - 1)
                    col = random.randint(0, GRID_SIZE - 1)
                    orientation = random.choice(SUBMARINE_ORIENTATIONS if name == "Sous-marin T" else ["H", "V"])
                    placed = self.place_ship(Ship(name, size), row, col, orientation)
            return

        self.place_all_from_layout(best_layout)

    def spacing_score(self):
        """
        Calcule un score d'espacement total entre tous les bateaux (somme des distances minimales par paires).

        :return: int — plus la valeur est élevée, plus les bateaux sont dispersés.
        """
        if len(self.ships) < 2:
            return 0
        minima = []
        for i, ship_a in enumerate(self.ships):
            best = 999
            for j, ship_b in enumerate(self.ships):
                if i == j:
                    continue
                for ra, ca in ship_a.positions:
                    for rb, cb in ship_b.positions:
                        dist = abs(ra - rb) + abs(ca - cb)
                        if dist < best:
                            best = dist
            minima.append(best)
        return sum(minima)

    def receive_shot(self, row, col):
        """
        Enregistre un tir sur la grille et retourne son résultat.

        :param row: Ligne visée (int).
        :param col: Colonne visée (int).
        :return: Tuple ('already'/'miss'/'hit'/'sunk', Ship ou None).
        """
        if (row, col) in self.shots:
            return "already", None
        ship = self.ship_at(row, col)
        if ship is None:
            self.shots[(row, col)] = "miss"
            return "miss", None
        self.shots[(row, col)] = "hit"
        ship.register_hit((row, col))
        if ship.is_sunk():
            return "sunk", ship
        return "hit", ship

    def all_sunk(self):
        """Retourne True si tous les bateaux de la grille sont coulés (bool)."""
        return len(self.ships) > 0 and all(ship.is_sunk() for ship in self.ships)

    def serialize(self, reveal_positions=True):
        """
        Sérialise la grille en dictionnaire pour transmission réseau ou sauvegarde.

        :param reveal_positions: Si True, inclut les positions complètes de chaque bateau (bool).
        :return: dict avec les clés 'ships' (list) et 'shots' (list).
        """
        return {
            "ships": [ship.to_dict(reveal_positions=reveal_positions) for ship in self.ships],
            "shots": [
                {"row": row, "col": col, "result": result}
                for (row, col), result in self.shots.items()
            ],
        }

    @classmethod
    def from_state(cls, state):
        """
        Reconstruit une instance Board à partir d'un dictionnaire sérialisé (inverse de serialize).

        :param state: Dict avec les clés 'ships' et 'shots' (dict).
        :return: Board reconstruit.
        """
        board = cls()
        for ship_data in state.get("ships", []):
            ship = Ship(ship_data["name"], ship_data["size"])
            ship.place([tuple(p) for p in ship_data.get("positions", [])])
            ship.hits = {tuple(p) for p in ship_data.get("hits", [])}
            ship.known_sunk = bool(ship_data.get("is_sunk", False))
            board.ships.append(ship)
        for item in state.get("shots", []):
            board.shots[(item["row"], item["col"])] = item["result"]
        return board


def layout_from_board(board):
    """
    Extrait le layout (positions de tous les bateaux) d'une grille sous forme de liste de dicts.

    :param board: Instance de Board dont on extrait le layout (Board).
    :return: list[dict] avec les clés 'name', 'size', 'positions' pour chaque bateau.
    """
    return [
        {"name": ship.name, "size": ship.size, "positions": [list(p) for p in ship.positions]}
        for ship in board.ships
    ]
