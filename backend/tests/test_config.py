from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from affiche.config import BACKEND_DIR, ConfigError, load_settings

NAMES = ("IMAGE_PROVIDER", "OPENAI_API_KEY", "SPEND_CAP_USD", "SPEND_CAP_SINCE", "ESTIMATE_SCENE_USD",
         "ESTIMATE_BACKGROUND_USD", "ATTEMPT_LIMIT", "DATA_DIR")
TODAY = datetime.now(UTC).date()
TOMORROW = (TODAY + timedelta(days=1)).isoformat()
SECRET = "sk-test-must-never-be-printed"


@pytest.fixture
def env(monkeypatch):
    """A valid environment. The developer's real .env (env_file=None) and shell variables are never read."""
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SPEND_CAP_USD", "20")
    monkeypatch.setenv("SPEND_CAP_SINCE", TODAY.isoformat())
    return monkeypatch


def load():
    return load_settings(env_file=None)


def test_valid_config_with_defaults(env):
    settings = load()
    assert settings.image_provider == "stub"
    assert settings.spend_cap_usd == Decimal("20")
    assert settings.spend_cap_since == TODAY
    assert settings.estimate_scene_usd == Decimal("0.40")
    assert settings.estimate_background_usd == Decimal("0.30")
    assert settings.attempt_limit == 3
    assert settings.data_dir == BACKEND_DIR / "data"


def test_relative_data_dir_is_resolved_from_backend(env):
    env.setenv("DATA_DIR", "data-stub")
    assert load().data_dir == BACKEND_DIR / "data-stub"


@pytest.mark.parametrize(("overrides", "match"), [
    ({"SPEND_CAP_USD": None}, "spend_cap_usd"),
    ({"SPEND_CAP_USD": "0"}, "spend_cap_usd"),
    ({"SPEND_CAP_USD": "-1"}, "spend_cap_usd"),
    ({"SPEND_CAP_USD": "inf"}, "spend_cap_usd"),
    ({"SPEND_CAP_USD": "-inf"}, "spend_cap_usd"),
    ({"SPEND_CAP_USD": "nan"}, "spend_cap_usd"),
    ({"SPEND_CAP_SINCE": None}, "spend_cap_since"),
    ({"SPEND_CAP_SINCE": TOMORROW}, "spend_cap_since"),
    ({"ESTIMATE_SCENE_USD": "0"}, "estimate_scene_usd"),
    ({"ESTIMATE_SCENE_USD": "-0.40"}, "estimate_scene_usd"),
    ({"ESTIMATE_BACKGROUND_USD": "0"}, "estimate_background_usd"),
    ({"ESTIMATE_BACKGROUND_USD": "-0.30"}, "estimate_background_usd"),
    ({"ATTEMPT_LIMIT": "0"}, "attempt_limit"),
    ({"IMAGE_PROVIDER": "openai"}, "OPENAI_API_KEY is required"),
    ({"IMAGE_PROVIDER": "openai", "OPENAI_API_KEY": ""}, "OPENAI_API_KEY is required"),
])
def test_invalid_config_is_refused(env, overrides, match):
    for name, value in overrides.items():
        if value is None:
            env.delenv(name)
        else:
            env.setenv(name, value)
    with pytest.raises(ConfigError, match=match):
        load()


def test_all_errors_are_listed(env):
    env.setenv("SPEND_CAP_USD", "0")
    env.setenv("ATTEMPT_LIMIT", "0")
    with pytest.raises(ConfigError, match="2 validation errors"):
        load()


def test_api_key_never_appears(env):
    env.setenv("IMAGE_PROVIDER", "openai")
    env.setenv("OPENAI_API_KEY", SECRET)
    settings = load()
    assert settings.openai_api_key.get_secret_value() == SECRET
    assert SECRET not in repr(settings) and SECRET not in str(settings)

    env.setenv("SPEND_CAP_USD", "0")
    env.setenv("SPEND_CAP_SINCE", TOMORROW)
    with pytest.raises(ConfigError) as caught:
        load()
    assert SECRET not in str(caught.value) and SECRET not in repr(caught.value)
    assert caught.value.__context__ is None and caught.value.__cause__ is None
