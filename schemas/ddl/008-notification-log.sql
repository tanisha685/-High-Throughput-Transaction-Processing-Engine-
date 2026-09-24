-- ============================================================================
-- Table: notification_log
-- Description: Audit and delivery log for real-time WebSockets, SMS, and Push.
-- ============================================================================

CREATE TYPE channel_type_enum AS ENUM (
    'WEBSOCKET',
    'PUSH',
    'SMS',
    'EMAIL',
    'WEBHOOK'
);

CREATE TYPE delivery_status_enum AS ENUM (
    'QUEUED',
    'SENT',
    'DELIVERED',
    'FAILED'
);

CREATE TABLE IF NOT EXISTS notification_log (
    notification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    transaction_id UUID,
    channel channel_type_enum NOT NULL,
    destination VARCHAR(255) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    status delivery_status_enum NOT NULL DEFAULT 'QUEUED',
    retry_count INTEGER NOT NULL DEFAULT 0,
    provider_response_id VARCHAR(100),
    error_message VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMPTZ
);

CREATE INDEX idx_notif_user_created ON notification_log (user_id, created_at DESC);
CREATE INDEX idx_notif_txn_id ON notification_log (transaction_id);
CREATE INDEX idx_notif_status ON notification_log (status) WHERE status = 'FAILED';
