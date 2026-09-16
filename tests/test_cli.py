from __future__ import annotations

import json
import os
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

import yasli_scraper.__main__ as scraper_main
from yasli_scraper import pipeline as pipeline_module
from yasli_scraper import r2 as r2_module
from yasli_scraper.__main__ import REQUIRED_ENV_VARS, main
from yasli_scraper.check import check_snapshot
from yasli_scraper.models import AddressEntry, Institution, Snapshot


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


def _one_institution_snapshot() -> Snapshot:
    return Snapshot(
        schema_version=2,
        scraped_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc),
        city="varna",
        institutions=[
            Institution(
                external_id="39",
                name='ДГ №7 "Изгрев"',
                kind="kindergarten",
                source_url="https://example.com/dz/39",
                address_entries=[AddressEntry(street="ул.Орех", number="12")],
                address="ул. Тестова 1",
                district_code=None,
                has_infant_group=False,
            )
        ],
    )


def test_sub_floor_snapshot_exits_nonzero_and_skips_upload(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    all_env: None,
) -> None:
    """A snapshot below MIN_EXPECTED_INSTITUTIONS must never reach R2."""
    snapshot = _one_institution_snapshot()
    assert len(snapshot.institutions) < scraper_main.MIN_EXPECTED_INSTITUTIONS

    async def _fake_run(city: str) -> Snapshot:
        return snapshot

    monkeypatch.setattr(pipeline_module, "run", _fake_run)

    def _fail_put(city: str, snap: Snapshot) -> None:
        raise AssertionError("put_snapshot must not be called for a sub-floor snapshot")

    monkeypatch.setattr(r2_module, "put_snapshot", _fail_put)

    rc = main(["run", "--city", "varna"])
    assert rc != 0
    err = capsys.readouterr().err
    assert "refusing to upload" in err
    assert str(len(snapshot.institutions)) in err


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


# --- check subcommand ---
#
# Files are built from Snapshot.model_dump_json() — the same serialisation the
# `run` command writes — then mutated as plain dicts so keys can be deleted.


def _varna_snapshot() -> Snapshot:
    """77 institutions matching EXPECTED_ROSTER["varna"]: 12 / 53 / 12."""

    def institution(**overrides: Any) -> Institution:
        base: dict[str, Any] = {
            "external_id": "39",
            "name": 'ДГ №7 "Изгрев"',
            "kind": "kindergarten",
            "source_url": "https://example.com/dz/39",
            "address_entries": [AddressEntry(street="ул.Орех", number="12")],
            "address": "ул. Тестова 1",
            "phone": "052/613039",
            "email": "info-400240@edu.mon.bg",
            "director": "Катя Григорова",
            "website": None,
            "district_code": None,
            "has_infant_group": False,
        }
        return Institution(**(base | overrides))

    institutions = [
        institution(
            external_id=str(i),
            name=f"ДЯ №{i}",
            kind="nursery",
            source_url=f"https://example.com/dy/{i}",
            district_code=f"0{i % 5 + 1}",
        )
        for i in range(1, 13)
    ]
    institutions += [
        institution(
            external_id=str(i),
            name='ДГ №6 "Палечко"' if i == 6 else f'ДГ №{i} "Тест"',
            source_url=f"https://example.com/dz/{i}",
            has_infant_group=i == 6,
        )
        for i in range(1, 54)
    ]
    institutions += [
        institution(
            external_id=f"pg{i}",
            name=f"ОУ №{i}",
            kind="preschool",
            source_url=f"https://example.com/pg/{i}",
            website=f"https://school{i}.example.com/",
        )
        for i in range(1, 13)
    ]
    return Snapshot(
        schema_version=2,
        scraped_at=datetime(2026, 9, 15, 13, 5, 33, tzinfo=timezone.utc),
        city="varna",
        institutions=institutions,
    )


def _snapshot_dict() -> dict[str, Any]:
    return json.loads(_varna_snapshot().model_dump_json())


def _write_json(tmp_path: Path, payload: Any) -> Path:
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _write_mutated(tmp_path: Path, mutate: Callable[[dict[str, Any]], None]) -> Path:
    payload = _snapshot_dict()
    mutate(payload)
    return _write_json(tmp_path, payload)


def _delete_phone_key(payload: dict[str, Any]) -> None:
    del payload["institutions"][0]["phone"]


def _null_phone(payload: dict[str, Any]) -> None:
    payload["institutions"][0]["phone"] = None


def _drop_a_nursery(payload: dict[str, Any]) -> None:
    payload["institutions"].pop(0)


def _null_institutions(payload: dict[str, Any]) -> None:
    payload["institutions"] = None


def _unchanged(payload: dict[str, Any]) -> None:
    pass


def _file_missing_phone_key(tmp_path: Path) -> Path:
    return _write_mutated(tmp_path, _delete_phone_key)


def _file_null_phone(tmp_path: Path) -> Path:
    return _write_mutated(tmp_path, _null_phone)


def _file_wrong_nursery_count(tmp_path: Path) -> Path:
    return _write_mutated(tmp_path, _drop_a_nursery)


def _file_malformed_shape(tmp_path: Path) -> Path:
    return _write_mutated(tmp_path, _null_institutions)


def _file_invalid_utf8(tmp_path: Path) -> Path:
    path = tmp_path / "snapshot.json"
    path.write_bytes(b"\xff{")
    return path


def _file_utf16(tmp_path: Path) -> Path:
    path = tmp_path / "snapshot.json"
    path.write_bytes(json.dumps(_snapshot_dict(), ensure_ascii=False).encode("utf-16"))
    return path


def _file_deeply_nested(tmp_path: Path) -> Path:
    path = tmp_path / "snapshot.json"
    path.write_bytes(b"[" * 100_000)
    return path


def _file_valid(tmp_path: Path) -> Path:
    return _write_mutated(tmp_path, _unchanged)


def test_check_valid_file_exits_zero_with_json_summary_and_no_r2_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    for name in REQUIRED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    path = _file_valid(tmp_path)

    rc = main(["check", str(path)])

    out, err = capsys.readouterr()
    assert rc == 0
    assert err == ""
    summary = json.loads(out)
    assert summary["total"] == 77
    assert summary["kinds"] == {"nursery": 12, "kindergarten": 53, "preschool": 12}
    assert out.startswith("{\n  ")  # indented, one object


def test_check_prints_summary_without_ascii_escaping(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = _snapshot_dict() | {"city": "варна"}
    path = _write_json(tmp_path, payload)

    rc = main(["check", str(path)])

    out, err = capsys.readouterr()
    assert rc == 1  # unknown city — the summary is still printed
    assert '"city": "варна"' in out
    assert "\\u" not in out


@pytest.mark.parametrize(
    ("make_file", "extra_argv", "expected"),
    [
        pytest.param(_file_missing_phone_key, [], ("phone",), id="missing-contact-key"),
        pytest.param(_file_null_phone, [], ("phone",), id="null-phone"),
        pytest.param(_file_wrong_nursery_count, [], ("11 nursery",), id="wrong-nursery-count"),
        pytest.param(_file_malformed_shape, [], ("contract:",), id="malformed-shape"),
        pytest.param(_file_invalid_utf8, [], ("invalid UTF-8",), id="invalid-utf8"),
        pytest.param(_file_utf16, [], ("invalid UTF-8",), id="utf16"),
        pytest.param(_file_deeply_nested, [], ("unusable JSON",), id="deeply-nested"),
        pytest.param(_file_valid, ["--city", "sofia"], ("varna", "sofia"), id="city-mismatch"),
    ],
)
def test_check_failure_exits_one_with_summary_and_one_line_per_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    make_file: Callable[[Path], Path],
    extra_argv: list[str],
    expected: tuple[str, ...],
) -> None:
    path = make_file(tmp_path)
    expected_city = extra_argv[1] if extra_argv else None
    report = check_snapshot(path.read_bytes(), expected_city=expected_city)
    assert not report.ok

    rc = main(["check", str(path), *extra_argv])

    out, err = capsys.readouterr()
    assert rc == 1
    json.loads(out)  # the summary is printed even when checks fail
    lines = err.splitlines()
    assert len(lines) == len(report.failures)
    assert all(line.startswith("check failed: ") for line in lines)
    assert any(all(fragment in line for fragment in expected) for line in lines)


def test_check_missing_path_exits_one_with_a_single_error_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "nope.json"

    rc = main(["check", str(path)])

    out, err = capsys.readouterr()
    assert rc == 1
    assert out == ""
    assert err.splitlines() == [err.rstrip("\n")]
    assert err.startswith("error: ")
    assert str(path) in err
    assert "Traceback" not in err


def test_check_directory_path_exits_one_with_a_single_error_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["check", str(tmp_path)])

    out, err = capsys.readouterr()
    assert rc == 1
    assert out == ""
    assert err.splitlines() == [err.rstrip("\n")]
    assert err.startswith("error: ")
    assert str(tmp_path) in err
    assert "Traceback" not in err


def test_check_matching_city_flag_adds_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _file_valid(tmp_path)

    rc = main(["check", str(path), "--city", "varna"])

    out, err = capsys.readouterr()
    assert rc == 0
    assert err == ""
    assert json.loads(out)["city"] == "varna"


def test_check_without_city_flag_uses_the_files_own_city(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write_json(tmp_path, _snapshot_dict() | {"city": "sofia"})

    rc = main(["check", str(path)])

    err = capsys.readouterr().err
    assert rc == 1
    assert any(line.startswith("check failed: ") and "sofia" in line for line in err.splitlines())
