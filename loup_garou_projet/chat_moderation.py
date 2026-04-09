import csv
import re
from pathlib import Path


class ChatModerator:
    def __init__(self, csv_path):
        self.csv_path = Path(csv_path)
        self.patterns = []
        self._load_patterns()

    def _compile_variant(self, text, match_type):
        text = (text or "").strip().lower()
        if not text:
            return None
        parts = re.split(r"\|", text)
        regex_parts = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            escaped = re.escape(part)
            escaped = escaped.replace(r"\ ", r"\s+")
            escaped = escaped.replace(r"\*", r"[*\\w]?")
            escaped = escaped.replace("0", "[0o]")
            escaped = escaped.replace("1", "[1i!l]")
            escaped = escaped.replace("3", "[3e]")
            escaped = escaped.replace("4", "[4a]")
            escaped = escaped.replace("5", "[5s]")
            escaped = escaped.replace("7", "[7t]")
            regex_parts.append(escaped)
        if not regex_parts:
            return None
        joined = "(?:" + "|".join(regex_parts) + ")"
        if match_type == "word":
            return re.compile(rf"(?i)(?<!\w){joined}(?!\w)")
        return re.compile(rf"(?i){joined}")

    def _load_patterns(self):
        if not self.csv_path.exists():
            return
        with self.csv_path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if (row.get("category") or "").strip().lower() == "normalization_rule":
                    continue
                match_type = (row.get("match_type") or "word").strip().lower()
                values = [
                    row.get("canonical_term", ""),
                    row.get("variants_or_patterns", ""),
                    row.get("acronym", ""),
                ]
                for value in values:
                    pattern = self._compile_variant(value, match_type)
                    if pattern is not None:
                        self.patterns.append(pattern)

    @staticmethod
    def _mask(match):
        text = match.group(0)
        return "*" * len(text)

    def moderate(self, message):
        clean = message
        hit = False
        for pattern in self.patterns:
            clean, count = pattern.subn(self._mask, clean)
            if count:
                hit = True
        return clean, hit
