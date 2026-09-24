import http from 'k6/http';
import { check, sleep } from 'k6';
import { uuidv4 } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

// ============================================================================
// Scenario: LT-002 - Sustained 12,000 TPS Target Load Test
// Target: 12,000 TPS for 60 minutes
// Pass/Fail: p95 < 50ms, p99 < 100ms, Error Rate < 0.01%
// ============================================================================

export const options = {
  scenarios: {
    target_throughput_test: {
      executor: 'constant-arrival-rate',
      rate: 12000,
      timeUnit: '1s',
      duration: '60m',
      preAllocatedVUs: 2000,
      maxVUs: 5000,
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<50', 'p(99)<100', 'p(99.9)<250'],
    http_req_failed: ['rate<0.0001'], // 99.99% success rate
  },
};

const BASE_URL = __ENV.API_URL || 'https://api.payscale.internal/v1';

// Seeded account IDs across the 4 database shards
const TEST_ACCOUNTS = [
  'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a00', // Shard 0
  'b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a01', // Shard 1
  'c2eebc99-9c0b-4ef8-bb6d-6bb9bd380a02', // Shard 2
  'd3eebc99-9c0b-4ef8-bb6d-6bb9bd380a03', // Shard 3
];

export default function () {
  const senderIndex = Math.floor(Math.random() * TEST_ACCOUNTS.length);
  let receiverIndex = Math.floor(Math.random() * TEST_ACCOUNTS.length);
  while (receiverIndex === senderIndex) {
    receiverIndex = Math.floor(Math.random() * TEST_ACCOUNTS.length);
  }

  const idempotencyKey = uuidv4();
  const payload = JSON.stringify({
    source_account_id: TEST_ACCOUNTS[senderIndex],
    destination_account_id: TEST_ACCOUNTS[receiverIndex],
    amount: (Math.random() * 500 + 10).toFixed(2),
    currency: 'INR',
    note: 'Load Test P2P Transfer',
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': idempotencyKey,
      'Authorization': 'Bearer test-jwt-token-synthetic-load',
    },
    timeout: '2000ms',
  };

  const res = http.post(`${BASE_URL}/payments/p2p`, payload, params);

  check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 100ms': (r) => r.timings.duration < 100,
    'has transaction_id': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.transaction_id !== undefined && body.status === 'COMPLETED';
      } catch (e) {
        return false;
      }
    },
  });
}
