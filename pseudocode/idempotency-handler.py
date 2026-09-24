"""
Two-Tier Distributed Idempotency Validation Engine
PayScale Financial Technologies — High-Throughput Transaction Processing Engine

Features:
- Sub-millisecond duplicate detection via Redis Cluster SETNX
- In-Flight Request Deduplication & Concurrent Throttling
- Final Transaction Response Caching with 24-Hour TTL
- Automatic Lock Release on Early Validation Failure
"""

import time
import json
from typing import Dict, Any, Optional, Tuple
from enum import Enum


class IdempotencyStatus(Enum):
    NEW_REQUEST_LOCKED = "NEW_REQUEST_LOCKED"
    IN_FLIGHT = "IN_FLIGHT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class MockRedisCluster:
    """Simulates Redis Cluster with atomic key-value operations and TTL."""
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    def setnx_with_ttl(self, key: str, value: str, ttl_seconds: int) -> bool:
        """Simulates: SET key value NX EX ttl_seconds"""
        current_time = time.time()
        if key in self._store:
            expiry = self._store[key]["expiry"]
            if current_time < expiry:
                return False  # Key already exists
        self._store[key] = {
            "value": value,
            "expiry": current_time + ttl_seconds
        }
        return True

    def get(self, key: str) -> Optional[str]:
        """Simulates: GET key"""
        current_time = time.time()
        if key not in self._store:
            return None
        if current_time >= self._store[key]["expiry"]:
            del self._store[key]
            return None
        return self._store[key]["value"]

    def set(self, key: str, value: str, ttl_seconds: int):
        """Simulates: SET key value EX ttl_seconds"""
        self._store[key] = {
            "value": value,
            "expiry": time.time() + ttl_seconds
        }

    def delete(self, key: str):
        """Simulates: DEL key"""
        if key in self._store:
            del self._store[key]


class IdempotencyManager:
    def __init__(self, redis_client: MockRedisCluster, lock_ttl_seconds: int = 120, cache_ttl_seconds: int = 86400):
        self.redis = redis_client
        self.lock_ttl = lock_ttl_seconds
        self.cache_ttl = cache_ttl_seconds

    def start_transaction(self, idempotency_key: str, request_hash: str) -> Tuple[IdempotencyStatus, Optional[Dict[str, Any]]]:
        """
        Attempts to acquire idempotency lock.
        Returns: (Status, CachedResponseIfCompleted)
        """
        redis_key = f"idemp:{idempotency_key}"
        lock_payload = json.dumps({
            "status": IdempotencyStatus.IN_FLIGHT.value,
            "request_hash": request_hash,
            "created_at": time.time()
        })

        acquired = self.redis.setnx_with_ttl(redis_key, lock_payload, self.lock_ttl)
        if acquired:
            return IdempotencyStatus.NEW_REQUEST_LOCKED, None

        # Key already exists: Check status
        cached_str = self.redis.get(redis_key)
        if not cached_str:
            # Race condition edge case where key expired right between SETNX and GET
            return self.start_transaction(idempotency_key, request_hash)

        cached_data = json.loads(cached_str)
        if cached_data.get("status") == IdempotencyStatus.IN_FLIGHT.value:
            return IdempotencyStatus.IN_FLIGHT, None
        
        # Already completed: Return cached response directly
        return IdempotencyStatus.COMPLETED, cached_data.get("response")

    def complete_transaction(self, idempotency_key: str, response_payload: Dict[str, Any]):
        """Caches the final transaction response with a 24-hour TTL."""
        redis_key = f"idemp:{idempotency_key}"
        cached_payload = json.dumps({
            "status": IdempotencyStatus.COMPLETED.value,
            "response": response_payload,
            "completed_at": time.time()
        })
        self.redis.set(redis_key, cached_payload, self.cache_ttl)

    def release_lock_on_failure(self, idempotency_key: str):
        """Releases lock so client can retry with same key if error was transient."""
        redis_key = f"idemp:{idempotency_key}"
        self.redis.delete(redis_key)


if __name__ == "__main__":
    print("Testing Idempotency Handler...")
    redis = MockRedisCluster()
    handler = IdempotencyManager(redis)
    test_key = "idemp-unique-req-8899"
    req_hash = "hash-abc-123"

    # 1. First Request: Successfully acquires lock
    status1, resp1 = handler.start_transaction(test_key, req_hash)
    assert status1 == IdempotencyStatus.NEW_REQUEST_LOCKED
    print(f"First Submission: {status1.value} (Lock Acquired)")

    # 2. Concurrent Request with same key while in flight
    status2, resp2 = handler.start_transaction(test_key, req_hash)
    assert status2 == IdempotencyStatus.IN_FLIGHT
    print(f"Concurrent Submission: {status2.value} (Deduplicated)")

    # 3. Transaction Completes and writes final response
    mock_response = {"transaction_id": "txn-999", "status": "COMPLETED", "amount": "500.00"}
    handler.complete_transaction(test_key, mock_response)

    # 4. Third Request after completion: Returns cached response instantly
    status3, resp3 = handler.start_transaction(test_key, req_hash)
    assert status3 == IdempotencyStatus.COMPLETED
    assert resp3["transaction_id"] == "txn-999"
    print(f"Subsequent Submission: {status3.value}, Cached Payload: {resp3}")
    print("Idempotency Engine Verified Successfully!")
