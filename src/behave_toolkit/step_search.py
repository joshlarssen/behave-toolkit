"""Rank Behave step definitions from natural-language queries."""
# pylint: disable=too-many-instance-attributes,duplicate-code

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass, field
import json
import math
from pathlib import Path
import re
import unicodedata
from typing import TYPE_CHECKING, Sequence

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
CAMEL_BOUNDARY_PATTERN = re.compile(r"([a-z0-9])([A-Z])")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "for",
    "from",
    "i",
    "in",
    "into",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}
FIELD_WEIGHTS = {
    "title": 5.0,
    "pattern": 4.5,
    "summary": 4.0,
    "docstring": 2.5,
    "parameters": 2.0,
    "examples": 2.5,
    "function": 1.5,
    "source": 1.0,
    "keyword": 1.0,
}
PARTIAL_MATCH_FACTOR = 0.55

if TYPE_CHECKING:
    from .step_docs import StepDocumentation


@dataclass(frozen=True, slots=True)
class StepSearchResult:
    title: str
    score: float
    step_type: str
    matcher: str
    pattern: str
    summary: str | None
    signature: str | None
    source: str
    page_path: str
    html_path: str
    examples: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _SearchIndexEntry:
    title: str
    step_type: str
    matcher: str
    pattern: str
    summary: str | None
    signature: str | None
    source: str
    page_path: str
    html_path: str
    examples: tuple[str, ...]
    token_weights: dict[str, float] = field(default_factory=dict)
    search_text: str = ""
    title_text: str = ""
    summary_text: str = ""
    term_count: int = 0


@dataclass(frozen=True, slots=True)
class _RawSearchEntry:
    title: str
    step_type: str
    matcher: str
    pattern: str
    summary: str | None
    signature: str | None
    source: str
    page_path: str
    html_path: str
    examples: tuple[str, ...]
    token_counts: dict[str, float] = field(default_factory=dict)
    search_text: str = ""
    title_text: str = ""
    summary_text: str = ""


def search_steps(
    features_dir: str | Path,
    query: str,
    *,
    limit: int = 10,
    max_examples_per_step: int = 3,
) -> list[StepSearchResult]:
    """Search the most relevant Behave steps for a query."""

    from .step_docs import _collect_catalog  # pylint: disable=import-outside-toplevel

    if limit < 1:
        raise ValueError("'limit' must be at least 1.")

    catalog = _collect_catalog(
        Path(features_dir).expanduser().resolve(),
        max_examples_per_step=max_examples_per_step,
    )
    index_entries = build_search_index_entries(catalog.steps)
    return search_index_entries(index_entries, query, limit=limit)


def build_search_index_entries(
    step_docs: Sequence[StepDocumentation],
) -> list[_SearchIndexEntry]:
    """Build a weighted search index from collected step documentation."""

    raw_entries = [_build_raw_search_entry(step_doc) for step_doc in step_docs]
    if not raw_entries:
        return []

    document_frequencies: Counter[str] = Counter()
    for raw_entry in raw_entries:
        document_frequencies.update(raw_entry.token_counts.keys())

    document_count = len(raw_entries)
    entries: list[_SearchIndexEntry] = []
    for raw_entry in raw_entries:
        token_weights = {
            token: round(
                weight
                * _inverse_document_frequency(
                    document_count,
                    document_frequencies[token],
                ),
                6,
            )
            for token, weight in raw_entry.token_counts.items()
        }
        entries.append(
            _SearchIndexEntry(
                title=raw_entry.title,
                step_type=raw_entry.step_type,
                matcher=raw_entry.matcher,
                pattern=raw_entry.pattern,
                summary=raw_entry.summary,
                signature=raw_entry.signature,
                source=raw_entry.source,
                page_path=raw_entry.page_path,
                html_path=raw_entry.html_path,
                examples=raw_entry.examples,
                token_weights=token_weights,
                search_text=raw_entry.search_text,
                title_text=raw_entry.title_text,
                summary_text=raw_entry.summary_text,
                term_count=len(token_weights),
            )
        )
    return entries


def search_index_entries(
    entries: Sequence[_SearchIndexEntry],
    query: str,
    *,
    limit: int = 10,
) -> list[StepSearchResult]:
    """Search a prebuilt search index."""

    if limit < 1:
        raise ValueError("'limit' must be at least 1.")

    normalized_query = _normalize_text(query)
    query_terms = _unique_tokens(_tokenize(query))
    if not normalized_query or not query_terms:
        return []

    ranked_results: list[StepSearchResult] = []
    for entry in entries:
        score = _score_search_entry(entry, normalized_query, query_terms)
        if score <= 0:
            continue

        ranked_results.append(
            StepSearchResult(
                title=entry.title,
                score=round(score, 6),
                step_type=entry.step_type.capitalize() if entry.step_type != "step" else "Generic",
                matcher=entry.matcher,
                pattern=entry.pattern,
                summary=entry.summary,
                signature=entry.signature,
                source=entry.source,
                page_path=entry.page_path,
                html_path=entry.html_path,
                examples=entry.examples,
            )
        )

    ranked_results.sort(key=lambda value: (-value.score, value.title.lower()))
    return ranked_results[:limit]


def render_search_index_json(step_docs: Sequence[StepDocumentation]) -> str:
    """Serialize the step search index used by the generated HTML docs."""

    payload = {
        "version": 1,
        "entries": [asdict(entry) for entry in build_search_index_entries(step_docs)],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _build_raw_search_entry(step_doc: StepDocumentation) -> _RawSearchEntry:
    summary = _docstring_summary(step_doc.docstring)
    examples = tuple(example.text for example in step_doc.examples)
    source = f"{step_doc.source_path}:{step_doc.source_line}"
    page_path = f"steps/{step_doc.slug}.md"
    html_path = f"steps/{step_doc.slug}.html"

    token_counts: dict[str, float] = {}
    search_segments: list[str] = []

    _add_weighted_tokens(token_counts, step_doc.title, FIELD_WEIGHTS["title"], search_segments)
    _add_weighted_tokens(token_counts, step_doc.pattern, FIELD_WEIGHTS["pattern"], search_segments)
    _add_weighted_tokens(
        token_counts,
        step_doc.step_type,
        FIELD_WEIGHTS["keyword"],
        search_segments,
    )
    _add_weighted_tokens(
        token_counts,
        step_doc.function_name,
        FIELD_WEIGHTS["function"],
        search_segments,
    )
    _add_weighted_tokens(
        token_counts,
        source,
        FIELD_WEIGHTS["source"],
        search_segments,
    )

    if summary:
        _add_weighted_tokens(token_counts, summary, FIELD_WEIGHTS["summary"], search_segments)
    if step_doc.docstring:
        _add_weighted_tokens(
            token_counts,
            step_doc.docstring,
            FIELD_WEIGHTS["docstring"],
            search_segments,
        )

    for parameter in step_doc.parameters:
        parameter_parts = [parameter.name]
        if parameter.pattern_syntax:
            parameter_parts.append(parameter.pattern_syntax)
        if parameter.base_type_name:
            parameter_parts.append(parameter.base_type_name)
        if parameter.python_type:
            parameter_parts.append(parameter.python_type)
        if parameter.runtime_type:
            parameter_parts.append(parameter.runtime_type)
        _add_weighted_tokens(
            token_counts,
            " ".join(parameter_parts),
            FIELD_WEIGHTS["parameters"],
            search_segments,
        )

    for example_text in examples:
        _add_weighted_tokens(
            token_counts,
            example_text,
            FIELD_WEIGHTS["examples"],
            search_segments,
        )

    title_text = _normalize_text(step_doc.title)
    summary_text = _normalize_text(summary or "")
    search_text = _normalize_text(" ".join(search_segments))
    return _RawSearchEntry(
        title=step_doc.title,
        step_type=step_doc.step_type,
        matcher=step_doc.matcher,
        pattern=step_doc.pattern,
        summary=summary,
        signature=step_doc.signature,
        source=source,
        page_path=page_path,
        html_path=html_path,
        examples=examples,
        token_counts=token_counts,
        search_text=search_text,
        title_text=title_text,
        summary_text=summary_text,
    )


def _add_weighted_tokens(
    token_counts: dict[str, float],
    text: str,
    weight: float,
    search_segments: list[str],
) -> None:
    search_segments.append(text)
    for token in _tokenize(text):
        token_counts[token] = token_counts.get(token, 0.0) + weight


def _score_search_entry(
    entry: _SearchIndexEntry,
    normalized_query: str,
    query_terms: Sequence[str],
) -> float:
    score = 0.0
    matched_terms = 0.0
    exact_matches = 0

    for term in query_terms:
        term_weight = entry.token_weights.get(term)
        if term_weight is not None:
            score += term_weight
            matched_terms += 1.0
            exact_matches += 1
            continue

        partial_weight = _best_partial_term_weight(entry, term)
        if partial_weight > 0:
            score += partial_weight * PARTIAL_MATCH_FACTOR
            matched_terms += PARTIAL_MATCH_FACTOR

    if normalized_query in entry.title_text:
        score += 10.0
    elif normalized_query in entry.summary_text:
        score += 7.0
    elif normalized_query in entry.search_text:
        score += 5.0

    if exact_matches == len(query_terms):
        score += 4.0

    if query_terms:
        score += (matched_terms / len(query_terms)) * 6.0

    if matched_terms == 0 and normalized_query not in entry.search_text:
        return 0.0

    return score / (1.0 + (entry.term_count * 0.01))


def _best_partial_term_weight(entry: _SearchIndexEntry, term: str) -> float:
    if len(term) < 4:
        return 0.0

    best_weight = 0.0
    for candidate, candidate_weight in entry.token_weights.items():
        if candidate.startswith(term) or term.startswith(candidate) or term in candidate:
            best_weight = max(best_weight, candidate_weight)
    return best_weight


def _inverse_document_frequency(document_count: int, document_frequency: int) -> float:
    return 1.0 + math.log((1.0 + document_count) / (1.0 + document_frequency))


def _docstring_summary(docstring: str | None) -> str | None:
    if not docstring:
        return None

    first_paragraph = docstring.strip().split("\n\n", maxsplit=1)[0]
    cleaned = " ".join(line.strip() for line in first_paragraph.splitlines() if line.strip())
    return cleaned or None


def _normalize_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", CAMEL_BOUNDARY_PATTERN.sub(r"\1 \2", text))
    without_marks = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    collapsed = " ".join(without_marks.casefold().split())
    return collapsed


def _tokenize(text: str) -> list[str]:
    normalized = _normalize_text(text)
    return [
        token
        for token in TOKEN_PATTERN.findall(normalized)
        if token not in STOP_WORDS and len(token) > 1
    ]


def _unique_tokens(tokens: Sequence[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        unique.append(token)
    return unique


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for step search."""

    parser = argparse.ArgumentParser(
        prog="behave-toolkit-search",
        description="Search Behave steps by title, docstring, parameters, and examples.",
    )
    parser.add_argument("query", help="Natural-language query used to rank steps.")
    parser.add_argument(
        "--features-dir",
        default="features",
        help="Path to the Behave features directory.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of results to display.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit results as JSON instead of a human-readable list.",
    )
    arguments = parser.parse_args(argv)

    results = search_steps(
        arguments.features_dir,
        arguments.query,
        limit=arguments.limit,
    )
    if arguments.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
        return 0

    if not results:
        print("No matching steps found.")
        return 0

    for index, result in enumerate(results, start=1):
        print(f"{index}. {result.title}  [score={result.score:.2f}]")
        print(f"   {result.step_type} | {result.matcher} | {result.source}")
        if result.summary:
            print(f"   {result.summary}")
        print(f"   Pattern: {result.pattern}")
        if result.signature:
            print(f"   Signature: {result.signature}")
        print(f"   Page: {result.page_path}")
        if result.examples:
            for example_text in result.examples[:2]:
                print(f"   Example: {example_text}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
