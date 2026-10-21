-- TradeIndiaMarketplace operations database (PostgreSQL 16). Target-state schema.
-- Status: PLANNED. The running code uses an in-memory store (timp/store.py) that enforces
-- the same UNIQUE rules named below; this file is the production migration 0001.
-- Money: numeric(12,2) INR. Times: timestamptz UTC. IDs: text with type prefix.

BEGIN;

CREATE TYPE product_status AS ENUM ('DISCOVERED','UNDER_REVIEW','SUPPLIER_VERIFICATION','FINANCIAL_REVIEW',
  'OWNER_APPROVED','PRODUCT_ONBOARDING','COMPLIANCE_APPROVED','READY_FOR_TESTING','READY_TO_PUBLISH','LIVE',
  'PAUSED','RETIRED','REJECTED');
CREATE TYPE sales_channel AS ENUM ('shopify','amazon_in','flipkart','meesho');
CREATE TYPE approval_scope AS ENUM ('PRODUCT_OPPORTUNITY','SUPPLIER_TERMS','PRICE_CHANGE','CHANNEL_PUBLICATION',
  'PURCHASE_COMMITMENT','AD_BUDGET','EXCEPTIONAL_REFUND','EXPENSE','DESTRUCTIVE_CHANGE');
CREATE TYPE approval_status AS ENUM ('PENDING','GRANTED','DENIED','CONSUMED','SUPERSEDED');
CREATE TYPE verification_status AS ENUM ('UNVERIFIED','IN_PROGRESS','VERIFIED','FAILED','EXPIRED');
CREATE TYPE check_result AS ENUM ('PASS','FAIL','PENDING','NOT_APPLICABLE');
CREATE TYPE listing_status AS ENUM ('DRAFT','VALIDATED','AWAITING_MANUAL_UPLOAD','PUBLISHED','PAUSED','WITHDRAWN');
CREATE TYPE order_status AS ENUM ('IMPORTED','AWAITING_SUPPLIER','SUPPLIER_ACCEPTED','DISPATCHED','DELIVERED',
  'CANCELLED','NEEDS_ATTENTION','RETURN_REQUESTED','RETURNED','REFUNDED');
CREATE TYPE po_status AS ENUM ('SUBMITTED','ACCEPTED','REJECTED','DISPATCHED','CANCELLED','CLOSED');
CREATE TYPE severity AS ENUM ('LOW','MEDIUM','HIGH','CRITICAL');

CREATE TABLE evidence (
  id text PRIMARY KEY, kind text NOT NULL, reference text NOT NULL, summary text NOT NULL DEFAULT '',
  sha256 text, captured_at timestamptz NOT NULL, stored_object_key text   -- copy kept in object storage
);

CREATE TABLE product_candidate (
  id text PRIMARY KEY, name text NOT NULL, category text NOT NULL, intended_customer text NOT NULL,
  specifications jsonb NOT NULL, variants jsonb NOT NULL DEFAULT '[]',
  indicative_price_low numeric(12,2), indicative_price_high numeric(12,2),
  supplier_leads jsonb NOT NULL, risks jsonb NOT NULL, confidence text NOT NULL CHECK (confidence IN ('low','medium','high')),
  recommended_action text NOT NULL, branded boolean NOT NULL DEFAULT false, brand text,
  created_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE candidate_evidence (candidate_id text REFERENCES product_candidate, evidence_id text REFERENCES evidence,
  role text NOT NULL CHECK (role IN ('demand','competition','pricing','risk')), PRIMARY KEY (candidate_id, evidence_id));

CREATE TABLE product (
  id text PRIMARY KEY, candidate_id text NOT NULL REFERENCES product_candidate,
  name text NOT NULL, normalized_key text NOT NULL, category text NOT NULL,
  status product_status NOT NULL DEFAULT 'DISCOVERED', version int NOT NULL DEFAULT 1,
  branded boolean NOT NULL DEFAULT false, brand text, hsn_code text, gst_pct numeric(5,2),
  selected_supplier_id text, selected_quotation_id text, attributes jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT product_key UNIQUE (normalized_key)                       -- duplicate prevention
);
CREATE TABLE product_version (product_id text REFERENCES product, version int, snapshot jsonb NOT NULL,
  reason text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (product_id, version));
CREATE TABLE product_variant (id text PRIMARY KEY, product_id text NOT NULL REFERENCES product,
  sku text NOT NULL UNIQUE, option_values jsonb NOT NULL, barcode text);

CREATE TABLE supplier (
  id text PRIMARY KEY, legal_name text NOT NULL, kind text NOT NULL, gstin text,
  contact_ref text NOT NULL, supports_third_party_fulfillment boolean NOT NULL,
  verification_status verification_status NOT NULL DEFAULT 'UNVERIFIED',
  reliability_score numeric(5,2) NOT NULL DEFAULT 0, created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT supplier_gstin UNIQUE (gstin)
);
CREATE TABLE supplier_verification (
  id text PRIMARY KEY, supplier_id text NOT NULL REFERENCES supplier, checks jsonb NOT NULL,
  status verification_status NOT NULL, verified_by text NOT NULL, verified_at timestamptz NOT NULL,
  expires_at timestamptz
);
CREATE TABLE supplier_verification_evidence (verification_id text REFERENCES supplier_verification,
  check_name text, evidence_id text REFERENCES evidence, PRIMARY KEY (verification_id, check_name));
CREATE TABLE supplier_quotation (
  id text PRIMARY KEY, supplier_id text NOT NULL REFERENCES supplier, product_id text NOT NULL REFERENCES product,
  sku text NOT NULL, unit_cost_excl_gst numeric(12,2) NOT NULL, gst_pct numeric(5,2) NOT NULL,
  moq int NOT NULL, dispatch_sla_hours int NOT NULL, valid_until timestamptz NOT NULL,
  evidence_id text NOT NULL REFERENCES evidence, version int NOT NULL, supersedes_id text REFERENCES supplier_quotation,
  active boolean NOT NULL DEFAULT true,
  CONSTRAINT quotation_version UNIQUE (supplier_id, sku, version)
);
CREATE UNIQUE INDEX one_active_quotation ON supplier_quotation (supplier_id, sku) WHERE active;
CREATE TABLE supplier_agreement (
  id text PRIMARY KEY, supplier_id text NOT NULL REFERENCES supplier, quotation_id text NOT NULL REFERENCES supplier_quotation,
  product_id text NOT NULL REFERENCES product, version int NOT NULL, terms jsonb NOT NULL,
  approval_id text NOT NULL, signed_evidence_id text REFERENCES evidence, created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT agreement_version UNIQUE (supplier_id, product_id, version)
);
CREATE TABLE supplier_inventory_snapshot (
  id text PRIMARY KEY, supplier_id text NOT NULL REFERENCES supplier, sku text NOT NULL,
  available_qty int NOT NULL CHECK (available_qty >= 0), captured_at timestamptz NOT NULL, source text NOT NULL
);
CREATE INDEX inv_latest ON supplier_inventory_snapshot (supplier_id, sku, captured_at DESC);

CREATE TABLE fulfillment_arrangement (
  id text PRIMARY KEY, product_id text NOT NULL REFERENCES product, channel sales_channel NOT NULL,
  method text NOT NULL, checks jsonb NOT NULL, verified boolean NOT NULL, verified_by text NOT NULL,
  verified_at timestamptz NOT NULL
);

CREATE TABLE approval_request (
  id text PRIMARY KEY, scope approval_scope NOT NULL, subject_id text NOT NULL, subject_version int NOT NULL,
  channel sales_channel, amount_limit numeric(12,2), summary text NOT NULL,
  requested_by text NOT NULL, requested_at timestamptz NOT NULL,
  status approval_status NOT NULL DEFAULT 'PENDING', decided_by text, decided_at timestamptz, note text NOT NULL DEFAULT '',
  CHECK ((status IN ('PENDING')) = (decided_by IS NULL))
);
CREATE UNIQUE INDEX one_pending_approval ON approval_request (scope, subject_id, subject_version, channel)
  NULLS NOT DISTINCT WHERE status = 'PENDING';
-- product_approval is the decided subset for product scopes
CREATE VIEW product_approval AS SELECT * FROM approval_request
  WHERE scope IN ('PRODUCT_OPPORTUNITY','CHANNEL_PUBLICATION','PRICE_CHANGE') AND status <> 'PENDING';

CREATE TABLE compliance_check (
  id text PRIMARY KEY, product_id text NOT NULL REFERENCES product, product_version int NOT NULL,
  check_type text NOT NULL, result check_result NOT NULL, policy_version text NOT NULL,
  checked_by text NOT NULL, checked_at timestamptz NOT NULL, notes text NOT NULL DEFAULT ''
);
CREATE TABLE compliance_evidence (check_id text REFERENCES compliance_check, evidence_id text REFERENCES evidence,
  PRIMARY KEY (check_id, evidence_id));

CREATE TABLE pricing_rule (
  id text PRIMARY KEY, product_id text NOT NULL REFERENCES product, channel sales_channel NOT NULL,
  floor_price_incl_gst numeric(12,2) NOT NULL, ceiling_price_incl_gst numeric(12,2) NOT NULL,
  max_auto_change_pct numeric(5,2) NOT NULL, approval_id text NOT NULL REFERENCES approval_request,
  active boolean NOT NULL DEFAULT true, CHECK (floor_price_incl_gst <= ceiling_price_incl_gst)
);
CREATE TABLE cost_estimate (
  id text PRIMARY KEY, product_id text NOT NULL REFERENCES product, product_version int NOT NULL,
  channel sales_channel NOT NULL, price_incl_gst numeric(12,2) NOT NULL, inputs jsonb NOT NULL,
  input_basis jsonb NOT NULL,             -- field -> quoted | actual | estimated
  fee_schedule jsonb NOT NULL, result jsonb NOT NULL, status text NOT NULL,
  created_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE channel_listing (
  id text PRIMARY KEY, product_id text NOT NULL REFERENCES product, channel sales_channel NOT NULL,
  sku text NOT NULL, price_incl_gst numeric(12,2) NOT NULL, attributes jsonb NOT NULL,
  status listing_status NOT NULL DEFAULT 'DRAFT', product_version int NOT NULL, external_id text,
  published_at timestamptz, validation_errors jsonb NOT NULL DEFAULT '[]',
  CONSTRAINT listing_channel_sku UNIQUE (channel, sku)
);

CREATE TABLE customer_order (
  id text PRIMARY KEY, channel sales_channel NOT NULL, external_order_id text NOT NULL,
  status order_status NOT NULL, ship_to_ref text NOT NULL,   -- token; address stays with channel / vault
  ship_to_pincode char(6) NOT NULL, created_at timestamptz NOT NULL, dispatch_by timestamptz,
  CONSTRAINT order_channel_ext UNIQUE (channel, external_order_id)
);
CREATE TABLE order_line (order_id text REFERENCES customer_order, line_no int, sku text NOT NULL,
  qty int NOT NULL CHECK (qty > 0), unit_price_incl_gst numeric(12,2) NOT NULL, PRIMARY KEY (order_id, line_no));
CREATE TABLE idempotency_key (key text PRIMARY KEY, resource_type text NOT NULL, resource_id text NOT NULL,
  first_seen_at timestamptz NOT NULL DEFAULT now());

CREATE TABLE supplier_purchase_order (
  id text PRIMARY KEY, order_id text NOT NULL REFERENCES customer_order, supplier_id text NOT NULL REFERENCES supplier,
  quotation_id text NOT NULL REFERENCES supplier_quotation, amount_incl_gst numeric(12,2) NOT NULL,
  idempotency_key text NOT NULL, status po_status NOT NULL, submitted_at timestamptz NOT NULL,
  approval_id text REFERENCES approval_request, confirmed_dispatch_by timestamptz, rejection_reason text
);
CREATE UNIQUE INDEX po_idem ON supplier_purchase_order (idempotency_key) WHERE status <> 'REJECTED';
CREATE TABLE shipment (
  id text PRIMARY KEY, order_id text NOT NULL REFERENCES customer_order, po_id text NOT NULL REFERENCES supplier_purchase_order,
  carrier text NOT NULL, tracking_number text NOT NULL, status text NOT NULL,
  dispatched_at timestamptz NOT NULL, delivered_at timestamptz,
  CONSTRAINT tracking UNIQUE (carrier, tracking_number)
);
CREATE TABLE shipment_event (shipment_id text REFERENCES shipment, evidence_id text REFERENCES evidence,
  event_code text NOT NULL, PRIMARY KEY (shipment_id, evidence_id));

CREATE TABLE return_request (
  id text PRIMARY KEY, order_id text NOT NULL REFERENCES customer_order, reason text NOT NULL, status text NOT NULL,
  requested_at timestamptz NOT NULL, received_evidence_id text REFERENCES evidence,
  supplier_credit_expected numeric(12,2) NOT NULL DEFAULT 0, supplier_credit_received numeric(12,2) NOT NULL DEFAULT 0,
  CONSTRAINT return_order UNIQUE (order_id)
);
CREATE TABLE refund (
  id text PRIMARY KEY, order_id text NOT NULL REFERENCES customer_order, return_id text REFERENCES return_request,
  amount numeric(12,2) NOT NULL CHECK (amount > 0), executed_by text NOT NULL,
  approval_id text REFERENCES approval_request, created_at timestamptz NOT NULL,
  CONSTRAINT refund_once UNIQUE (return_id)
);
CREATE TABLE customer_support_case (
  id text PRIMARY KEY, order_id text REFERENCES customer_order, category text NOT NULL, severity severity NOT NULL,
  status text NOT NULL, opened_at timestamptz NOT NULL, due_by timestamptz NOT NULL, history jsonb NOT NULL DEFAULT '[]'
);
CREATE TABLE marketing_campaign (
  id text PRIMARY KEY, channel sales_channel NOT NULL, name text NOT NULL, budget_inr numeric(12,2) NOT NULL,
  spent_inr numeric(12,2) NOT NULL DEFAULT 0, status text NOT NULL, approval_id text REFERENCES approval_request
);
CREATE TABLE expense (
  id text PRIMARY KEY, category text NOT NULL, amount_inr numeric(12,2) NOT NULL, description text NOT NULL,
  approval_id text REFERENCES approval_request, incurred_at timestamptz NOT NULL
);
CREATE TABLE marketplace_settlement (
  id text PRIMARY KEY, channel sales_channel NOT NULL, period text NOT NULL, lines jsonb NOT NULL,
  status text NOT NULL, variances jsonb NOT NULL, reconciled_at timestamptz NOT NULL,
  CONSTRAINT settlement_period UNIQUE (channel, period)
);

CREATE TABLE agent_task (
  id text PRIMARY KEY, agent text NOT NULL, kind text NOT NULL, subject_id text NOT NULL, status text NOT NULL,
  depends_on jsonb NOT NULL DEFAULT '[]', created_at timestamptz NOT NULL, due_by timestamptz, result text NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX one_open_task ON agent_task (kind, subject_id) WHERE status IN ('OPEN','IN_PROGRESS','BLOCKED');

CREATE TABLE audit_event (
  seq bigserial PRIMARY KEY, at timestamptz NOT NULL, actor_id text NOT NULL, action text NOT NULL,
  subject text NOT NULL, details jsonb NOT NULL, prev_hash char(64) NOT NULL, hash char(64) NOT NULL UNIQUE
);
-- append-only: the application role gets INSERT/SELECT only
REVOKE UPDATE, DELETE, TRUNCATE ON audit_event FROM PUBLIC;

CREATE TABLE test_run (
  id text PRIMARY KEY, product_id text REFERENCES product, product_version int, suite text NOT NULL,
  results jsonb NOT NULL, created_at timestamptz NOT NULL
);
CREATE TABLE notification (
  id text PRIMARY KEY, severity severity NOT NULL, kind text NOT NULL, message text NOT NULL,
  subject_id text NOT NULL, created_at timestamptz NOT NULL, acknowledged_by text, acknowledged_at timestamptz
);
CREATE TABLE emergency_stop (switch text PRIMARY KEY CHECK (switch IN ('PUBLISHING','SUPPLIER_ORDERS','CAMPAIGNS')),
  engaged boolean NOT NULL, changed_by text NOT NULL, changed_at timestamptz NOT NULL, reason text NOT NULL);
CREATE TABLE job_dead_letter (id bigserial PRIMARY KEY, op text NOT NULL, subject text NOT NULL, payload jsonb NOT NULL,
  error text NOT NULL, attempts int NOT NULL, created_at timestamptz NOT NULL, resolved_at timestamptz);

COMMIT;
