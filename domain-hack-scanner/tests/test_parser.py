from domain_parser import decode_bytes, extract_domains


def test_messy_registrar_text_extracts_domains_and_ignores_prices_email_and_duplicates():
    text = """
    12345 vir.us $12.99 auction
    parasit.es,19.50 EUR
    https://realm.sh/path?q=1
    sales@example.com
    2026.09 1.2.3
    vir.us duplicate
    """
    domains, stats = extract_domains(text)
    assert domains == ["vir.us", "parasit.es", "realm.sh"]
    assert stats.extracted == 4
    assert stats.unique == 3
    assert stats.duplicates_removed == 1


def test_decode_cp1252():
    raw = "realm.sh €12,99".encode("cp1252")
    text, encoding = decode_bytes(raw)
    assert "realm.sh" in text
    assert encoding in {"cp1252", "latin-1"}


def test_letters_only_rejects_invalid_names_without_salvaging_substrings():
    text = """
    vir.us
    https://www.PARASIT.ES/path
    vir2.us
    vi-r.us
    vir_.us
    vir.us_extra
    vïr.us
    ｖｉｒ.us
    2vir.us
    vi_r.us
    vir.2us
    vir.us-park
    foo1.bar.com
    foo+bar.com
    foo!bar.com
    """
    domains, stats = extract_domains(text)
    assert domains == ["vir.us", "parasit.es"]
    assert stats.unique == 2


def test_domain_validator_rejects_invalid_characters_in_any_label():
    from domain_parser import _valid_domain

    for name in ["a1.us", "a-b.us", "a_b.us", "a+z.us",
                 "a.1us", "a..us", "näme.us"]:
        assert not _valid_domain(name)
    assert _valid_domain("safe.domain.com")
