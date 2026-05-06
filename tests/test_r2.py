from __future__ import annotations

import json
from datetime import datetime, timezone

import boto3
import pytest
from moto import mock_aws

from yasli_scraper.r2 import put_snapshot

BUCKET = "yasli-snapshots-test"


@pytest.fixture
def s3_client():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


def test_put_snapshot_writes_both_keys(s3_client) -> None:
    payload = {"schema_version": 1, "city": "varna", "institutions": []}
    fixed_now = datetime(2026, 5, 6, 12, 30, 45, tzinfo=timezone.utc)

    timestamped_key, latest_key = put_snapshot(
        "varna", payload, client=s3_client, bucket=BUCKET, now=fixed_now
    )

    assert timestamped_key == "snapshots/varna/2026-05-06T12:30:45Z.json"
    assert latest_key == "snapshots/varna/latest.json"

    timestamped = s3_client.get_object(Bucket=BUCKET, Key=timestamped_key)
    latest = s3_client.get_object(Bucket=BUCKET, Key=latest_key)

    assert json.loads(timestamped["Body"].read()) == payload
    assert json.loads(latest["Body"].read()) == payload


def test_put_snapshot_writes_timestamped_before_latest(s3_client) -> None:
    """Order is load-bearing: timestamped first, latest second."""
    call_order: list[str] = []

    real_put = s3_client.put_object

    def tracking_put(**kwargs):
        call_order.append(kwargs["Key"])
        return real_put(**kwargs)

    s3_client.put_object = tracking_put  # type: ignore[method-assign]

    put_snapshot(
        "varna",
        {"schema_version": 1, "city": "varna", "institutions": []},
        client=s3_client,
        bucket=BUCKET,
        now=datetime(2026, 5, 6, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert len(call_order) == 2
    assert call_order[0] == "snapshots/varna/2026-05-06T12:00:00Z.json"
    assert call_order[1] == "snapshots/varna/latest.json"


def test_put_snapshot_failure_on_first_write_does_not_touch_latest(s3_client) -> None:
    """If the timestamped write fails, latest.json must not be modified."""
    # Seed a previous "good" latest.
    previous = {"schema_version": 1, "city": "varna", "institutions": ["previous"]}
    s3_client.put_object(
        Bucket=BUCKET,
        Key="snapshots/varna/latest.json",
        Body=json.dumps(previous).encode("utf-8"),
        ContentType="application/json",
    )

    real_put = s3_client.put_object

    def failing_put(**kwargs):
        if kwargs["Key"].endswith("latest.json"):
            return real_put(**kwargs)
        raise RuntimeError("simulated R2 failure on timestamped write")

    s3_client.put_object = failing_put  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="simulated R2 failure"):
        put_snapshot(
            "varna",
            {"schema_version": 1, "city": "varna", "institutions": ["new"]},
            client=s3_client,
            bucket=BUCKET,
            now=datetime(2026, 5, 6, 13, 0, 0, tzinfo=timezone.utc),
        )

    # latest.json must still hold the previous payload.
    s3_client.put_object = real_put  # type: ignore[method-assign]
    latest = s3_client.get_object(Bucket=BUCKET, Key="snapshots/varna/latest.json")
    assert json.loads(latest["Body"].read()) == previous
