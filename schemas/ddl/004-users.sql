-- ============================================================================
-- Table: users
-- Description: User identity, profile, KYC status, and risk tier management.
-- ============================================================================

CREATE TYPE kyc_status_enum AS ENUM (
    'PENDING',
    'VERIFIED',
    'REJECTED',
    'EXPIRED'
);

CREATE TYPE user_status_enum AS ENUM (
    'ACTIVE',
    'BLOCKED',
    'DORMANT',
    'DELETED'
);

CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number VARCHAR(20) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    kyc_status kyc_status_enum NOT NULL DEFAULT 'PENDING',
    kyc_document_type VARCHAR(50),
    kyc_document_hash VARCHAR(128),
    user_status user_status_enum NOT NULL DEFAULT 'ACTIVE',
    risk_score INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_phone ON users (phone_number);
CREATE INDEX idx_users_kyc_status ON users (kyc_status);
CREATE INDEX idx_users_risk_score ON users (risk_score);
