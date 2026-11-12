from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import BACKEND_ROOT, Settings


def test_environment_overrides_dotenv_and_secrets_are_redacted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ADI_ENVIRONMENT=development\nADI_MODEL_API_KEY=private-example-key\n", encoding="utf-8"
    )
    monkeypatch.setenv("ADI_ENVIRONMENT", "test")
    settings = Settings(_env_file=env_file, data_dir=tmp_path / "metadata")
    assert settings.environment == "test"
    assert settings.model_api_key is not None
    assert settings.model_api_key.get_secret_value() == "private-example-key"
    assert "private-example-key" not in repr(settings)
    assert "private-example-key" not in settings.model_dump_json()
    assert not settings.data_dir.exists()


def test_relative_data_directory_is_anchored_to_backend_not_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None, data_dir=Path("data/example"))
    assert settings.database_path == BACKEND_ROOT / "data" / "example" / "metadata.sqlite3"


@pytest.mark.parametrize("timeout", [0, -1, 31, "not-a-number"])
def test_invalid_timeouts_are_rejected(timeout: object) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, sqlite_timeout_seconds=timeout)


def test_invalid_configuration_does_not_echo_its_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADI_ENVIRONMENT", "sensitive-invalid-input")
    with pytest.raises(ValidationError) as failure:
        Settings(_env_file=None)
    assert "sensitive-invalid-input" not in str(failure.value)
