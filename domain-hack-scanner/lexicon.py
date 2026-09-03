from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

try:
    from wordfreq import zipf_frequency
except ImportError:  # pragma: no cover - handled in UI
    zipf_frequency = None


WORD_RE = re.compile(r"[a-z]+", re.I)


@dataclass(frozen=True)
class WordEvidence:
    accepted: bool
    zipf: float
    source: str


def parse_custom_wordlist(text: str) -> set[str]:
    """Accept one-per-line or loosely separated alphabetic custom words."""
    return {token.lower() for token in WORD_RE.findall(text or "") if len(token) >= 2}


@lru_cache(maxsize=200_000)
def _zipf(word: str) -> float:
    if zipf_frequency is None:
        return 0.0
    return float(zipf_frequency(word, "en"))


def lookup_word(
    word: str,
    *,
    min_zipf: float,
    custom_words: set[str] | None = None,
) -> WordEvidence:
    word = word.lower()
    custom_words = custom_words or set()

    if word in custom_words:
        # Keep the real frequency when available for scoring/display, while the
        # custom dictionary itself is authoritative for acceptance.
        return WordEvidence(True, _zipf(word), "custom")

    if zipf_frequency is None:
        raise RuntimeError(
            "wordfreq is not installed. Install dependencies from requirements.txt."
        )

    frequency = _zipf(word)
    return WordEvidence(frequency >= min_zipf, frequency, "wordfreq")
