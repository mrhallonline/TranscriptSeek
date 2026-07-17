"""Conservative local identifier detection for human-reviewed de-identification."""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict


PATTERNS = {
    "EMAIL": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "PHONE": re.compile(r"(?<!\w)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\w)"),
    "URL": re.compile(r"\bhttps?://[^\s]+", re.IGNORECASE),
    "POSTAL_CODE": re.compile(r"\b\d{5}(?:-\d{4})?\b"),
}


@dataclass(frozen=True)
class DetectedIdentifier:
    entity_type: str
    text: str
    start_char: int
    end_char: int
    confidence: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def detect_identifiers(text: str) -> list[DetectedIdentifier]:
    found = []
    for entity_type, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            found.append(DetectedIdentifier(entity_type, match.group(), match.start(), match.end(), 0.99))
    return sorted(found, key=lambda item: (item.start_char, item.end_char))


def apply_confirmed_redactions(text: str, replacements: list[dict[str, object]]) -> str:
    """Apply reviewed replacements from right to left, preserving source offsets."""
    result = text
    accepted = [item for item in replacements if item.get("status") == "confirmed"]
    for item in sorted(accepted, key=lambda value: int(value["start_char"]), reverse=True):
        start, end = int(item["start_char"]), int(item["end_char"])
        if not (0 <= start <= end <= len(result)):
            raise ValueError("Redaction offsets are outside the source segment")
        result = result[:start] + str(item["replacement"]) + result[end:]
    return result

