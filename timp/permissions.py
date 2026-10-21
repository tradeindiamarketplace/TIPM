"""Agent responsibility and permission matrix (docs/03). Least privilege: agents propose, the owner decides."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    ORCHESTRATOR = "agent_a_orchestrator"
    PRODUCT_ANALYST = "agent_b_product_discovery"
    SUPPLIER_SOURCING = "agent_c_supplier_sourcing"
    FINANCE = "agent_d_finance"
    ARCHITECT = "agent_e_architect"
    DEVELOPER = "agent_f_developer"
    DESIGN = "agent_g_design"
    MARKETING = "agent_h_marketing"
    PRICING = "agent_i_pricing"
    FULFILLMENT = "agent_j_fulfillment"
    QA = "agent_k_qa"
    SUPPORT = "agent_l_support"
    COMPLIANCE = "agent_m_compliance"
    SYSTEM = "system"            # webhooks and schedulers


class Perm(StrEnum):
    # owner-only
    DECIDE_APPROVAL = "decide_approval"
    SET_THRESHOLDS = "set_thresholds"
    RELEASE_EMERGENCY_STOP = "release_emergency_stop"
    DESTRUCTIVE_CHANGE = "destructive_change"
    CONFIRM_MANUAL_UPLOAD = "confirm_manual_upload"
    # proposals and records
    PROPOSE_PRODUCT = "propose_product"
    ADVANCE_LIFECYCLE = "advance_lifecycle"
    REQUEST_APPROVAL = "request_approval"
    RECORD_SUPPLIER = "record_supplier"
    RECORD_VERIFICATION = "record_verification"
    RECORD_QUOTATION = "record_quotation"
    RECORD_AGREEMENT = "record_agreement"
    RECORD_INVENTORY = "record_inventory"
    RECORD_COMPLIANCE = "record_compliance"
    RECORD_FULFILLMENT_ARRANGEMENT = "record_fulfillment_arrangement"
    CALCULATE_ECONOMICS = "calculate_economics"
    EDIT_CONTENT = "edit_content"
    RECORD_TEST_RUN = "record_test_run"
    # operational side effects (only within approvals)
    PUBLISH_LISTING = "publish_listing"
    PAUSE_LISTING = "pause_listing"
    APPLY_PRICING_RULE = "apply_pricing_rule"
    IMPORT_ORDER = "import_order"
    SUBMIT_SUPPLIER_PO = "submit_supplier_po"
    RECORD_SHIPMENT_EVENT = "record_shipment_event"
    CANCEL_ORDER = "cancel_order"
    MANAGE_RETURN = "manage_return"
    ISSUE_REFUND = "issue_refund"
    VIEW_ORDER = "view_order"
    MANAGE_SUPPORT_CASE = "manage_support_case"
    RECONCILE_SETTLEMENT = "reconcile_settlement"
    PROPOSE_CAMPAIGN = "propose_campaign"
    RUN_CAMPAIGN = "run_campaign"
    ENGAGE_EMERGENCY_STOP = "engage_emergency_stop"
    MANAGE_TASKS = "manage_tasks"


OWNER_ONLY = {Perm.DECIDE_APPROVAL, Perm.SET_THRESHOLDS, Perm.RELEASE_EMERGENCY_STOP,
              Perm.DESTRUCTIVE_CHANGE, Perm.CONFIRM_MANUAL_UPLOAD}

MATRIX: dict[Role, set[Perm]] = {
    Role.OWNER: set(Perm),
    Role.ORCHESTRATOR: {Perm.ADVANCE_LIFECYCLE, Perm.REQUEST_APPROVAL, Perm.PUBLISH_LISTING, Perm.PAUSE_LISTING,
                        Perm.ENGAGE_EMERGENCY_STOP, Perm.MANAGE_TASKS, Perm.VIEW_ORDER},
    Role.PRODUCT_ANALYST: {Perm.PROPOSE_PRODUCT, Perm.REQUEST_APPROVAL},
    Role.SUPPLIER_SOURCING: {Perm.RECORD_SUPPLIER, Perm.RECORD_VERIFICATION, Perm.RECORD_QUOTATION,
                             Perm.RECORD_AGREEMENT, Perm.RECORD_INVENTORY, Perm.REQUEST_APPROVAL},
    Role.FINANCE: {Perm.CALCULATE_ECONOMICS, Perm.RECONCILE_SETTLEMENT, Perm.REQUEST_APPROVAL},
    Role.ARCHITECT: set(),
    Role.DEVELOPER: {Perm.RECORD_TEST_RUN},
    Role.DESIGN: {Perm.EDIT_CONTENT},
    Role.MARKETING: {Perm.EDIT_CONTENT, Perm.PROPOSE_CAMPAIGN, Perm.REQUEST_APPROVAL},
    Role.PRICING: {Perm.CALCULATE_ECONOMICS, Perm.APPLY_PRICING_RULE, Perm.REQUEST_APPROVAL},
    Role.FULFILLMENT: {Perm.SUBMIT_SUPPLIER_PO, Perm.RECORD_SHIPMENT_EVENT, Perm.RECORD_INVENTORY,
                       Perm.RECORD_FULFILLMENT_ARRANGEMENT, Perm.CANCEL_ORDER, Perm.MANAGE_RETURN,
                       Perm.VIEW_ORDER, Perm.REQUEST_APPROVAL},
    Role.QA: {Perm.RECORD_TEST_RUN},
    Role.SUPPORT: {Perm.VIEW_ORDER, Perm.MANAGE_SUPPORT_CASE, Perm.MANAGE_RETURN, Perm.REQUEST_APPROVAL},
    Role.COMPLIANCE: {Perm.RECORD_COMPLIANCE, Perm.RECORD_VERIFICATION, Perm.RECORD_FULFILLMENT_ARRANGEMENT,
                      Perm.PAUSE_LISTING, Perm.ENGAGE_EMERGENCY_STOP},
    Role.SYSTEM: {Perm.IMPORT_ORDER, Perm.RECORD_SHIPMENT_EVENT, Perm.RECORD_INVENTORY, Perm.SUBMIT_SUPPLIER_PO,
                  Perm.ISSUE_REFUND, Perm.RUN_CAMPAIGN, Perm.PAUSE_LISTING, Perm.MANAGE_RETURN},
}

assert all(not (perms & OWNER_ONLY) for r, perms in MATRIX.items() if r is not Role.OWNER)


class PermissionDenied(Exception):
    pass


@dataclass(frozen=True)
class Actor:
    id: str
    role: Role

    @property
    def is_owner(self) -> bool:
        return self.role is Role.OWNER


def require(actor: Actor, perm: Perm) -> None:
    if perm not in MATRIX.get(actor.role, set()):
        raise PermissionDenied(f"{actor.id} ({actor.role}) lacks {perm}")
