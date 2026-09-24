-- ============================================================================
-- Table: fraud_rules
-- Description: Dynamic risk rules for real-time velocity and anomaly evaluation.
-- ============================================================================

CREATE TYPE rule_action_enum AS ENUM (
    'ALLOW',
    'FLAG_MANUAL_REVIEW',
    'CHALLENGE_OTP',
    'BLOCK'
);

CREATE TABLE IF NOT EXISTS fraud_rules (
    rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_code VARCHAR(50) UNIQUE NOT NULL,
    rule_name VARCHAR(150) NOT NULL,
    description TEXT,
    condition_expression TEXT NOT NULL, -- Evaluated by Rule Engine
    risk_score_delta INTEGER NOT NULL DEFAULT 10,
    action rule_action_enum NOT NULL DEFAULT 'FLAG_MANUAL_REVIEW',
    is_active BOOLEAN NOT NULL DEFAULT true,
    priority INTEGER NOT NULL DEFAULT 100,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_fraud_rules_active_priority ON fraud_rules (is_active, priority ASC);
