# ADR-003: Selection of Hash-Based Sharding on `account_id` with Distributed Saga Orchestration

## Status
Accepted

## Context
PayScale's transaction processing system must scale to 12,000+ sustained TPS and 18,000 TPS peak burst. In a monolithic database, all write I/O concentrates on a single primary node, causing lock contention, connection starvation, and high write latencies.

To scale horizontally, we must partition the dataset across multiple physical PostgreSQL nodes. The sharding strategy must address:
1. Uniform distribution of account records and transaction writes across nodes.
2. Low query latency for single-account balance queries and balance debits (< 10ms).
3. A robust protocol for cross-shard peer-to-peer transfers (where sender and recipient accounts reside on distinct physical shards).
4. Prevention of hot-spot bottlenecks on high-throughput merchant accounts.
5. Strict adherence to RBI Data Residency regulations (servers within India).

## Decision
We adopt **Application-Level Hash-Based Sharding** keyed on `account_id` using a consistent virtual shard mapping (1,024 Vnodes across 4 physical PostgreSQL clusters). Cross-shard transactions will be orchestrated using the **Distributed Saga Pattern** with forward execution and compensating rollbacks.

### Architectural Details:
- **Shard Key:** `account_id` (UUIDv7).
- **Physical Topology:** 4 Shards (each with 1 Primary + 2 Synchronous Standby replicas in AWS Mumbai).
- **Shard Routing Formula:** `shard_id = (MurmurHash3(account_id) % 1024) / 256`.
- **Cross-Shard Coordination:** Non-blocking Orchestrated Saga coordinated by the Transaction Orchestrator service. Sagas execute Step 1 (Debit Sender on Shard A) and Step 2 (Credit Receiver on Shard B). If Step 2 fails, Step 1 is rolled back via a compensating credit refund.
- **Hot Account Optimization:** High-volume merchant accounts are subdivided into 16 concurrent balance sub-buckets, eliminating single-row lock contention.

## Alternatives Considered

| Dimension | Hash-Based (`account_id`) [Selected] | Range-Based Sharding | Geographic Sharding | Two-Phase Commit (2PC) Distributed DB |
| :--- | :--- | :--- | :--- | :--- |
| **Write Distribution**| Uniform across all shards ($\sigma < 0.05\%$) | Prone to severe hot ranges | Skewed heavily to Tier-1 metros | Uniform |
| **Single-Account Latency**| **< 8 ms (Single shard query)** | < 8 ms | < 8 ms | 45-80 ms (Global consensus overhead) |
| **Cross-Shard Handling** | Saga with Compensations | Saga with Compensations | Complex inter-region latency | Synchronous 2PC locks |
| **Deadlock Risk** | **0% (Lock-free OCC)** | High during range scans | Low | Extreme under load |
| **Cost at Target Scale**| **~$14,400 / month** | ~$14,400 / month | ~$18,000 / month | > $26,000 / month |

- **Two-Phase Commit (2PC):** Rejected because 2PC holds pessimistic locks across multiple database nodes during the network prepare/commit cycle. If any node experiences a minor network jitter or pause, row locks block hundreds of concurrent transactions, leading to cascading connection exhaustion.
- **Geographic Sharding:** Rejected because user transaction volume is heavily concentrated in major metropolitan hubs (Mumbai, Bengaluru, Delhi NCR), which would create severe load imbalance on the West/North shards while leaving other nodes underutilized.

## Consequences

### Positive:
- **Linear Horizontal Scalability:** Adding 4 additional shards (scaling from 4 to 8) doubles system write throughput to 24,000 TPS.
- **Isolation of Failure:** If Shard 2 fails, accounts on Shards 0, 1, and 3 continue processing without interruption (75% system availability maintained even during severe isolated failure).
- **Sub-10ms Balance Operations:** 100% of single-account balance checks and self-transfers execute locally on one shard.

### Negative & Trade-offs:
- Cross-shard transfers introduce eventual consistency window (< 500ms) between debit and credit completion.
- Rebalancing during shard expansion requires background virtual vnode migration tooling.

## Compliance & Regulatory Alignment
- **RBI Data Localization (2018):** All 4 physical shards and replication streams reside strictly within the AWS Mumbai (`ap-south-1`) region.
- **PCI-DSS v4.0:** Shard storage volumes are encrypted using AWS KMS customer-managed keys (CMK) with AES-256.
