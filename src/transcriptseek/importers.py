"""Transcript parsing with normalized millisecond timestamps."""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ImportedSegment:
    start_ms: int
    end_ms: int
    text: str
    speaker: str | None = None
    confidence: float | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


_TIMESTAMP_RE = re.compile(
    r"(?P<h>\d{1,2}):(?P<m>\d{2}):(?P<s>\d{2})[,.](?P<ms>\d{3})"
)


def parse_timestamp(value: str | int | float) -> int:
    if isinstance(value, (int, float)):
        if value < 0:
            raise ValueError("Timestamps cannot be negative")
        return round(float(value) * 1000)
    value = value.strip()
    match = _TIMESTAMP_RE.fullmatch(value)
    if match:
        return (
            int(match["h"]) * 3_600_000
            + int(match["m"]) * 60_000
            + int(match["s"]) * 1000
            + int(match["ms"])
        )
    try:
        return parse_timestamp(float(value))
    except ValueError as exc:
        raise ValueError(f"Unsupported timestamp: {value!r}") from exc


def parse_srt(text: str) -> list[ImportedSegment]:
    blocks = re.split(r"\r?\n\s*\r?\n", text.strip())
    result: list[ImportedSegment] = []
    for block in blocks:
        lines = [line.strip("\ufeff") for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        timing_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue
        start_raw, end_raw = [part.strip().split()[0] for part in lines[timing_index].split("-->")]
        body = "\n".join(lines[timing_index + 1 :]).strip()
        if body:
            result.append(ImportedSegment(parse_timestamp(start_raw), parse_timestamp(end_raw), body))
    return result


def parse_vtt(text: str) -> list[ImportedSegment]:
    text = re.sub(r"^\ufeff?WEBVTT[^\n]*\r?\n", "", text, count=1)
    return parse_srt(text.replace(".", ","))


def parse_json(text: str) -> list[ImportedSegment]:
    payload = json.loads(text)
    items = payload.get("segments", payload) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ValueError("JSON transcript must be a list or contain a segments list")
    result = []
    for item in items:
        result.append(
            ImportedSegment(
                start_ms=parse_timestamp(item.get("start_ms", item.get("start", 0)) / 1000)
                if "start_ms" in item
                else parse_timestamp(item.get("start", 0)),
                end_ms=parse_timestamp(item.get("end_ms", item.get("end", 0)) / 1000)
                if "end_ms" in item
                else parse_timestamp(item.get("end", 0)),
                text=str(item["text"]).strip(),
                speaker=item.get("speaker"),
                confidence=float(item["confidence"]) if item.get("confidence") is not None else None,
            )
        )
    return result


def parse_csv_transcript(
    text: str,
    *,
    start_column: str = "start",
    end_column: str = "end",
    text_column: str = "text",
    speaker_column: str = "speaker",
) -> list[ImportedSegment]:
    rows = csv.DictReader(io.StringIO(text))
    required = {start_column, end_column, text_column}
    if not rows.fieldnames or not required.issubset(rows.fieldnames):
        raise ValueError(f"CSV transcript requires columns: {', '.join(sorted(required))}")
    return [
        ImportedSegment(
            parse_timestamp(row[start_column]),
            parse_timestamp(row[end_column]),
            row[text_column].strip(),
            row.get(speaker_column) or None,
        )
        for row in rows
        if row.get(text_column, "").strip()
    ]


def parse_untimed(text: str, *, seconds_per_paragraph: int = 30) -> list[ImportedSegment]:
    paragraphs = [part.strip() for part in re.split(r"\r?\n\s*\r?\n", text) if part.strip()]
    duration = seconds_per_paragraph * 1000
    return [ImportedSegment(i * duration, (i + 1) * duration, part) for i, part in enumerate(paragraphs)]


def load_transcript(path: Path, *, format_name: str | None = None) -> list[ImportedSegment]:
    format_name = (format_name or path.suffix.removeprefix(".")).lower()
    text = path.read_text(encoding="utf-8-sig")
    parsers = {
        "srt": parse_srt,
        "vtt": parse_vtt,
        "json": parse_json,
        "csv": parse_csv_transcript,
        "txt": parse_untimed,
    }
    try:
        segments = parsers[format_name](text)
    except KeyError as exc:
        raise ValueError(f"Unsupported transcript format: {format_name}") from exc
    validate_segments(segments)
    return segments


def validate_segments(segments: Iterable[ImportedSegment]) -> None:
    previous_start = -1
    for segment in segments:
        if not segment.text:
            raise ValueError("Transcript segments cannot be empty")
        if segment.start_ms < previous_start:
            raise ValueError("Transcript segments must be ordered by start time")
        if segment.end_ms < segment.start_ms:
            raise ValueError("Segment end time precedes start time")
        previous_start = segment.start_ms

