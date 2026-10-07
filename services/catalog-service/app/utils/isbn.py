import re


def _valid_isbn10(s: str) -> bool:
    if not re.fullmatch(r"\d{9}[\dX]", s):
        return False
    return sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(s)) % 11 == 0


def _valid_isbn13(s: str) -> bool:
    if not re.fullmatch(r"\d{13}", s):
        return False
    return sum(int(c) * (3 if i % 2 else 1) for i, c in enumerate(s)) % 10 == 0


def normalize_isbn(raw: str) -> str:
    """Strip separators, uppercase, and verify the check digit. Raises ValueError if invalid."""
    s = re.sub(r"[\s-]", "", raw).upper()
    if not (_valid_isbn10(s) or _valid_isbn13(s)):
        raise ValueError("Enter a valid ISBN-10 or ISBN-13.")
    return s
