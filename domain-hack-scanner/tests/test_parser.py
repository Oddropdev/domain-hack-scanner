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
