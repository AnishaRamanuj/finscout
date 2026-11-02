"""Turn a 0-100 composite score into a plain-English verdict a retail investor can act on."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Verdict:
    label: str
    color: str          # hex for background badge
    text_color: str     # hex for badge text
    plain: str          # one-sentence beginner-friendly description


def verdict_for(composite: float) -> Verdict:
    """Map a composite score to a verdict badge + plain-English explainer."""
    s = composite or 0
    if s >= 70:
        return Verdict(
            label="Strong Pick",
            color="#16a34a",
            text_color="#ffffff",
            plain="Strong signals across growth, momentum and quality — top of our list this week.",
        )
    if s >= 58:
        return Verdict(
            label="Pick",
            color="#2563eb",
            text_color="#ffffff",
            plain="Solid fundamentals and favourable momentum — worth a close look.",
        )
    if s >= 48:
        return Verdict(
            label="Hold",
            color="#64748b",
            text_color="#ffffff",
            plain="Mixed signals. Fine if you already own it, nothing special to add new money to.",
        )
    if s >= 35:
        return Verdict(
            label="Watch",
            color="#f59e0b",
            text_color="#111827",
            plain="Weakness in several factors. Keep on radar, but don't add here.",
        )
    return Verdict(
        label="Avoid",
        color="#dc2626",
        text_color="#ffffff",
        plain="Multiple warning signs. Not a buy right now in our model.",
    )
