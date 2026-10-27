from pathlib import Path

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ShowcaseSettings(BaseSettings):
    asset_root: Path
    dynbench_base_url: AnyHttpUrl = "http://127.0.0.1:8766"
    dynbench_public_base_url: AnyHttpUrl | None = None
    dynbench_timeout_seconds: float = 1.5
    showcase_title: str = "课题二：动态 Benchmark 与异常样本生命周期"

    model_config = SettingsConfigDict(
        env_prefix="TOPIC2_SHOWCASE_",
        extra="ignore",
    )

    @field_validator("asset_root")
    @classmethod
    def resolve_asset_root(cls, value: Path) -> Path:
        return value.expanduser().resolve()
