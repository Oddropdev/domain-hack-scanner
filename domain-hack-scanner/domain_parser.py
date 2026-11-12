from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


# Deliberately extracts domain-looking tokens from arbitrary registrar/export text.
# Candidate extraction includes invalid label characters so they can be
# rejected in full; numeric prices and dates are rejected by _valid_domain.
DOMAIN_RE = re.compile(
    r"(?i)(?<![@\w.+!#$%&'*=?^`{|}~-])"
    r"(?:https?://)?(?:www\.)?"
    r"((?:[a-z0-9_+-]{1,63}\.)+[a-z0-9_+-]{2,63})"
    r"(?::\d{1,5})?"
    r"(?=$|[^\w.+-])"
)

# Match broad domain-like candidates, then reject complete candidates that
# contain any non-letter label. Never salvage a substring of an invalid name.
LABEL_RE = re.compile(r"^[a-z]{1,63}$", re.ASCII | re.I)
TLD_RE = re.compile(r"^[a-z]{2,63}$", re.ASCII | re.I)

@dataclass(frozen=True)
class ParseStats:
    extracted: int
    unique: int
    duplicates_removed: int
    encoding: str | None = None


def decode_bytes(raw: bytes) -> tuple[str, str]:
    """Decode registrar/export files without assuming UTF-8 only."""
    if not raw:
        return "", "empty"

    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue

    # latin-1 should always decode, but keep a safe final fallback.
    return raw.decode("utf-8", errors="replace"), "utf-8-replace"


def _valid_domain(domain: str) -> bool:
    if len(domain) > 253 or domain.startswith(".") or domain.endswith("."):
        return False

    labels = domain.split(".")
    if len(labels) < 2:
        return False

    if not TLD_RE.fullmatch(labels[-1]):
        return False

    return all(LABEL_RE.fullmatch(label) for label in labels[:-1])


def extract_domains(text: str) -> tuple[list[str], ParseStats]:
    """
    Extract unique domains from messy text while preserving first-seen order.

    Intentionally ignores surrounding prices, auction IDs, currencies, labels,
    comments and URL paths. Email domains are excluded by the regex lookbehind.
    """
    normalized = text or ""
    raw_matches = [m.group(1).lower().rstrip(".") for m in DOMAIN_RE.finditer(normalized)]
    valid_matches = [domain for domain in raw_matches if _valid_domain(domain)]

    unique_domains = list(dict.fromkeys(valid_matches))
    stats = ParseStats(
        extracted=len(valid_matches),
        unique=len(unique_domains),
        duplicates_removed=len(valid_matches) - len(unique_domains),
    )
    return unique_domains, stats


def extract_domains_from_bytes(raw: bytes) -> tuple[list[str], ParseStats]:
    text, encoding = decode_bytes(raw)
    domains, stats = extract_domains(text)
    return domains, ParseStats(
        extracted=stats.extracted,
        unique=stats.unique,
        duplicates_removed=stats.duplicates_removed,
        encoding=encoding,
    )


def merge_domain_lists(domain_lists: Iterable[Iterable[str]]) -> list[str]:
    """Merge multiple uploads/pastes and deduplicate while preserving order."""
    seen: set[str] = set()
    merged: list[str] = []
    for domains in domain_lists:
        for domain in domains:
            if domain not in seen:
                seen.add(domain)
                merged.append(domain)
    return merged
