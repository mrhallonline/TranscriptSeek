"""Deterministic, provenance-friendly local transcript analyzers."""

from __future__ import annotations

import hashlib
import json
import math
import re
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable


TOKEN_RE = re.compile(r"[\w'-]+", re.UNICODE)
DEFAULT_STOPWORDS = frozenset(
    "a an and are as at be been but by for from had has have he her hers him his i in is it "
    "its me my of on or our she that the their them they this to was we were will with you your".split()
)


@dataclass(frozen=True)
class AnalyzerContext:
    project_id: str
    transcript_hash: str
    segments: list[dict[str, Any]]


class Analyzer(ABC):
    analyzer_id: str
    version = "1.0.0"
    deterministic = True
    limitations: str

    @abstractmethod
    def run(self, context: AnalyzerContext, parameters: dict[str, Any]) -> dict[str, Any]: ...

    def manifest(self) -> dict[str, Any]:
        return {
            "id": self.analyzer_id,
            "version": self.version,
            "deterministic": self.deterministic,
            "limitations": self.limitations,
        }


def tokens(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_RE.findall(text)]


class FrequencyAnalyzer(Analyzer):
    analyzer_id = "frequency"
    limitations = "Token counts do not capture context, irony, negation, or meaning."

    def run(self, context: AnalyzerContext, parameters: dict[str, Any]) -> dict[str, Any]:
        minimum = int(parameters.get("minimum_count", 1))
        limit = min(int(parameters.get("limit", 50)), 500)
        include_stopwords = bool(parameters.get("include_stopwords", False))
        ngram_size = min(max(int(parameters.get("ngram_size", 1)), 1), 4)
        all_tokens: list[str] = []
        for segment in context.segments:
            current = tokens(segment["text"])
            if not include_stopwords:
                current = [word for word in current if word not in DEFAULT_STOPWORDS]
            all_tokens.extend(" ".join(current[i : i + ngram_size]) for i in range(len(current) - ngram_size + 1))
        counts = Counter(all_tokens)
        return {
            "items": [
                {"term": term, "count": count}
                for term, count in counts.most_common()
                if count >= minimum
            ][:limit],
            "token_count": len(all_tokens),
        }


class CollocationAnalyzer(Analyzer):
    analyzer_id = "collocation"
    limitations = "Association scores indicate co-occurrence, not causal or thematic importance."

    def run(self, context: AnalyzerContext, parameters: dict[str, Any]) -> dict[str, Any]:
        limit = min(int(parameters.get("limit", 30)), 200)
        words = [
            word
            for segment in context.segments
            for word in tokens(segment["text"])
            if word not in DEFAULT_STOPWORDS
        ]
        singles = Counter(words)
        pairs = Counter(zip(words, words[1:]))
        total = max(len(words), 1)
        scored = []
        for (left, right), count in pairs.items():
            if count < 2:
                continue
            pmi = math.log2((count * total) / (singles[left] * singles[right]))
            scored.append({"terms": [left, right], "count": count, "pmi": round(pmi, 3)})
        return {"items": sorted(scored, key=lambda item: (item["pmi"], item["count"]), reverse=True)[:limit]}


class KeyphraseAnalyzer(Analyzer):
    analyzer_id = "keyphrase"
    limitations = "Keyphrases are frequency-ranked surface forms and require researcher interpretation."

    def run(self, context: AnalyzerContext, parameters: dict[str, Any]) -> dict[str, Any]:
        frequency = FrequencyAnalyzer()
        params = {"ngram_size": 2, "minimum_count": 1, "limit": parameters.get("limit", 30)}
        return frequency.run(context, params)


class ConcordanceAnalyzer(Analyzer):
    analyzer_id = "concordance"
    limitations = "Concordance windows show nearby wording, not the full interactional context."

    def run(self, context: AnalyzerContext, parameters: dict[str, Any]) -> dict[str, Any]:
        term = str(parameters.get("term", "trust")).strip()
        if not term:
            raise ValueError("Concordance analysis requires a term")
        width = min(max(int(parameters.get("width", 55)), 15), 250)
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        items = []
        for segment in context.segments:
            for match in pattern.finditer(segment["text"]):
                items.append({
                    "segment_id": segment["id"],
                    "start_ms": segment["start_ms"],
                    "speaker": segment.get("speaker"),
                    "left": segment["text"][max(0, match.start() - width) : match.start()],
                    "term": match.group(),
                    "right": segment["text"][match.end() : match.end() + width],
                })
        return {"term": term, "items": items, "count": len(items)}


class EntityAnalyzer(Analyzer):
    analyzer_id = "entity"
    limitations = "Rule-based entities are incomplete and may mistake ordinary capitalized phrases for identifiers."
    _capitalized = re.compile(r"\b(?:[A-Z][a-z]{2,})(?:\s+[A-Z][a-z]{2,}){0,2}\b")

    def run(self, context: AnalyzerContext, parameters: dict[str, Any]) -> dict[str, Any]:
        from .redaction import detect_identifiers

        items = []
        for segment in context.segments:
            for entity in detect_identifiers(segment["text"]):
                items.append(entity.to_dict() | {"segment_id": segment["id"], "start_ms": segment["start_ms"]})
            for match in self._capitalized.finditer(segment["text"]):
                if match.start() == 0 and " " not in match.group():
                    continue
                items.append({
                    "entity_type": "POSSIBLE_NAME_OR_PLACE",
                    "text": match.group(),
                    "start_char": match.start(),
                    "end_char": match.end(),
                    "confidence": 0.45,
                    "segment_id": segment["id"],
                    "start_ms": segment["start_ms"],
                })
        return {"items": items, "requires_human_review": True}


class SentimentAnalyzer(Analyzer):
    analyzer_id = "sentiment"
    limitations = "Lexicon sentiment misses irony, negation, culture, and domain meaning; never treat it as participant affect."
    positive = frozenset("agree benefit calm care confident fair good hopeful improve listen safe support trust value welcome".split())
    negative = frozenset("angry anxious bad barrier distrust exclude fear harm ignored risk unsafe worry".split())

    def run(self, context: AnalyzerContext, parameters: dict[str, Any]) -> dict[str, Any]:
        items = []
        for segment in context.segments:
            words = tokens(segment["text"])
            positive = sum(word in self.positive for word in words)
            negative = sum(word in self.negative for word in words)
            score = (positive - negative) / max(positive + negative, 1)
            items.append({
                "segment_id": segment["id"], "start_ms": segment["start_ms"],
                "score": round(score, 3), "positive_terms": positive, "negative_terms": negative,
            })
        return {"items": items, "interpretation": "exploratory lexical polarity, not emotion"}


class TopicExplorerAnalyzer(Analyzer):
    analyzer_id = "topic_explorer"
    limitations = "Term clusters are navigation aids, not discovered themes or validated qualitative findings."

    def run(self, context: AnalyzerContext, parameters: dict[str, Any]) -> dict[str, Any]:
        limit = min(int(parameters.get("limit", 8)), 30)
        document_frequency: Counter[str] = Counter()
        total_frequency: Counter[str] = Counter()
        for segment in context.segments:
            words = [word for word in tokens(segment["text"]) if word not in DEFAULT_STOPWORDS and len(word) > 2]
            document_frequency.update(set(words))
            total_frequency.update(words)
        ranked = sorted(
            total_frequency,
            key=lambda word: total_frequency[word] * math.log(1 + len(context.segments) / max(document_frequency[word], 1)),
            reverse=True,
        )[:limit]
        return {
            "items": [
                {
                    "term": term,
                    "count": total_frequency[term],
                    "segment_count": document_frequency[term],
                }
                for term in ranked
            ],
            "requires_researcher_naming": True,
        }


ANALYZERS: dict[str, Analyzer] = {
    analyzer.analyzer_id: analyzer
    for analyzer in (
        FrequencyAnalyzer(), CollocationAnalyzer(), KeyphraseAnalyzer(), ConcordanceAnalyzer(),
        EntityAnalyzer(), SentimentAnalyzer(), TopicExplorerAnalyzer(),
    )
}


def analysis_input_hash(segments: Iterable[dict[str, Any]], parameters: dict[str, Any]) -> str:
    payload = json.dumps(
        {"segments": list(segments), "parameters": parameters},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
