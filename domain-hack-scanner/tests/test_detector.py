from hack_detector import detect_domain_hack, scan_domains
from lexicon import WordEvidence


WORDS = {
    "virus": 4.8,
    "parasites": 3.8,
    "realms": 3.9,
    "realm": 4.1,
}


def fake_lookup(word: str) -> WordEvidence:
    if word in WORDS:
        return WordEvidence(True, WORDS[word], "test")
    return WordEvidence(False, 0.0, "test")


def test_exact_virus_hack():
    hit = detect_domain_hack("vir.us", lookup=fake_lookup)
    assert hit is not None
    assert hit.word == "virus"
    assert hit.hack_type == "EXACT"
    assert hit.extra == ""
    assert hit.tld_chars_in_word == 2


def test_exact_parasites_hack():
    hit = detect_domain_hack("parasit.es", lookup=fake_lookup)
    assert hit is not None
    assert hit.word == "parasites"
    assert hit.hack_type == "EXACT"


def test_plus_one_realm_sh():
    hit = detect_domain_hack("realm.sh", lookup=fake_lookup)
    assert hit is not None
    assert hit.word == "realms"
    assert hit.hack_type == "PLUS_1"
    assert hit.extra == "h"
    assert hit.tld_chars_in_word == 1


def test_word_must_cross_dot():
    # realm itself being a word is not enough; joined/cross-dot candidate is not.
    hit = detect_domain_hack("realm.zz", lookup=fake_lookup)
    assert hit is None


def test_multilabel_suffix_is_intentionally_excluded_v1():
    assert detect_domain_hack("foo.co.uk", lookup=fake_lookup) is None


def test_scan_sorting_and_detection():
    hits = scan_domains(["realm.sh", "vir.us", "parasit.es"], lookup=fake_lookup)
    assert {h.domain for h in hits} == {"realm.sh", "vir.us", "parasit.es"}
    assert hits[0].score >= hits[-1].score
