-- ============================================================================
-- Table: accounts
-- Description: Core account balance entity supporting Optimistic Concurrency
-- Control (OCC), shard routing, tier rate limits, and dual balances.
-- ============================================================================

CREATE TYPE account_type_enum AS ENUM (
    'SAVINGS',
    'CURRENT',
    'WALLET',
    'MERCHANT',
    'SETTLEMENT_POOL'
);

CREATE TYPE account_status_enum AS ENUM (
    'ACTIVE',
    'FROZEN',
    'SUSPENDED',
    'CLOSED'
);

CREATE TYPE account_tier_enum AS ENUM (
    'BASIC',       -- 50 TPS limit
    'PREMIUM',     -- 200 TPS limit
    'MERCHANT'     -- 1000 TPS limit
);

CREATE TABLE IF NOT EXISTS accounts (
    account_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    account_type account_type_enum NOT NULL DEFAULT 'SAVINGS',
    currency CHAR(3) NOT NULL DEFAULT 'INR',
    available_balance NUMERIC(18, 4) NOT NULL DEFAULT 0.0000 CHECK (available_balance >= 0.0000),
    ledger_balance NUMERIC(18, 4) NOT NULL DEFAULT 0.0000,
    version BIGINT NOT NULL DEFAULT 1,
    status account_status_enum NOT NULL DEFAULT 'ACTIVE',
    tier account_tier_enum NOT NULL DEFAULT 'BASIC',
    shard_key INTEGER NOT NULL,
    daily_limit NUMERIC(18, 4) NOT NULL DEFAULT 100000.0000,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_positive_ledger CHECK (ledger_balance >= -10000000.0000)
);

-- B-Tree index for fast user account lookups
CREATE INDEX idx_accounts_user_id ON accounts (user_id);

-- Index for status & tier filtering
CREATE INDEX idx_accounts_status ON accounts (status) WHERE status != 'ACTIVE';

-- Trigger to automatically update updated_at timestamp on record changes
CREATE OR REPLACE FUNCTION update_account_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_accounts_updated_at
BEFORE UPDATE ON accounts
FOR EACH ROW
EXECUTE FUNCTION update_account_timestamp();
