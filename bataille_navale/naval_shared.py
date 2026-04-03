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
        self.name = name
        self.size = size
        self.positions = []
        self.hits = set()
        self.known_sunk = False

    def place(self, positions):
        self.positions = list(positions)
        self.hits = set()
        self.known_sunk = False

    def register_hit(self, pos):
        if pos in self.positions:
            self.hits.add(pos)
            if self.is_sunk():
                self.known_sunk = True

    def is_sunk(self):
        if not self.positions:
            return self.known_sunk
        return len(self.hits) == len(self.positions)

    def to_dict(self, reveal_positions=True):
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
        self.ships = []
        self.shots = {}

    def inside(self, row, col):
        return 0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE

    def ship_at(self, row, col):
        for ship in self.ships:
            if (row, col) in ship.positions:
                return ship
        return None

    def ship_by_name(self, name):
        for ship in self.ships:
            if ship.name == name:
                return ship
        return None

    def neighborhood(self, row, col):
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                nr = row + dr
                nc = col + dc
                if self.inside(nr, nc):
                    yield nr, nc

    def touches_existing_ship(self, positions):
        occupied = {pos for ship in self.ships for pos in ship.positions}
        for row, col in positions:
            for neighbor in self.neighborhood(row, col):
                if neighbor in occupied and neighbor not in positions:
                    return True
        return False

    def can_place_ship(self, row, col, size, orientation, no_touching=False):
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
        for index, ship in enumerate(self.ships):
            if ship.name == name:
                return self.ships.pop(index)
        return None

    def remove_ship_at(self, row, col):
        ship = self.ship_at(row, col)
        if ship is None:
            return None
        self.remove_ship_by_name(ship.name)
        return ship

    def place_all_from_layout(self, layout):
        self.reset()
        for item in layout:
            ship = Ship(item["name"], item["size"])
            ship.place([tuple(p) for p in item["positions"]])
            self.ships.append(ship)

    def auto_place_all(self):
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
        return len(self.ships) > 0 and all(ship.is_sunk() for ship in self.ships)

    def serialize(self, reveal_positions=True):
        return {
            "ships": [ship.to_dict(reveal_positions=reveal_positions) for ship in self.ships],
            "shots": [
                {"row": row, "col": col, "result": result}
                for (row, col), result in self.shots.items()
            ],
        }

    @classmethod
    def from_state(cls, state):
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
    return [
        {"name": ship.name, "size": ship.size, "positions": [list(p) for p in ship.positions]}
        for ship in board.ships
    ]
