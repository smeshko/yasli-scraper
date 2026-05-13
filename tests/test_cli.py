from __future__ import annotations

import os
from pathlib import Path

import pytest

import yasli_scraper.__main__ as scraper_main
from yasli_scraper.__main__ import REQUIRED_ENV_VARS, main


@pytest.fixture
def all_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in REQUIRED_ENV_VARS:
        monkeypatch.setenv(name, f"test-{name.lower()}")


def test_missing_city_exits_nonzero_with_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # argparse calls sys.exit(2) and prints usage to stderr on missing required arg.
    with pytest.raises(SystemExit) as exc_info:
        main(["run"])
    assert exc_info.value.code != 0
    err = capsys.readouterr().err
    assert "usage" in err.lower()
    assert "--city" in err


def test_unknown_subcommand_exits_nonzero_with_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["bogus"])
    assert exc_info.value.code != 0
    err = capsys.readouterr().err
    assert "usage" in err.lower()


def test_no_subcommand_exits_nonzero_with_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code != 0
    err = capsys.readouterr().err
    assert "usage" in err.lower()


@pytest.mark.parametrize("missing", list(REQUIRED_ENV_VARS))
def test_missing_env_var_exits_nonzero_naming_var(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    missing: str,
) -> None:
    for name in REQUIRED_ENV_VARS:
        monkeypatch.setenv(name, f"test-{name.lower()}")
    monkeypatch.delenv(missing, raising=False)

    rc = main(["run", "--city", "varna"])
    assert rc != 0
    err = capsys.readouterr().err
    assert missing in err


def test_empty_env_var_treated_as_missing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    for name in REQUIRED_ENV_VARS:
        monkeypatch.setenv(name, f"test-{name.lower()}")
    monkeypatch.setenv("R2_BUCKET", "")

    rc = main(["run", "--city", "varna"])
    assert rc != 0
    err = capsys.readouterr().err
    assert "R2_BUCKET" in err


def _write_repo_env(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "R2_ACCOUNT_ID=file-account-id",
                "R2_ACCESS_KEY_ID=file-access-key",
                "R2_SECRET_ACCESS_KEY=file-secret",
                "R2_BUCKET=file-bucket",
            ]
        ),
        encoding="utf-8",
    )


def test_validate_env_reads_r2_values_from_repo_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_env = tmp_path / ".env"
    _write_repo_env(repo_env)
    monkeypatch.setattr(scraper_main, "REPO_ENV_PATH", repo_env)
    for name in REQUIRED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    assert scraper_main.validate_env() is None
    assert os.environ["R2_ACCOUNT_ID"] == "file-account-id"
    assert os.environ["R2_ACCESS_KEY_ID"] == "file-access-key"
    assert os.environ["R2_SECRET_ACCESS_KEY"] == "file-secret"
    assert os.environ["R2_BUCKET"] == "file-bucket"


def test_exported_r2_bucket_overrides_repo_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_env = tmp_path / ".env"
    _write_repo_env(repo_env)
    monkeypatch.setattr(scraper_main, "REPO_ENV_PATH", repo_env)
    for name in REQUIRED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("R2_BUCKET", "exported-bucket")

    assert scraper_main.validate_env() is None
    assert os.environ["R2_BUCKET"] == "exported-bucket"
