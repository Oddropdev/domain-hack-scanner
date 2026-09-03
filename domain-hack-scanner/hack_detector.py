from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable, Iterable

from lexicon import WordEvidence


@dataclass(frozen=True)
class HackResult:
    domain: str
    word: str
    hack_type: str
    extra: str
    score: int
    zipf: float
    split_ratio: float
    tld_chars_in_word: int
    sld: str
    tld: str
    word_source: str

    def to_dict(self) -> dict:
        return asdict(self)


def _brevity_score(word_len: int) -> float:
    if word_len <= 5:
        return 15.0
    if word_len == 6:
        return 14.0
    if word_len == 7:
        return 13.0
    if word_len == 8:
        return 12.0
    if word_len == 9:
        return 11.0
    if word_len == 10:
        return 10.0
    if word_len <= 12:
        return 8.0
    if word_len <= 15:
        return 6.0
    return 3.0


def _frequency_score(zipf: float) -> float:
    # 1.5 ~= rare but attested, 6.5 ~= extremely common. Clamp to 0..25.
    return max(0.0, min(25.0, (zipf - 1.5) / 5.0 * 25.0))


def _split_score(ratio: float, tld_chars_in_word: int) -> float:
    """Favor visible, meaningful cross-dot splits rather than 1-char tails."""
    if tld_chars_in_word <= 0:
        return 0.0

    if 0.15 <= ratio <= 0.45:
        base = 15.0
    elif 0.10 <= ratio < 0.15 or 0.45 < ratio <= 0.55:
        base = 12.0
    elif 0.05 <= ratio < 0.10 or 0.55 < ratio <= 0.70:
        base = 8.0
    else:
        base = 5.0

    # One-character contribution is valid (e.g. realm.sh -> realms + h), but
    # visually weaker than vir.us / parasit.es.
    if tld_chars_in_word == 1:
        base -= 3.0
    return max(0.0, base)


def _tld_visual_score(tld: str, tld_chars_in_word: int, extra: str) -> float:
    score = 0.0
    if 2 <= len(tld) <= 4:
        score += 4.0
    elif len(tld) <= 8:
        score += 2.5
    else:
        score += 1.0

    if 2 <= tld_chars_in_word <= 4:
        score += 5.0
    elif tld_chars_in_word == 1:
        score += 2.5
    elif tld_chars_in_word > 4:
        score += 3.0

    if extra:
        score -= 1.5
    return max(0.0, min(10.0, score))


def score_hack(
    *,
    word: str,
    hack_type: str,
    zipf: float,
    sld: str,
    tld: str,
    extra: str,
) -> tuple[int, float, int]:
    tld_chars_in_word = len(word) - len(sld)
    split_ratio = tld_chars_in_word / max(len(word), 1)

    exactness = 35.0 if hack_type == "EXACT" else 20.0
    total = (
        exactness
        + _frequency_score(zipf)
        + _brevity_score(len(word))
        + _split_score(split_ratio, tld_chars_in_word)
        + _tld_visual_score(tld, tld_chars_in_word, extra)
    )
    return int(round(max(0.0, min(100.0, total)))), split_ratio, tld_chars_in_word


def detect_domain_hack(
    domain: str,
    *,
    lookup: Callable[[str], WordEvidence],
    include_plus_one: bool = True,
    min_word_length: int = 3,
) -> HackResult | None:
    """
    Detect dictionary words that cross the SLD/TLD dot.

    V1 intentionally handles one direct dot only:
      vir.us       -> virus      (EXACT)
      parasit.es   -> parasites  (EXACT)
      realm.sh     -> realms + h (PLUS_1)

    Multi-label suffixes such as example.co.uk are excluded rather than guessed.
    """
    domain = domain.lower().strip().rstrip(".")
    if domain.count(".") != 1:
        return None

    sld, tld = domain.split(".", 1)
    if not sld.isalpha() or not tld.isalpha():
        return None

    joined = sld + tld

    # Exact hack: the whole SLD + TLD is one word, and at least one TLD letter
    # must actually participate in the word.
    if len(joined) >= min_word_length:
        evidence = lookup(joined)
        if evidence.accepted and len(joined) > len(sld):
            score, split_ratio, tld_chars = score_hack(
                word=joined,
                hack_type="EXACT",
                zipf=evidence.zipf,
                sld=sld,
                tld=tld,
                extra="",
            )
            return HackResult(
                domain=domain,
                word=joined,
                hack_type="EXACT",
                extra="",
                score=score,
                zipf=evidence.zipf,
                split_ratio=split_ratio,
                tld_chars_in_word=tld_chars,
                sld=sld,
                tld=tld,
                word_source=evidence.source,
            )

    # Word + one trailing character. The word still has to cross the dot, which
    # prevents ordinary dictionary SLDs from being misclassified.
    if include_plus_one and len(tld) >= 2 and len(joined) - 1 >= min_word_length:
        candidate = joined[:-1]
        extra = joined[-1]
        if len(candidate) > len(sld):
            evidence = lookup(candidate)
            if evidence.accepted:
                score, split_ratio, tld_chars = score_hack(
                    word=candidate,
                    hack_type="PLUS_1",
                    zipf=evidence.zipf,
                    sld=sld,
                    tld=tld,
                    extra=extra,
                )
                return HackResult(
                    domain=domain,
                    word=candidate,
                    hack_type="PLUS_1",
                    extra=extra,
                    score=score,
                    zipf=evidence.zipf,
                    split_ratio=split_ratio,
                    tld_chars_in_word=tld_chars,
                    sld=sld,
                    tld=tld,
                    word_source=evidence.source,
                )

    return None


def scan_domains(
    domains: Iterable[str],
    *,
    lookup: Callable[[str], WordEvidence],
    include_plus_one: bool = True,
    min_word_length: int = 3,
) -> list[HackResult]:
    results: list[HackResult] = []
    for domain in domains:
        hit = detect_domain_hack(
            domain,
            lookup=lookup,
            include_plus_one=include_plus_one,
            min_word_length=min_word_length,
        )
        if hit is not None:
            results.append(hit)

    results.sort(key=lambda r: (-r.score, -r.zipf, len(r.word), r.domain))
    return results
