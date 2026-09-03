# Domain Hack Scanner

A small, mobile-friendly Streamlit app for scanning messy expired-domain auction/export files for **single dictionary-word domain hacks**.

Examples:

- `vir.us` → `virus` → **Exact**
- `parasit.es` → `parasites` → **Exact**
- `realm.sh` → `realms` + trailing `h` → **+1**

The reconstructed word must cross the dot. The scanner does **not** report ordinary dictionary SLDs merely because the left side is a word.

## Why this is separate

This repository is intentionally independent from the larger expired-auction scanner. It makes the domain-hack logic easy to test on real Dynadot/Namecheap exports before merging `domain_parser.py`, `lexicon.py`, and `hack_detector.py` into the main pipeline.

## Input handling

Upload `.txt`, `.csv`, `.tsv`, `.log` or `.list` files, or paste raw text directly.

The parser extracts domain-looking tokens from arbitrary surrounding text, for example:

```text
12345 vir.us $12.99 auction
parasit.es,19.50 EUR
https://realm.sh/something
```

becomes:

```text
vir.us
parasit.es
realm.sh
```

Prices, currencies, bid counts, dates, IDs, comments and URL paths are ignored. Email addresses are excluded. Duplicates are removed while preserving first-seen order.

File decoding falls back through UTF-8-SIG, UTF-8, Windows CP1252 and Latin-1.

## Dictionary model

The built-in English-word signal uses `wordfreq` Zipf frequency rather than shipping an enormous word-list file.

Default modes:

- **Common English**: cleaner, higher frequency threshold
- **Broad English**: rarer words, more noise

You can also upload a custom dictionary (including a `words_alpha.txt`-style list). Custom words are treated as authoritative matches even if their `wordfreq` score is low.

This is useful for specialist scientific, technical or domain-investing vocabulary.

## Detection rules

### Exact

```text
SLD + TLD == dictionary word
```

Example:

```text
vir + us = virus
```

### +1 trailing character

```text
(SLD + TLD)[:-1] == dictionary word
```

The candidate must still cross the dot.

Example:

```text
realm + sh = realmsh
realmsh[:-1] = realms
extra = h
```

V1 intentionally scans direct `SLD.TLD` domains only. Multi-label suffixes such as `example.co.uk` are excluded rather than guessed.

## Scoring

Results are ranked 0–100 using deterministic lexical/visual factors:

- exact hack vs +1
- word frequency/familiarity
- word brevity
- split quality
- how many word characters the TLD contributes
- TLD visual compactness

The score is a triage score, not a valuation.

## Local run

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

## Deploy: GitHub → Streamlit Community Cloud

1. Create a **private GitHub repository**.
2. Upload/push this repository as-is.
3. Open Streamlit Community Cloud and create a new app from that repo.
4. Set the app entry point to `app.py`.
5. Deploy.
6. Keep the app private if your expired-auction lists are commercially sensitive.

No database, login, registrar API or persistence layer is required for V1.

## Privacy / limitations

The application code does not intentionally save uploaded files; it processes their contents in the running Streamlit session. Hosting infrastructure still necessarily receives the upload in order to process it.

The scanner does **not** check:

- domain availability
- current registration/ownership
- auction status
- prices
- trademark conflicts
- UDRP risk
- TLD delegation/validity
- commercial value

Those should remain separate downstream screening stages.

## Suggested future integration

Once the detector proves useful on live lists, merge these modules into the existing scanner:

```text
INPUT
├── .COM exact dictionary
├── .COM broad combinations
├── .COM brandables
├── other-TLD exact
└── DOMAIN HACKS
    ├── exact word
    └── word + one trailing character
```
