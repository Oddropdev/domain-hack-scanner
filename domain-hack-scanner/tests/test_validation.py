from hack_detector import detect_domain_hack
from lexicon import WordEvidence


def lookup(word: str) -> WordEvidence:
    return WordEvidence(True, 4.0, "test")


def test_direct_detection_rejects_non_letters_and_non_ascii():
    for domain in ["v1r.us", "vi-r.us", "vi_r.us", "vïr.us",
                   "vir.u5", "vir.üs", "vir..us"]:
        assert detect_domain_hack(domain, lookup=lookup) is None


def test_valid_letter_only_hack_still_detected():
    assert detect_domain_hack("VIR.US", lookup=lookup) is not None
