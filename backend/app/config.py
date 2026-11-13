"""Backend-only configuration; loading settings creates no application data or connections."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ADI_",
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    environment: Literal["development", "test", "production"] = "development"
    data_dir: Path = BACKEND_ROOT / "data"
    sqlite_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    model_api_key: SecretStr | None = Field(default=None, repr=False)
    uploads_enabled: bool = True
    upload_max_bytes: int = Field(default=25_000_000, gt=0, le=25_000_000)
    upload_max_rows: int = Field(default=100_000, gt=0, le=100_000)
    upload_max_columns: int = Field(default=256, gt=0, le=256)
    import_timeout_seconds: float = Field(default=45.0, gt=0, le=120)

    @field_validator("data_dir")
    @classmethod
    def normalize_data_dir(cls, value: Path) -> Path:
        expanded = value.expanduser()
        return (expanded if expanded.is_absolute() else BACKEND_ROOT / expanded).resolve()

    @property
    def database_path(self) -> Path:
        return self.data_dir / "metadata.sqlite3"
