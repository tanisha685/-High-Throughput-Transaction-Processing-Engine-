# ADR-005: Selection of Write-Through for Idempotency and Cache-Aside with Event Invalidation for Account Balances

## Status
Accepted

## Context
In high-throughput transaction engines (12,000+ TPS), caching is vital for reducing database read load. However, improper caching in financial systems introduces severe consistency risks (e.g., displaying stale balances, double-spend vulnerabilities, or losing idempotency tokens).

During load testing on the legacy monolith, the single Redis instance suffered:
- Cache hit rates collapsing from 92% to 61% under load (BN-004).
- Memory exhaustion due to unbounded session caching without TTLs.
- Stale balance reads causing false validation rejections.

We must define an explicit caching and invalidation strategy for:
1. Client Idempotency Keys (24-hour deduplication).
2. Hot Account Balance Snapshots.
3. API Gateway Tier Rate Limiting Counters.

## Decision
We adopt a **Dual Caching Strategy**:

### 1. Write-Through Caching for Idempotency Keys:
- When a payment request arrives, the API Gateway immediately executes an atomic `SET key IN_FLIGHT NX EX 86400` against the Redis Cluster.
- Once the transaction completes, the final response JSON is written to Redis with a 24-hour TTL (`SET key ResponseJSON EX 86400`).
- This guarantees sub-millisecond duplicate detection before any database or microservice compute is invoked.

### 2. Cache-Aside with Event-Driven Invalidation for Account Balances:
- Account balance reads first check the Redis hot cache.
- On cache miss: Read balance from the database shard and populate Redis with a short TTL (60 seconds).
- On balance mutation (debit/credit): The core database update commits, and the Debezium CDC outbox event publishes a cache eviction signal (`DEL account:{account_id}`) across all Redis nodes.

## Alternatives Considered

| Dimension | Cache-Aside + Event Eviction (Selected) | Write-Behind (Async DB Flush) | Write-Through (Sync DB + Cache) |
| :--- | :--- | :--- | :--- |
| **Financial Correctness**| **100% (PostgreSQL is Single Source of Truth)**| Flawed (Redis crash causes lost money!) | High |
| **Write Latency Overhead**| **Minimal (< 1ms async pub)** | Ultra-low (In-memory write) | Higher (Serial Redis + DB write) |
| **Staleness Window** | < 100ms (Bounded by CDC replication) | None (Reads hit cache) | None |
| **Failure Recovery** | Instant (Rebuild cache from DB) | Complex (Reconstruct lost writes from logs)| Rebuild from DB |

- **Write-Behind Caching:** Completely rejected for financial transaction data. In Write-Behind, writes occur in Redis first and flush asynchronously to the database. If a Redis master crashes before flushing, committed customer funds are permanently lost, causing severe financial loss and regulatory violations.

## Consequences

### Positive:
- **Zero Financial Loss Risk:** PostgreSQL remains the immutable source of truth; Redis acts purely as an ephemeral performance accelerator.
- **High Hit Ratio (> 95%):** Segregating idempotency keys from hot account balances prevents memory thrashing.
- **Sub-Millisecond Deduplication:** Idempotency checks resolve in < 1.2ms at the ingress layer.

### Negative & Trade-offs:
- Under rapid consecutive balance queries immediately following a transfer, clients may observe an eventual consistency window of up to 100ms before cache eviction propagates.

## Compliance & Regulatory Alignment
- **RBI Digital Payment Directives:** Financial balances are persistently anchored in relational storage within India before client acknowledgment.
- **PCI-DSS v4.0:** Cached payloads contain no sensitive cardholder verification data (CVV/PIN).
