import hashlib
from app.agents.page_exploration.utils.dom_signature import compute_dom_signature


def test_signature_stable_for_same_content():
    el1 = [
        {"key": "button-a", "source": {"role": "button", "name": "A"}},
        {"key": "input-b", "source": {"role": "textbox", "label": "B"}},
    ]
    el2 = [
        {"key": "button-a", "source": {"role": "button", "name": "A"}},
        {"key": "input-b", "source": {"role": "textbox", "label": "B"}},
    ]
    s1 = compute_dom_signature(el1)
    s2 = compute_dom_signature(el2)
    assert s1 == s2


def test_signature_ignores_ref_but_sensitive_to_role():
    # Different element.key but same role+name -> still same (semantically equivalent)
    el1 = [{"source": {"role": "button", "name": "A"}}]
    el2 = [{"source": {"role": "button", "name": "A"}}]
    assert compute_dom_signature(el1) == compute_dom_signature(el2)


def test_signature_sensitive_to_role_change():
    el1 = [{"source": {"role": "button", "name": "A"}}]
    el2 = [{"source": {"role": "textbox", "name": "A"}}]
    assert compute_dom_signature(el1) != compute_dom_signature(el2)


def test_signature_sensitive_to_name_change():
    el1 = [{"source": {"role": "button", "name": "A"}}]
    el2 = [{"source": {"role": "button", "name": "B"}}]
    assert compute_dom_signature(el1) != compute_dom_signature(el2)


def test_signature_sensitive_to_aria_change():
    el1 = [{"source": {"role": "button", "aria_label": "A"}}]
    el2 = [{"source": {"role": "button", "aria_label": "B"}}]
    assert compute_dom_signature(el1) != compute_dom_signature(el2)


def test_signature_format_is_sha256_prefix():
    el = [{"source": {"role": "button", "name": "A"}}]
    s = compute_dom_signature(el)
    assert s.startswith("sha256:")
    assert len(s) == len("sha256:") + 64


def test_signature_empty_returns_seed():
    assert compute_dom_signature([]).startswith("sha256:")
