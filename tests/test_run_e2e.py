"""End-to-end CLI tests: full scrape → R2 / --out file."""
from __future__ import annotations

import json
from pathlib import Path

import boto3
import httpx
import pytest
import respx
from moto import mock_aws

from yasli_scraper import r2 as r2_module
from yasli_scraper.__main__ import REQUIRED_ENV_VARS, main
from yasli_scraper.source import BASE_URL, REGIONS_PATH

from .fixtures import load_html

BUCKET = "yasli-snapshots-e2e"

PIPELINE_INSTITUTIONS = [
    ("infant", "39", "infant_39.html", 'ДГ№6 "Палечко"'),
    ("garden", "34", "garden_34.html", 'ДГ№1 "Светулка"'),
    ("pg", "10", "pg_10.html", 'ОУ "Капитан Петко войвода"'),
]


def _rajon_url(reception: str, ext_id: str) -> str:
    return f"{BASE_URL}/lv/documents/{reception}/varna/rajon/{ext_id}.html"


def _mock_scrape() -> None:
    by_reception: dict[str, list[dict[str, str]]] = {
        "infant": [],
        "garden": [],
        "pg": [],
    }
    for reception, ext_id, fixture, name in PIPELINE_INSTITUTIONS:
        url = _rajon_url(reception, ext_id)
        by_reception[reception].append({"DZ_NAME": name, "RAJON": url})
        respx.get(url).mock(
            return_value=httpx.Response(200, content=load_html(fixture))
        )
    for reception, entries in by_reception.items():
        respx.post(
            f"{BASE_URL}{REGIONS_PATH}", json={"reception": reception}
        ).mock(
            return_value=httpx.Response(
                200,
                content=json.dumps({"childhoodRajon": entries}).encode(),
            )
        )


@pytest.fixture
def all_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("R2_ACCOUNT_ID", "fake-account-id")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "fake-key")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "fake-secret")
    monkeypatch.setenv("R2_BUCKET", BUCKET)
    import os

    for name in REQUIRED_ENV_VARS:
        assert os.environ[name]


@pytest.fixture
def no_r2_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in REQUIRED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@respx.mock
def test_run_writes_full_snapshot_to_r2(
    monkeypatch: pytest.MonkeyPatch, all_env: None
) -> None:
    _mock_scrape()

    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        monkeypatch.setattr(r2_module, "make_client", lambda env=None: client)

        rc = main(["run", "--city", "varna"])
        assert rc == 0

        objects = client.list_objects_v2(Bucket=BUCKET, Prefix="snapshots/varna/")
        keys = sorted(o["Key"] for o in objects.get("Contents", []))
        assert "snapshots/varna/latest.json" in keys
        assert len(keys) == 2

        latest = client.get_object(Bucket=BUCKET, Key="snapshots/varna/latest.json")
        payload = json.loads(latest["Body"].read())
        assert payload["schema_version"] == 1
        assert payload["city"] == "varna"
        assert payload["scraped_at"].endswith("Z")
        assert len(payload["institutions"]) == len(PIPELINE_INSTITUTIONS)
        kinds = {i["kind"] for i in payload["institutions"]}
        assert kinds == {"nursery", "kindergarten", "preschool"}


@respx.mock
def test_out_writes_file_and_skips_r2(
    monkeypatch: pytest.MonkeyPatch, no_r2_env: None, tmp_path: Path
) -> None:
    """`--out` writes the file, does not instantiate the R2 client."""
    _mock_scrape()

    def _fail_r2(env=None):  # pragma: no cover - should not be called
        raise AssertionError("R2 client must not be instantiated when --out is set")

    monkeypatch.setattr(r2_module, "make_client", _fail_r2)

    out = tmp_path / "snap.json"
    rc = main(["run", "--city", "varna", "--out", str(out)])
    assert rc == 0
    assert out.exists()
    payload = json.loads(out.read_text())
    assert payload["schema_version"] == 1
    assert len(payload["institutions"]) == len(PIPELINE_INSTITUTIONS)


@respx.mock
def test_out_works_without_r2_env(
    no_r2_env: None, tmp_path: Path
) -> None:
    _mock_scrape()
    out = tmp_path / "snap.json"
    rc = main(["run", "--city", "varna", "--out", str(out)])
    assert rc == 0
    payload = json.loads(out.read_text())
    assert payload["city"] == "varna"


def test_out_with_missing_parent_exits_nonzero(
    capsys: pytest.CaptureFixture[str], no_r2_env: None
) -> None:
    """`--out` with a non-existent parent dir bails before scraping."""
    rc = main(["run", "--city", "varna", "--out", "/no/such/dir/snap.json"])
    assert rc != 0
    err = capsys.readouterr().err
    assert "/no/such/dir" in err
