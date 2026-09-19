"""Cloudflare R2 client (S3-compatible) and snapshot upload helper."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import boto3

from yasli_scraper.models import Snapshot


def _endpoint_url(account_id: str) -> str:
    return f"https://{account_id}.r2.cloudflarestorage.com"


def make_client(env: dict[str, str] | None = None) -> Any:
    """Build a boto3 S3 client pointed at the configured R2 account.

    Reads credentials from the process environment (or the supplied dict, for
    tests). The four required env vars MUST be present and non-empty — the CLI
    validates this before calling.
    """
    source = os.environ if env is None else env
    return boto3.client(
        "s3",
        endpoint_url=_endpoint_url(source["R2_ACCOUNT_ID"]),
        aws_access_key_id=source["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=source["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def _utc_iso_filename(now: datetime | None = None) -> str:
    moment = now if now is not None else datetime.now(timezone.utc)
    # Drop microseconds and append Z; safe for object keys.
    return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def snapshot_keys(city: str, now: datetime | None = None) -> tuple[str, str]:
    """Return ``(timestamped_key, latest_key)`` for `city` at the given instant.

    The sole definition of the object-key layout, split out so a caller can name
    both keys *before* the writes begin — `promote` needs them to report which
    objects a failed upload may have touched, which is exactly when nothing is
    returned.
    """
    return (
        f"snapshots/{city}/{_utc_iso_filename(now)}.json",
        f"snapshots/{city}/latest.json",
    )


def put_snapshot_bytes(
    city: str,
    body: bytes,
    *,
    client: Any | None = None,
    bucket: str | None = None,
    now: datetime | None = None,
) -> tuple[str, str]:
    """Write `body` to R2 as both a timestamped object and `latest.json`.

    The body is written **unmodified** — nothing here parses, reformats or
    re-serialises it, so the bytes a caller validated are the bytes that land.
    Validation is entirely the caller's responsibility.

    Order is load-bearing: the timestamped object is uploaded first so that a
    failure of the second write leaves `latest.json` pointing at the previous
    good snapshot (audit trail preserved).

    Returns ``(timestamped_key, latest_key)``.
    """
    s3 = client if client is not None else make_client()
    bucket_name = bucket if bucket is not None else os.environ["R2_BUCKET"]

    timestamped_key, latest_key = snapshot_keys(city, now)

    # First write: timestamped audit-trail object.
    s3.put_object(
        Bucket=bucket_name,
        Key=timestamped_key,
        Body=body,
        ContentType="application/json",
    )

    # Second write: mutable pointer the backend reads. Only happens if the
    # first succeeded.
    s3.put_object(
        Bucket=bucket_name,
        Key=latest_key,
        Body=body,
        ContentType="application/json",
    )

    return timestamped_key, latest_key


def put_snapshot(
    city: str,
    payload: Snapshot,
    *,
    client: Any | None = None,
    bucket: str | None = None,
    now: datetime | None = None,
) -> tuple[str, str]:
    """Write the snapshot to R2 as both a timestamped object and `latest.json`.

    Serialises `payload` and delegates the ordered two-phase write to
    :func:`put_snapshot_bytes`.

    Returns ``(timestamped_key, latest_key)``.
    """
    return put_snapshot_bytes(
        city,
        payload.model_dump_json(indent=2).encode("utf-8"),
        client=client,
        bucket=bucket,
        now=now,
    )
