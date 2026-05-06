from __future__ import annotations

import pytest

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
