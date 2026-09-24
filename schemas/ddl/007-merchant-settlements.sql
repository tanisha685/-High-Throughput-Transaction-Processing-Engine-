-- ============================================================================
-- Table: merchant_settlements
-- Description: Batch merchant settlement records for daily payout lifecycles.
-- ============================================================================

CREATE TYPE settlement_status_enum AS ENUM (
    'PENDING',
    'PROCESSING',
    'SETTLED',
    'FAILED',
    'DISPUTED'
);

CREATE TABLE IF NOT EXISTS merchant_settlements (
    settlement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id VARCHAR(64) NOT NULL,
    merchant_id UUID NOT NULL,
    gross_amount NUMERIC(18, 4) NOT NULL CHECK (gross_amount > 0),
    net_amount NUMERIC(18, 4) NOT NULL CHECK (net_amount > 0),
    mdr_fee NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    gst_fee NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    transaction_count INTEGER NOT NULL CHECK (transaction_count > 0),
    status settlement_status_enum NOT NULL DEFAULT 'PENDING',
    bank_reference_id VARCHAR(100),
    failure_reason VARCHAR(255),
    settlement_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_settlements_batch_id ON merchant_settlements (batch_id);
CREATE INDEX idx_settlements_merchant_date ON merchant_settlements (merchant_id, settlement_date);
CREATE INDEX idx_settlements_status ON merchant_settlements (status);
