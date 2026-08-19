import pytest
from app.normalization.normalizer import normalize_domain
from app.rules.overrides import BrandOverrideEngine


def test_brand_overrides_matching(override_engine):
    # discord.com -> Communication
    norm_discord = normalize_domain("https://discord.com/channels/@me")
    match_discord = override_engine.match(norm_discord)
    assert match_discord is not None
    assert match_discord.category == "Communication"
    assert match_discord.category_id == 1

    # telegram.org -> Communication
    norm_tg = normalize_domain("telegram.org")
    match_tg = override_engine.match(norm_tg)
    assert match_tg is not None
    assert match_tg.category == "Communication"

    # whatsapp.com -> Communication
    norm_wa = normalize_domain("whatsapp.com")
    match_wa = override_engine.match(norm_wa)
    assert match_wa is not None
    assert match_wa.category == "Communication"

    # youtube.com -> Entertainment & Media
    norm_yt = normalize_domain("https://www.youtube.com/watch?v=123")
    match_yt = override_engine.match(norm_yt)
    assert match_yt is not None
    assert match_yt.category == "Entertainment & Media"
    assert match_yt.category_id == 7


def test_unregistered_domain_returns_none(override_engine):
    norm_unknown = normalize_domain("https://random-unknown-site.org")
    match_unknown = override_engine.match(norm_unknown)
    assert match_unknown is None
