"""Synthetic roster for Taller Aurora. Names are fictional on purpose."""

from __future__ import annotations

from typing import Final

INTERVIEWERS: Final[dict[str, dict[str, str]]] = {
    "iv-ana": {
        "name": "Ana Luz",
        "email": "ana.luz@taller-aurora.example",
        "timezone": "America/Argentina/Buenos_Aires",
    },
    "iv-bruno": {
        "name": "Bruno Paz",
        "email": "bruno.paz@taller-aurora.example",
        "timezone": "America/Argentina/Buenos_Aires",
    },
    "iv-camila": {
        "name": "Camila Norte",
        "email": "camila.norte@taller-aurora.example",
        "timezone": "UTC",
    },
    "iv-elena": {
        "name": "Elena Sur",
        "email": "elena.sur@taller-aurora.example",
        "timezone": "UTC",
    },
}

CANDIDATES: Final[dict[str, dict[str, str]]] = {
    "cand-uno": {
        "name": "Candidata Uno",
        "email": "candidata.uno@mail.example",
        "timezone": "America/Argentina/Buenos_Aires",
    },
    "cand-dos": {
        "name": "Candidato Dos",
        "email": "candidato.dos@mail.example",
        "timezone": "UTC",
    },
    "cand-tres": {
        "name": "Candidata Tres",
        "email": "candidata.tres@mail.example",
        "timezone": "America/New_York",
    },
}


def other_markers(candidate_id: str) -> tuple[str, ...]:
    """Folded names and mailboxes of every candidate except the session one."""
    markers: list[str] = []
    for key, row in CANDIDATES.items():
        if key == candidate_id:
            continue
        markers.append(row["name"])
        markers.append(row["email"])
        markers.append(key)
    return tuple(markers)
