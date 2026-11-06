import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"

PositiveUsd = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
# The provider_calls.error_kind values the gateway can produce (D-PV-001). Defined here, not in the gateway,
# so that loading settings does not import the provider SDK.
ProviderErrorKind = Literal["refused", "quota", "rate_limited", "timeout", "provider_error", "invalid_request",
                            "invalid_response", "auth"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_ignore_empty=True,  # a copied .env.example ("NAME=") keeps the defaults
        extra="ignore",  # .env holds names that later tasks read
        hide_input_in_errors=True,  # a model-level error would otherwise print every raw input, the key included
    )

    image_provider: Literal["stub", "openai"] = "stub"
    openai_api_key: SecretStr | None = None
    stub_fail: ProviderErrorKind | None = None  # every stub call fails with this kind (manual runs)
    spend_cap_usd: PositiveUsd  # no default: no cap, nothing starts (ADR-010)
    spend_cap_since: date
    estimate_scene_usd: PositiveUsd = Decimal("0.40")
    estimate_background_usd: PositiveUsd = Decimal("0.30")
    attempt_limit: int = Field(3, ge=1)
    min_source_short_edge: int = Field(800, ge=1)  # a photo's shorter edge below this → low_resolution warning
    rembg_model: str = "birefnet-general-lite"
    max_hole_ratio: float = Field(0.05, gt=0, lt=1)
    data_dir: Path = BACKEND_DIR / "data"

    @field_validator("spend_cap_since")
    @classmethod
    def _not_in_future(cls, value: date) -> date:
        if value > datetime.now(UTC).date():
            raise ValueError("must not be after today (UTC)")
        return value

    @field_validator("openai_api_key")
    @classmethod
    def _printable_ascii_key(cls, value: SecretStr | None) -> SecretStr | None:
        # A pasted invisible character (U+200B) would fail later, in header building, with an error that prints
        # the whole key. The message is constant: it never contains the value.
        if value is not None and not re.fullmatch(r"[!-~]+", value.get_secret_value()):
            raise ValueError("must be printable ASCII with no whitespace")
        return value

    @field_validator("data_dir")
    @classmethod
    def _relative_to_backend(cls, value: Path) -> Path:
        return value if value.is_absolute() else BACKEND_DIR / value

    @model_validator(mode="after")
    def _key_for_openai(self) -> "Settings":
        if self.image_provider == "openai" and self.openai_api_key is None:
            raise ValueError("OPENAI_API_KEY is required when IMAGE_PROVIDER=openai")
        return self

    @model_validator(mode="after")
    def _stub_fail_only_for_stub(self) -> "Settings":
        # A paid run must never be told to fake failures.
        if self.stub_fail is not None and self.image_provider != "stub":
            raise ValueError("STUB_FAIL is only allowed when IMAGE_PROVIDER=stub")
        return self


class ConfigError(Exception):
    """Invalid startup configuration. The message lists every error and never contains an input value."""


def load_settings(env_file: Path | None = ENV_FILE) -> Settings:
    try:
        return Settings(_env_file=env_file)
    except ValidationError as error:
        # str() honours hide_input_in_errors; error.errors() and error.json() still carry the raw
        # inputs (the API key included), so the ValidationError must not travel, not even as __context__.
        message = str(error)
    raise ConfigError(message)
