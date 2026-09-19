from __future__ import annotations

import json
from datetime import datetime, timezone

import boto3
import pytest
from moto import mock_aws

from yasli_scraper.models import AddressEntry, Institution, Snapshot
from yasli_scraper.r2 import put_snapshot, put_snapshot_bytes, snapshot_keys

BUCKET = "yasli-snapshots-test"


def _make_snapshot(when: datetime | None = None) -> Snapshot:
    return Snapshot(
        schema_version=2,
        scraped_at=when or datetime(2026, 5, 6, 12, 30, 45, tzinfo=timezone.utc),
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


@pytest.fixture
def s3_client():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


def test_put_snapshot_writes_both_keys(s3_client) -> None:
    fixed_now = datetime(2026, 5, 6, 12, 30, 45, tzinfo=timezone.utc)
    payload = _make_snapshot(fixed_now)

    timestamped_key, latest_key = put_snapshot(
        "varna", payload, client=s3_client, bucket=BUCKET, now=fixed_now
    )

    assert timestamped_key == "snapshots/varna/2026-05-06T12:30:45Z.json"
    assert latest_key == "snapshots/varna/latest.json"

    timestamped = s3_client.get_object(Bucket=BUCKET, Key=timestamped_key)
    latest = s3_client.get_object(Bucket=BUCKET, Key=latest_key)

    expected = json.loads(payload.model_dump_json())
    assert json.loads(timestamped["Body"].read()) == expected
    assert json.loads(latest["Body"].read()) == expected


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
        _make_snapshot(datetime(2026, 5, 6, 12, 0, 0, tzinfo=timezone.utc)),
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
    previous_payload = {"schema_version": 2, "city": "varna", "institutions": ["previous"]}
    s3_client.put_object(
        Bucket=BUCKET,
        Key="snapshots/varna/latest.json",
        Body=json.dumps(previous_payload).encode("utf-8"),
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
            _make_snapshot(datetime(2026, 5, 6, 13, 0, 0, tzinfo=timezone.utc)),
            client=s3_client,
            bucket=BUCKET,
            now=datetime(2026, 5, 6, 13, 0, 0, tzinfo=timezone.utc),
        )

    # latest.json must still hold the previous payload.
    s3_client.put_object = real_put  # type: ignore[method-assign]
    latest = s3_client.get_object(Bucket=BUCKET, Key="snapshots/varna/latest.json")
    assert json.loads(latest["Body"].read()) == previous_payload


def test_put_snapshot_serialises_with_indent_two(s3_client) -> None:
    """`run`'s published bytes are pinned: put_snapshot owns the serialisation."""
    fixed_now = datetime(2026, 5, 6, 12, 30, 45, tzinfo=timezone.utc)
    payload = _make_snapshot(fixed_now)

    timestamped_key, latest_key = put_snapshot(
        "varna", payload, client=s3_client, bucket=BUCKET, now=fixed_now
    )

    expected = payload.model_dump_json(indent=2).encode("utf-8")
    for key in (timestamped_key, latest_key):
        assert s3_client.get_object(Bucket=BUCKET, Key=key)["Body"].read() == expected


def test_snapshot_keys_matches_what_put_snapshot_bytes_writes(s3_client) -> None:
    """The key layout has exactly one definition, so the two cannot drift."""
    fixed_now = datetime(2026, 7, 1, 8, 15, 0, tzinfo=timezone.utc)

    assert snapshot_keys("varna", fixed_now) == put_snapshot_bytes(
        "varna", b"{}", client=s3_client, bucket=BUCKET, now=fixed_now
    )


def test_put_snapshot_bytes_writes_the_given_bytes_to_both_keys(s3_client) -> None:
    """The body reaches both objects unmodified — no re-serialisation."""
    # Deliberately *not* what the model would emit: compact separators plus a
    # trailing newline. If anything re-serialised the payload, this would change.
    body = (
        json.dumps(json.loads(_make_snapshot().model_dump_json()), separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    fixed_now = datetime(2026, 5, 6, 12, 30, 45, tzinfo=timezone.utc)

    timestamped_key, latest_key = put_snapshot_bytes(
        "varna", body, client=s3_client, bucket=BUCKET, now=fixed_now
    )

    assert timestamped_key == "snapshots/varna/2026-05-06T12:30:45Z.json"
    assert latest_key == "snapshots/varna/latest.json"

    for key in (timestamped_key, latest_key):
        assert s3_client.get_object(Bucket=BUCKET, Key=key)["Body"].read() == body


def test_put_snapshot_bytes_writes_timestamped_before_latest(s3_client) -> None:
    """Order is load-bearing on the bytes path too."""
    call_order: list[str] = []

    real_put = s3_client.put_object

    def tracking_put(**kwargs):
        call_order.append(kwargs["Key"])
        return real_put(**kwargs)

    s3_client.put_object = tracking_put  # type: ignore[method-assign]

    put_snapshot_bytes(
        "varna",
        b'{"city": "varna"}',
        client=s3_client,
        bucket=BUCKET,
        now=datetime(2026, 5, 6, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert len(call_order) == 2
    assert call_order[0] == "snapshots/varna/2026-05-06T12:00:00Z.json"
    assert call_order[1] == "snapshots/varna/latest.json"


def test_put_snapshot_bytes_failure_on_first_write_does_not_touch_latest(
    s3_client,
) -> None:
    """If the timestamped write fails, latest.json must not be modified."""
    previous_payload = {"schema_version": 2, "city": "varna", "institutions": ["previous"]}
    s3_client.put_object(
        Bucket=BUCKET,
        Key="snapshots/varna/latest.json",
        Body=json.dumps(previous_payload).encode("utf-8"),
        ContentType="application/json",
    )

    real_put = s3_client.put_object

    def failing_put(**kwargs):
        if kwargs["Key"].endswith("latest.json"):
            return real_put(**kwargs)
        raise RuntimeError("simulated R2 failure on timestamped write")

    s3_client.put_object = failing_put  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="simulated R2 failure"):
        put_snapshot_bytes(
            "varna",
            b'{"city": "varna"}',
            client=s3_client,
            bucket=BUCKET,
            now=datetime(2026, 5, 6, 13, 0, 0, tzinfo=timezone.utc),
        )

    s3_client.put_object = real_put  # type: ignore[method-assign]
    latest = s3_client.get_object(Bucket=BUCKET, Key="snapshots/varna/latest.json")
    assert json.loads(latest["Body"].read()) == previous_payload
