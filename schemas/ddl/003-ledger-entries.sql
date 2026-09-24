-- ============================================================================
-- Table: ledger_entries (Partitioned by Range on created_at)
-- Description: Immutable double-entry bookkeeping ledger. Every financial movement
-- creates at least one DEBIT and one CREDIT entry.
-- ============================================================================

CREATE TYPE entry_direction_enum AS ENUM (
    'DEBIT',
    'CREDIT'
);

CREATE TYPE ledger_entry_type_enum AS ENUM (
    'PAYMENT',
    'FEE',
    'REFUND',
    'SETTLEMENT_PAYOUT',
    'ADJUSTMENT'
);

CREATE TABLE IF NOT EXISTS ledger_entries (
    entry_id UUID NOT NULL,
    transaction_id UUID NOT NULL,
    account_id UUID NOT NULL,
    entry_type ledger_entry_type_enum NOT NULL,
    direction entry_direction_enum NOT NULL,
    amount NUMERIC(18, 4) NOT NULL CHECK (amount > 0),
    balance_after NUMERIC(18, 4) NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'INR',
    description VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (entry_id, created_at)
) PARTITION BY RANGE (created_at);

-- Partitions for Ledger Entries
CREATE TABLE IF NOT EXISTS ledger_entries_2026_09 PARTITION OF ledger_entries
    FOR VALUES FROM ('2026-09-01 00:00:00+00') TO ('2026-10-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS ledger_entries_2026_10 PARTITION OF ledger_entries
    FOR VALUES FROM ('2026-10-01 00:00:00+00') TO ('2026-11-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS ledger_entries_default PARTITION OF ledger_entries DEFAULT;

-- Indexes for Audits and Account Statement Queries
CREATE INDEX idx_ledger_account_created ON ledger_entries (account_id, created_at DESC);
CREATE INDEX idx_ledger_transaction_id ON ledger_entries (transaction_id);
CREATE INDEX idx_ledger_direction_type ON ledger_entries (direction, entry_type);
