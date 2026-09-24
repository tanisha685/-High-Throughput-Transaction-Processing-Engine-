-- ============================================================================
-- Table: transactions (Partitioned by Range on created_at)
-- Description: Core immutable transaction record with idempotency, saga trace,
-- and monthly range partitioning.
-- ============================================================================

CREATE TYPE transaction_type_enum AS ENUM (
    'P2P',
    'MERCHANT_PAYMENT',
    'SETTLEMENT',
    'REVERSAL',
    'FEE'
);

CREATE TYPE transaction_status_enum AS ENUM (
    'INITIATED',
    'PROCESSING',
    'COMPLETED',
    'FAILED',
    'REVERSED'
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id UUID NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    transaction_type transaction_type_enum NOT NULL,
    source_account_id UUID,
    destination_account_id UUID,
    amount NUMERIC(18, 4) NOT NULL CHECK (amount > 0),
    fee_amount NUMERIC(18, 4) NOT NULL DEFAULT 0.0000 CHECK (fee_amount >= 0),
    currency CHAR(3) NOT NULL DEFAULT 'INR',
    status transaction_status_enum NOT NULL DEFAULT 'INITIATED',
    saga_id UUID NOT NULL,
    failure_reason VARCHAR(500),
    risk_score INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    
    PRIMARY KEY (transaction_id, created_at)
) PARTITION BY RANGE (created_at);

-- Partition definitions (Monthly Partitioning Strategy)
CREATE TABLE IF NOT EXISTS transactions_2026_09 PARTITION OF transactions
    FOR VALUES FROM ('2026-09-01 00:00:00+00') TO ('2026-10-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS transactions_2026_10 PARTITION OF transactions
    FOR VALUES FROM ('2026-10-01 00:00:00+00') TO ('2026-11-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS transactions_2026_11 PARTITION OF transactions
    FOR VALUES FROM ('2026-11-01 00:00:00+00') TO ('2026-12-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS transactions_default PARTITION OF transactions DEFAULT;

-- Composite & B-Tree Indexes
CREATE INDEX idx_transactions_idempotency ON transactions (idempotency_key);
CREATE INDEX idx_transactions_source_acc ON transactions (source_account_id, created_at DESC);
CREATE INDEX idx_transactions_dest_acc ON transactions (destination_account_id, created_at DESC);
CREATE INDEX idx_transactions_saga_id ON transactions (saga_id);
CREATE INDEX idx_transactions_status_created ON transactions (status, created_at);
CREATE INDEX idx_transactions_metadata_gin ON transactions USING GIN (metadata);
