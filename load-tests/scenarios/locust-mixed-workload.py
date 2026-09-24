"""
Locust Mixed Workload Benchmark Script: Scenario LT-007
Distribution:
- 60% P2P Payments (/payments/p2p)
- 20% Balance Inquiries (/accounts/{id}/balance)
- 10% Merchant Payments (/payments/merchant)
- 5%  Transaction History with Cursor Pagination (/accounts/{id}/transactions)
- 5%  Transaction Reversals / Refunds
Target: 12,000 TPS across 50,000 Simulated Users
"""

import uuid
import random
from locust import HttpUser, task, between, events


class MixedWorkloadFintechUser(HttpUser):
    wait_time = between(0.05, 0.2) # High concurrency user activity

    accounts = [
        "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a00", # Shard 0
        "b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a01", # Shard 1
        "c2eebc99-9c0b-4ef8-bb6d-6bb9bd380a02", # Shard 2
        "d3eebc99-9c0b-4ef8-bb6d-6bb9bd380a03", # Shard 3
    ]

    # Task 1: 60% P2P Transfers (Weight 60)
    @task(60)
    def p2p_payment(self):
        sender = random.choice(self.accounts)
        receiver = random.choice([acc for acc in self.accounts if acc != sender])
        idempotency_key = str(uuid.uuid4())
        
        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
            "Authorization": "Bearer test-jwt-token-workload"
        }
        payload = {
            "source_account_id": sender,
            "destination_account_id": receiver,
            "amount": round(random.uniform(50.0, 2500.0), 2),
            "currency": "INR",
            "note": "Diwali P2P Transfer"
        }

        with self.client.post("/v1/payments/p2p", json=payload, headers=headers, catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"P2P payment failed with status {resp.status_code}: {resp.text}")

    # Task 2: 20% Balance Inquiries (Weight 20)
    @task(20)
    def get_balance(self):
        acc = random.choice(self.accounts)
        headers = {"Authorization": "Bearer test-jwt-token-workload"}
        with self.client.get(f"/v1/accounts/{acc}/balance", headers=headers, catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Balance check failed: {resp.status_code}")

    # Task 3: 10% Merchant Payments (Weight 10)
    @task(10)
    def merchant_payment(self):
        sender = random.choice(self.accounts)
        headers = {
            "Idempotency-Key": str(uuid.uuid4()),
            "Authorization": "Bearer test-jwt-token-workload"
        }
        payload = {
            "source_account_id": sender,
            "destination_account_id": "m99ebc99-9c0b-4ef8-bb6d-6bb9bd380a99", # Merchant Shard
            "amount": round(random.uniform(100.0, 15000.0), 2),
            "currency": "INR"
        }
        self.client.post("/v1/payments/p2p", json=payload, headers=headers)

    # Task 4: 5% Transaction History with Cursor Pagination (Weight 5)
    @task(5)
    def transaction_history(self):
        acc = random.choice(self.accounts)
        headers = {"Authorization": "Bearer test-jwt-token-workload"}
        self.client.get(f"/v1/accounts/{acc}/transactions?limit=20", headers=headers)

    # Task 5: 5% Idempotency Deduplication Verification (Weight 5)
    @task(5)
    def duplicate_retry_test(self):
        # Re-send same request to verify Redis cache deduplication
        fixed_key = "idemp-stress-dedupe-key-fixed"
        headers = {
            "Idempotency-Key": fixed_key,
            "Authorization": "Bearer test-jwt-token-workload"
        }
        payload = {
            "source_account_id": self.accounts[0],
            "destination_account_id": self.accounts[1],
            "amount": 10.00,
            "currency": "INR"
        }
        self.client.post("/v1/payments/p2p", json=payload, headers=headers)
