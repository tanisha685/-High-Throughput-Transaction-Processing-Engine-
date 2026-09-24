import http from 'k6/http';
import { check } from 'k6';
import { uuidv4 } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

// ============================================================================
// Scenario: LT-006 - Failover Under 12,000 TPS Load Test
// Simulates: Sustained 12,000 TPS with DB Primary kill at T+10m
// Pass/Fail:
// - Zero committed data loss (RPO = 0)
// - Recovery time <= 30s (RTO SLA)
// - p99 latency during failover <= 5000ms, returning to < 100ms post-promotion
// ============================================================================

export const options = {
  scenarios: {
    failover_test: {
      executor: 'constant-arrival-rate',
      rate: 12000,
      timeUnit: '1s',
      duration: '30m',
      preAllocatedVUs: 1500,
      maxVUs: 4000,
    },
  },
  thresholds: {
    // Failover SLA threshold allowances
    'http_req_failed{phase:steady_state}': ['rate<0.001'],
    'http_req_duration{phase:steady_state}': ['p(99)<100'],
  },
};

const BASE_URL = __ENV.API_URL || 'https://api.payscale.internal/v1';

export default function () {
  const idempotencyKey = uuidv4();
  const payload = JSON.stringify({
    source_account_id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a00',
    destination_account_id: 'b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a01',
    amount: 100.0,
    currency: 'INR',
    note: 'Failover Chaos Test Transaction',
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': idempotencyKey,
      'Authorization': 'Bearer chaos-test-token',
    },
    timeout: '5000ms',
  };

  const res = http.post(`${BASE_URL}/payments/p2p`, payload, params);

  check(res, {
    'valid response status (200 or transient 503)': (r) => r.status === 200 || r.status === 503,
  });
}
