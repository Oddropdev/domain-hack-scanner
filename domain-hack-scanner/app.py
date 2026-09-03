from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import streamlit as st

from domain_parser import extract_domains, extract_domains_from_bytes, merge_domain_lists
from hack_detector import scan_domains
from lexicon import lookup_word, parse_custom_wordlist


st.set_page_config(
    page_title="Domain Hack Scanner",
    page_icon="⌁",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
.block-container {max-width: 880px; padding-top: 1.2rem; padding-bottom: 3rem;}
[data-testid="stFileUploader"] section {padding: 1.15rem 0.8rem;}
.small-note {opacity: 0.72; font-size: 0.86rem;}
.result-card {
    border: 1px solid rgba(140, 150, 170, 0.22);
    border-radius: 12px;
    padding: 0.75rem 0.9rem;
    margin: 0.4rem 0;
}
.result-domain {font-size: 1.08rem; font-weight: 700; letter-spacing: 0.01em;}
.result-meta {opacity: 0.72; font-size: 0.84rem; margin-top: 0.15rem;}
@media (max-width: 640px) {
    .block-container {padding-left: 0.85rem; padding-right: 0.85rem; padding-top: 0.7rem;}
    h1 {font-size: 1.75rem !important;}
}
</style>
""",
    unsafe_allow_html=True,
)

st.title("Domain Hack Scanner")
st.caption(
    "Find dictionary-word domain hacks from messy expired-auction/export files. "
    "Prices, IDs, notes and other surrounding text are ignored."
)

with st.expander("What counts as a hit?", expanded=False):
    st.markdown(
        """
- `vir.us` → **virus** → Exact
- `parasit.es` → **parasites** → Exact
- `realm.sh` → **realms** + trailing `h` → +1

The dictionary word **must cross the dot**. Ordinary dictionary-word SLDs are not
reported just because the left side is a word.
"""
    )

uploaded_files = st.file_uploader(
    "Upload auction/export files",
    type=["txt", "csv", "tsv", "log", "list"],
    accept_multiple_files=True,
    help="You can upload raw Dynadot/Namecheap-style text exports. Files are parsed as text, not as a fixed CSV schema.",
)

paste_text = st.text_area(
    "Or paste raw text",
    height=150,
    placeholder="12345   vir.us   $12.99   Auction\nparasit.es,19.50 EUR\nhttps://realm.sh/something",
)

with st.expander("Scanner settings", expanded=False):
    depth = st.selectbox(
        "Dictionary depth",
        options=["Common English", "Broad English"],
        index=0,
        help="Common is cleaner. Broad allows rarer words and produces more noise.",
    )
    default_zipf = 3.0 if depth == "Common English" else 1.7
    min_zipf = st.slider(
        "Minimum word frequency (Zipf)",
        min_value=1.0,
        max_value=5.5,
        value=float(default_zipf),
        step=0.1,
        help="Higher = more familiar words. 3.0 is a practical clean default.",
    )
    min_word_length = st.slider("Minimum reconstructed word length", 3, 15, 4)
    include_plus_one = st.checkbox("Include word + one trailing character", value=True)

    custom_dict_file = st.file_uploader(
        "Optional custom dictionary",
        type=["txt", "csv"],
        accept_multiple_files=False,
        help="Optional: upload your own words_alpha.txt or specialist word list. Custom words are accepted regardless of frequency threshold.",
        key="custom_dictionary",
    )

scan_clicked = st.button("Scan domain hacks", type="primary", use_container_width=True)

if scan_clicked:
    domain_lists: list[list[str]] = []
    input_rows = []

    for uploaded in uploaded_files or []:
        domains, stats = extract_domains_from_bytes(uploaded.getvalue())
        domain_lists.append(domains)
        input_rows.append(
            {
                "source": uploaded.name,
                "extracted": stats.extracted,
                "unique_in_source": stats.unique,
                "encoding": stats.encoding,
            }
        )

    if paste_text.strip():
        domains, stats = extract_domains(paste_text)
        domain_lists.append(domains)
        input_rows.append(
            {
                "source": "pasted text",
                "extracted": stats.extracted,
                "unique_in_source": stats.unique,
                "encoding": "text area",
            }
        )

    domains = merge_domain_lists(domain_lists)

    custom_words: set[str] = set()
    if custom_dict_file is not None:
        custom_raw = custom_dict_file.getvalue()
        for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                custom_text = custom_raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            custom_text = custom_raw.decode("utf-8", errors="replace")
        custom_words = parse_custom_wordlist(custom_text)

    if not domains:
        st.warning("No domain-looking tokens were found in the uploaded/pasted text.")
    else:
        def lookup(candidate: str):
            return lookup_word(candidate, min_zipf=min_zipf, custom_words=custom_words)

        try:
            results = scan_domains(
                domains,
                lookup=lookup,
                include_plus_one=include_plus_one,
                min_word_length=min_word_length,
            )
        except RuntimeError as exc:
            st.error(str(exc))
            st.stop()

        st.session_state["scan_domains"] = domains
        st.session_state["scan_results"] = [r.to_dict() for r in results]
        st.session_state["scan_inputs"] = input_rows
        st.session_state["scan_custom_words"] = len(custom_words)

if "scan_results" in st.session_state:
    results = st.session_state["scan_results"]
    domains = st.session_state.get("scan_domains", [])

    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Domains scanned", f"{len(domains):,}")
    c2.metric("Hacks found", f"{len(results):,}")
    c3.metric("Hit rate", f"{(len(results) / max(len(domains), 1) * 100):.2f}%")

    if st.session_state.get("scan_custom_words"):
        st.caption(f"Custom dictionary words loaded: {st.session_state['scan_custom_words']:,}")

    if not results:
        st.info("No domain hacks matched the current dictionary threshold/settings.")
    else:
        df = pd.DataFrame(results)
        df["type"] = df["hack_type"].map({"EXACT": "Exact", "PLUS_1": "+1"})
        df["split"] = (df["split_ratio"] * 100).round(1).astype(str) + "%"
        df["zipf"] = df["zipf"].round(2)

        filter_type = st.segmented_control(
            "Type",
            options=["All", "Exact", "+1"],
            default="All",
        )
        min_score_filter = st.slider("Minimum score", 0, 100, 0, key="result_min_score")

        shown = df[df["score"] >= min_score_filter].copy()
        if filter_type == "Exact":
            shown = shown[shown["type"] == "Exact"]
        elif filter_type == "+1":
            shown = shown[shown["type"] == "+1"]

        shown = shown.sort_values(["score", "zipf"], ascending=[False, False])

        st.subheader(f"Results · {len(shown):,}")

        # Compact cards make the best hits readable on mobile without horizontal scrolling.
        for row in shown.head(20).itertuples(index=False):
            extra_text = f" · extra: {row.extra.upper()}" if row.extra else ""
            st.markdown(
                f"""
<div class="result-card">
  <div class="result-domain">{row.score:02d} · {row.domain}</div>
  <div>{row.word.upper()}</div>
  <div class="result-meta">{row.type}{extra_text} · Zipf {row.zipf:.2f} · TLD contributes {row.tld_chars_in_word} char(s)</div>
</div>
""",
                unsafe_allow_html=True,
            )

        if len(shown) > 20:
            st.caption("Top 20 shown as mobile cards. Full filtered set is in the table/downloads below.")

        display_cols = [
            "domain",
            "word",
            "type",
            "extra",
            "score",
            "zipf",
            "split",
            "tld_chars_in_word",
        ]
        st.dataframe(
            shown[display_cols],
            hide_index=True,
            use_container_width=True,
            column_config={
                "domain": "Domain",
                "word": "Word",
                "type": "Type",
                "extra": "Extra",
                "score": st.column_config.NumberColumn("Score", format="%d"),
                "zipf": st.column_config.NumberColumn("Zipf", format="%.2f"),
                "split": "TLD share",
                "tld_chars_in_word": "TLD chars",
            },
        )

        csv_cols = [
            "domain",
            "word",
            "type",
            "extra",
            "score",
            "zipf",
            "split_ratio",
            "tld_chars_in_word",
            "sld",
            "tld",
            "word_source",
        ]
        csv_bytes = shown[csv_cols].to_csv(index=False).encode("utf-8")
        txt_bytes = ("\n".join(shown["domain"].tolist()) + "\n").encode("utf-8")

        d1, d2 = st.columns(2)
        d1.download_button(
            "Download CSV",
            data=csv_bytes,
            file_name="domain_hacks.csv",
            mime="text/csv",
            use_container_width=True,
        )
        d2.download_button(
            "Download TXT",
            data=txt_bytes,
            file_name="domain_hacks.txt",
            mime="text/plain",
            use_container_width=True,
        )

        with st.expander("Input parsing details", expanded=False):
            input_rows = st.session_state.get("scan_inputs", [])
            if input_rows:
                st.dataframe(pd.DataFrame(input_rows), hide_index=True, use_container_width=True)

st.divider()
st.markdown(
    "<div class='small-note'>Lexical scanner only: it does not check registration status, trademarks, UDRP risk, pricing or whether a TLD is currently delegated. Uploaded files are processed in app memory; this code does not intentionally persist them.</div>",
    unsafe_allow_html=True,
)
