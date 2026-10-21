"""Shared data model. Mirrors db/schema.sql; money is Decimal INR, times are UTC."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any


class ProductStatus(StrEnum):
    DISCOVERED = "DISCOVERED"
    UNDER_REVIEW = "UNDER_REVIEW"
    SUPPLIER_VERIFICATION = "SUPPLIER_VERIFICATION"
    FINANCIAL_REVIEW = "FINANCIAL_REVIEW"
    OWNER_APPROVED = "OWNER_APPROVED"
    PRODUCT_ONBOARDING = "PRODUCT_ONBOARDING"
    COMPLIANCE_APPROVED = "COMPLIANCE_APPROVED"
    READY_FOR_TESTING = "READY_FOR_TESTING"
    READY_TO_PUBLISH = "READY_TO_PUBLISH"
    LIVE = "LIVE"
    PAUSED = "PAUSED"
    RETIRED = "RETIRED"
    REJECTED = "REJECTED"


class Channel(StrEnum):
    SHOPIFY = "shopify"          # TradeIndiaMarketplace.com
    AMAZON_IN = "amazon_in"
    FLIPKART = "flipkart"
    MEESHO = "meesho"


class IntegrationStatus(StrEnum):
    LIVE_TESTED = "live_tested"  # exercised against the real environment
    PARTIAL = "partial"          # code exists, not yet tested against the real environment
    SIMULATED = "simulated"      # in-memory stand-in for tests only
    MANUAL = "manual"            # export file + human upload
    UNAVAILABLE = "unavailable"  # no credentials / approval yet


class VerificationStatus(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    IN_PROGRESS = "IN_PROGRESS"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class ApprovalScope(StrEnum):
    PRODUCT_OPPORTUNITY = "PRODUCT_OPPORTUNITY"
    SUPPLIER_TERMS = "SUPPLIER_TERMS"
    PRICE_CHANGE = "PRICE_CHANGE"
    CHANNEL_PUBLICATION = "CHANNEL_PUBLICATION"
    PURCHASE_COMMITMENT = "PURCHASE_COMMITMENT"
    AD_BUDGET = "AD_BUDGET"
    EXCEPTIONAL_REFUND = "EXCEPTIONAL_REFUND"
    EXPENSE = "EXPENSE"
    DESTRUCTIVE_CHANGE = "DESTRUCTIVE_CHANGE"


# Scopes that authorise exactly one action and are then consumed.
SINGLE_USE_SCOPES = {
    ApprovalScope.PURCHASE_COMMITMENT,
    ApprovalScope.EXCEPTIONAL_REFUND,
    ApprovalScope.EXPENSE,
    ApprovalScope.DESTRUCTIVE_CHANGE,
}


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    GRANTED = "GRANTED"
    DENIED = "DENIED"
    CONSUMED = "CONSUMED"
    SUPERSEDED = "SUPERSEDED"


class ListingStatus(StrEnum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    AWAITING_MANUAL_UPLOAD = "AWAITING_MANUAL_UPLOAD"
    PUBLISHED = "PUBLISHED"
    PAUSED = "PAUSED"
    WITHDRAWN = "WITHDRAWN"


class OrderStatus(StrEnum):
    IMPORTED = "IMPORTED"
    AWAITING_SUPPLIER = "AWAITING_SUPPLIER"
    SUPPLIER_ACCEPTED = "SUPPLIER_ACCEPTED"
    DISPATCHED = "DISPATCHED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"
    RETURN_REQUESTED = "RETURN_REQUESTED"
    RETURNED = "RETURNED"
    REFUNDED = "REFUNDED"


class POStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    DISPATCHED = "DISPATCHED"
    CANCELLED = "CANCELLED"
    CLOSED = "CLOSED"


class ShipmentStatus(StrEnum):
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    EXCEPTION = "EXCEPTION"
    RTO = "RTO"


class ReturnStatus(StrEnum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RECEIVED = "RECEIVED"
    REFUNDED = "REFUNDED"


class CheckResult(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    PENDING = "PENDING"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class StopSwitch(StrEnum):
    PUBLISHING = "PUBLISHING"
    SUPPLIER_ORDERS = "SUPPLIER_ORDERS"
    CAMPAIGNS = "CAMPAIGNS"


@dataclass
class Evidence:
    kind: str                    # e.g. "url", "document", "carrier_api", "quotation_pdf"
    reference: str               # URL, file id or API event id
    captured_at: datetime
    summary: str = ""


@dataclass
class ProductCandidate:
    id: str
    name: str
    category: str
    intended_customer: str
    specifications: dict[str, Any]
    variants: list[str]
    demand_evidence: list[Evidence]
    competition_evidence: list[Evidence]
    indicative_price_low: Decimal | None
    indicative_price_high: Decimal | None
    supplier_leads: list[str]
    risks: list[str]
    confidence: str              # "low" | "medium" | "high", with reasons in risks/evidence
    recommended_action: str
    branded: bool = False
    brand: str | None = None
    created_by: str = ""
    created_at: datetime | None = None


@dataclass
class Product:
    id: str
    candidate_id: str
    name: str
    normalized_key: str
    category: str
    status: ProductStatus
    version: int = 1
    branded: bool = False
    brand: str | None = None
    hsn_code: str | None = None
    gst_pct: Decimal | None = None
    selected_supplier_id: str | None = None
    selected_quotation_id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class ProductVariant:
    id: str
    product_id: str
    sku: str
    option_values: dict[str, str]
    barcode: str | None = None


@dataclass
class Supplier:
    id: str
    legal_name: str
    kind: str                    # MANUFACTURER | WHOLESALER | AUTHORISED_DISTRIBUTOR | IMPORTER
    gstin: str | None
    contact_ref: str             # pointer to the contact record, not raw PII in logs
    supports_third_party_fulfillment: bool
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    reliability_score: Decimal = Decimal("0")
    created_at: datetime | None = None


@dataclass
class SupplierVerification:
    id: str
    supplier_id: str
    checks: dict[str, CheckResult]
    evidence: dict[str, Evidence]
    status: VerificationStatus
    verified_by: str
    verified_at: datetime
    expires_at: datetime | None = None


@dataclass
class SupplierQuotation:
    id: str
    supplier_id: str
    product_id: str
    sku: str
    unit_cost_excl_gst: Decimal
    gst_pct: Decimal
    moq: int
    dispatch_sla_hours: int
    valid_until: datetime
    evidence: Evidence
    version: int = 1
    supersedes_id: str | None = None
    active: bool = True


@dataclass
class SupplierAgreement:
    id: str
    supplier_id: str
    quotation_id: str
    product_id: str
    version: int
    terms: dict[str, Any]        # payment terms, return handling, packaging, invoice rules
    approval_id: str
    signed_evidence: Evidence | None
    created_at: datetime


@dataclass
class SupplierInventorySnapshot:
    id: str
    supplier_id: str
    sku: str
    available_qty: int
    captured_at: datetime
    source: str                  # "supplier_api" | "supplier_feed_csv" | "manual_call"


@dataclass
class FulfillmentArrangement:
    id: str
    product_id: str
    channel: Channel
    method: str                  # e.g. "supplier_direct_self_ship", "marketplace_fulfilment"
    checks: dict[str, bool]
    evidence: list[Evidence]
    verified: bool
    verified_by: str
    verified_at: datetime


@dataclass
class ChannelListing:
    id: str
    product_id: str
    channel: Channel
    sku: str
    price_incl_gst: Decimal
    attributes: dict[str, Any]
    status: ListingStatus = ListingStatus.DRAFT
    product_version: int = 1
    external_id: str | None = None
    published_at: datetime | None = None
    validation_errors: list[str] = field(default_factory=list)


@dataclass
class ComplianceCheck:
    id: str
    product_id: str
    product_version: int
    check_type: str
    result: CheckResult
    evidence: list[Evidence]
    policy_version: str          # which rule text / circular / policy page and its date
    checked_by: str
    checked_at: datetime
    notes: str = ""


@dataclass
class ApprovalRequest:
    id: str
    scope: ApprovalScope
    subject_id: str
    subject_version: int
    summary: str
    requested_by: str
    requested_at: datetime
    channel: Channel | None = None
    amount_limit: Decimal | None = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    decided_by: str | None = None
    decided_at: datetime | None = None
    note: str = ""


# A decided ApprovalRequest is the ProductApproval record for product scopes.
ProductApproval = ApprovalRequest


@dataclass
class PricingRule:
    id: str
    product_id: str
    channel: Channel
    floor_price_incl_gst: Decimal
    ceiling_price_incl_gst: Decimal
    max_auto_change_pct: Decimal
    approval_id: str
    active: bool = True


@dataclass
class CostEstimate:
    id: str
    product_id: str
    product_version: int
    channel: Channel
    price_incl_gst: Decimal
    result: Any                  # economics.EconomicsReport
    created_by: str
    created_at: datetime


@dataclass
class OrderLine:
    sku: str
    qty: int
    unit_price_incl_gst: Decimal


@dataclass
class CustomerOrder:
    id: str
    channel: Channel
    external_order_id: str
    lines: list[OrderLine]
    status: OrderStatus
    ship_to_ref: str             # token for the address held by the channel; never raw address in logs
    ship_to_pincode: str
    created_at: datetime
    dispatch_by: datetime | None = None   # only ever a supplier-confirmed time
    notes: list[str] = field(default_factory=list)


@dataclass
class SupplierPurchaseOrder:
    id: str
    order_id: str
    supplier_id: str
    quotation_id: str
    lines: list[OrderLine]
    amount_incl_gst: Decimal
    idempotency_key: str
    status: POStatus
    submitted_at: datetime
    approval_id: str | None = None
    confirmed_dispatch_by: datetime | None = None
    rejection_reason: str | None = None


@dataclass
class Shipment:
    id: str
    order_id: str
    po_id: str
    carrier: str
    tracking_number: str
    status: ShipmentStatus
    events: list[Evidence]
    dispatched_at: datetime
    delivered_at: datetime | None = None


@dataclass
class ReturnRequest:
    id: str
    order_id: str
    reason: str
    status: ReturnStatus
    requested_at: datetime
    received_evidence: Evidence | None = None
    supplier_credit_expected: Decimal = Decimal("0")
    supplier_credit_received: Decimal = Decimal("0")


@dataclass
class Refund:
    id: str
    order_id: str
    return_id: str | None
    amount: Decimal
    executed_by: str             # "channel" when the marketplace executes it
    approval_id: str | None
    created_at: datetime


@dataclass
class CustomerSupportCase:
    id: str
    order_id: str | None
    category: str
    severity: Severity
    status: str
    opened_at: datetime
    due_by: datetime
    history: list[str] = field(default_factory=list)


@dataclass
class MarketingCampaign:
    id: str
    channel: Channel
    name: str
    budget_inr: Decimal
    status: str                  # PROPOSED | APPROVED | RUNNING | PAUSED | ENDED
    spent_inr: Decimal = Decimal("0")
    approval_id: str | None = None


@dataclass
class Expense:
    id: str
    category: str
    amount_inr: Decimal
    description: str
    approval_id: str | None
    incurred_at: datetime


@dataclass
class MarketplaceSettlement:
    id: str
    channel: Channel
    period: str
    lines: list[dict[str, Any]]
    status: str                  # MATCHED | VARIANCE
    variances: list[dict[str, Any]]
    reconciled_at: datetime


@dataclass
class AgentTask:
    id: str
    agent: str
    kind: str
    subject_id: str
    status: str                  # OPEN | IN_PROGRESS | BLOCKED | DONE | FAILED
    created_at: datetime
    depends_on: list[str] = field(default_factory=list)
    due_by: datetime | None = None
    result: str = ""


@dataclass
class AuditEvent:
    seq: int
    at: datetime
    actor_id: str
    action: str
    subject: str
    details: dict[str, Any]
    prev_hash: str
    hash: str


@dataclass
class TestRun:
    id: str
    product_id: str
    product_version: int
    suite: str
    results: list[tuple[str, bool, Severity]]
    created_at: datetime

    @property
    def critical_failures(self) -> list[str]:
        return [n for n, ok, sev in self.results if not ok and sev in (Severity.HIGH, Severity.CRITICAL)]


@dataclass
class Notification:
    id: str
    severity: Severity
    kind: str
    message: str
    subject_id: str
    created_at: datetime
