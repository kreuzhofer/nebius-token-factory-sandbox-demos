"""Small version-1 interchange contract; unknown money is never zero."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

Money = Annotated[str, Field(pattern=r"^-?\d{1,12}(\.\d{1,4})?$")]


class Evidence(BaseModel):
    field: str
    page: int | None = Field(default=None, ge=1)
    text: str | None = None
    reason: str | None = None


class Page(BaseModel):
    number: int = Field(ge=1)
    text: str
    blocks: list[str] = Field(default_factory=list)


class Detail(BaseModel):
    description: str
    amount: Money | None = None


class AmountComponent(BaseModel):
    role: Literal[
        "item",
        "subtotal",
        "discount",
        "tax_added",
        "fee",
        "total",
        "tax_included",
        "tender",
        "change",
        "carry_forward",
        "conversion",
    ]
    amount: Money
    page: int = Field(ge=1)
    text: str


class Arithmetic(BaseModel):
    basis: Literal["items", "subtotal", "none"]
    complete: bool
    components: list[AmountComponent] = Field(default_factory=list)


class ReceiptValues(BaseModel):
    merchant: str | None = None
    date_text: str | None = None
    transaction_date: str | None = None
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] | None = None
    transaction_type: Literal["purchase", "refund"] | None = None
    printed_total: str | None = None
    total: Money | None = None
    line_items: list[Detail] = Field(default_factory=list)
    taxes: list[Detail] = Field(default_factory=list)
    discounts: list[Detail] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    monetary_issues: list[str] = Field(
        default_factory=list,
        description="Unresolved monetary contradictions or ambiguity that prevents inclusion.",
    )

    @field_validator("transaction_date")
    @classmethod
    def iso_date(cls, value):
        if value is not None and date.fromisoformat(value).isoformat() != value:
            raise ValueError("Use YYYY-MM-DD or null")
        return value


class ExtractedDocument(BaseModel):
    pages: list[Page] = Field(min_length=1)


class ReceiptInterpretation(ReceiptValues):
    arithmetic: Arithmetic | None = None


class ReceiptFields(ReceiptValues):
    pages: list[Page] = Field(default_factory=list)


class Receipt(ReceiptFields):
    schema_version: Literal["1"] = "1"
    receipt_id: str
    source: str
    credit: str = ""
    content_hash: str | None = None
    pixel_hash: str | None = None
    rendered_pages: list[str] = Field(default_factory=list)
    error: str | None = None
    arithmetic: Arithmetic | None = None


class DuplicateGroup(BaseModel):
    receipt_ids: list[str] = Field(min_length=2)
    confidence: Literal["confirmed", "suspected"]
    reason: str


class MonetaryFlag(BaseModel):
    receipt_id: str
    reason: str


class Decisions(BaseModel):
    duplicates: list[DuplicateGroup] = Field(default_factory=list)
    monetary_flags: list[MonetaryFlag] = Field(default_factory=list)


class Entry(BaseModel):
    receipt_id: str
    source: str
    outcome: Literal["included", "flagged", "duplicate", "error"]
    reasons: list[str] = Field(default_factory=list)
    signed_amount: Money | None = None
    currency: str | None = None
    duplicate_of: str | None = None


class Report(BaseModel):
    schema_version: Literal["1"] = "1"
    status: Literal["completed", "completed_with_flags", "failed"]
    entries: list[Entry]
    totals: dict[str, Money]
    receipts: list[Receipt]
    artifacts: dict[str, str] = Field(default_factory=dict)
    error: str | None = None
