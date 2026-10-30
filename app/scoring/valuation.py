"""Valuation = PE vs sensible band (lower=cheaper=higher score, capped)."""


def score_valuation(pe: float | None) -> float:
    if pe is None or pe <= 0:
        return 50.0
    if pe < 10:
        return 90.0
    if pe < 15:
        return 80.0
    if pe < 20:
        return 70.0
    if pe < 30:
        return 55.0
    if pe < 50:
        return 40.0
    return 25.0
