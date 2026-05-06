"""End-to-end test: CLI `run` subcommand → stub envelope → R2 put_snapshot."""
from __future__ import annotations

import json

import boto3
import pytest
from moto import mock_aws

from yasli_scraper import r2 as r2_module
from yasli_scraper.__main__ import REQUIRED_ENV_VARS, main

BUCKET = "yasli-snapshots-e2e"


@pytest.fixture
def all_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("R2_ACCOUNT_ID", "fake-account-id")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "fake-key")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "fake-secret")
    monkeypatch.setenv("R2_BUCKET", BUCKET)
    # Sanity: every required var is now set.
    import os

    for name in REQUIRED_ENV_VARS:
        assert os.environ[name]


def test_run_writes_stub_snapshot_to_r2(
    monkeypatch: pytest.MonkeyPatch, all_env: None
) -> None:
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)

        # Bypass the real R2 endpoint config; reuse moto's mocked client.
        monkeypatch.setattr(r2_module, "make_client", lambda env=None: client)

        rc = main(["run", "--city", "varna"])
        assert rc == 0

        objects = client.list_objects_v2(Bucket=BUCKET, Prefix="snapshots/varna/")
        keys = sorted(o["Key"] for o in objects.get("Contents", []))
        assert "snapshots/varna/latest.json" in keys
        # Exactly one timestamped object plus latest.
        assert len(keys) == 2

        latest = client.get_object(Bucket=BUCKET, Key="snapshots/varna/latest.json")
        payload = json.loads(latest["Body"].read())
        assert payload["schema_version"] == 1
        assert payload["city"] == "varna"
        assert payload["institutions"] == []
        assert payload["scraped_at"].endswith("Z")
