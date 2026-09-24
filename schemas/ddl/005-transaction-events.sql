-- ============================================================================
-- Table: transaction_events
-- Description: State machine transitions for saga orchestration and audit logs.
-- ============================================================================

CREATE TABLE IF NOT EXISTS transaction_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL,
    saga_id UUID NOT NULL,
    from_state VARCHAR(50) NOT NULL,
    to_state VARCHAR(50) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_transaction_id ON transaction_events (transaction_id);
CREATE INDEX idx_events_saga_id ON transaction_events (saga_id);
CREATE INDEX idx_events_created_at ON transaction_events (created_at DESC);
