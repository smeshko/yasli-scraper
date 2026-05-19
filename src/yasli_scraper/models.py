"""Pydantic models defining the v2 snapshot contract.

Construction validates implicitly: anything that doesn't fit the contract
raises ``pydantic.ValidationError`` before the snapshot ever reaches R2.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    field_serializer,
    model_validator,
)
from pydantic.networks import UrlConstraints

HttpsUrl = Annotated[HttpUrl, UrlConstraints(allowed_schemes=["https"])]
DistrictCode = Literal["01", "02", "03", "04", "05"]
Kind = Literal["nursery", "kindergarten", "preschool"]


class AddressEntry(BaseModel):
    """One street/number row attached to an institution.

    Both fields are preserved verbatim from the source — the scraper does not
    canonicalise. Normalisation is the backend's job during ingest.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    street: str = Field(min_length=1)
    number: str = Field(min_length=1)


class Institution(BaseModel):
    """One municipal institution (nursery / kindergarten / preschool)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    external_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    kind: Kind
    source_url: HttpsUrl
    address_entries: list[AddressEntry]
    address: str | None = None
    district_code: DistrictCode | None = None
    has_infant_group: bool

    @field_validator("address")
    @classmethod
    def _address_non_empty(cls, value: str | None) -> str | None:
        if value == "":
            raise ValueError("address must be non-empty or null")
        return value

    @model_validator(mode="after")
    def _nursery_requires_district(self) -> Self:
        if self.kind == "nursery" and self.district_code is None:
            raise ValueError("nursery institutions require district_code")
        return self


class Snapshot(BaseModel):
    """The top-level v2 snapshot envelope written to R2."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[2]
    scraped_at: AwareDatetime
    city: str = Field(min_length=1)
    institutions: list[Institution] = Field(min_length=1)

    @field_serializer("scraped_at")
    def _serialise_scraped_at(self, value: datetime) -> str:
        return (
            value.astimezone(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
