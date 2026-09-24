# Day 7: Message Queue Topology & Exactly-Once Semantics (EOS)
**Project:** PayScale High-Throughput Transaction Processing Engine (HTTPE)  
**Author:** Senior Infrastructure Architect  
**Deliverable:** Kafka Topic Architecture, Partition Math, Outbox CDC, and DLQ Policies  

---

## 1. Kafka Topic Topology & Mathematical Partition Sizing

To guarantee linear scalability without partition bottlenecks at 12,000 TPS sustained (18,000 TPS burst), we establish a dedicated topic topology.

### 1.1 Topic Sizing & Configuration Matrix

| Topic Name | Partitions | Replication Factor | Min In-Sync Replicas | Partition Key | Retention Policy | Peak Ingestion Rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `transaction-events` | **48** | 3 | 2 | `account_id` | 7 Days (Delete) | 18,000 msgs/sec |
| `outbox-cdc-events` | **48** | 3 | 2 | `account_id` | 3 Days (Delete) | 18,000 msgs/sec |
| `notification-dispatch`| **24** | 3 | 2 | `user_id` | 24 Hours (Delete)| 15,000 msgs/sec |
| `settlement-batch` | **8** | 3 | 2 | `batch_id` | 30 Days (Compact)| 500 msgs/sec |
| `audit-compliance` | **24** | 3 | 2 | `transaction_id`| 90 Days (Delete)| 36,000 msgs/sec |
| `txn-dead-letter-queue`| **12** | 3 | 2 | `transaction_id`| 30 Days (Delete)| < 50 msgs/sec |

### 1.2 Partition Mathematics & Throughput Proof
Let:
- $T_{\text{target}} = 18,000 \text{ msgs/sec}$ (peak burst).
- $C_{\text{single\_consumer}} \approx 450 \text{ msgs/sec}$ (conservative throughput for a single worker thread executing database/network operations).

The required minimum partition count $P$ is calculated as:
$$P = \frac{T_{\text{target}}}{C_{\text{single\_consumer}}} = \frac{18,000}{450} = 40 \text{ partitions}$$
We select **48 partitions** (divisible by 2, 3, 4, 6, 8, 12, 16, 24, 48), ensuring optimal load balancing across any consumer group pod count ($N \in \{6, 8, 12, 16, 24, 48\}$).

---

## 2. Consumer Group Topology & Workload Mapping

```mermaid
flowchart LR
    subgraph KAFKA["Kafka Cluster: topic 'transaction-events' (48 Partitions)"]
        P0["P0..P7"]
        P1["P8..P15"]
        P2["P16..P23"]
        P3["P24..P31"]
        P4["P32..P39"]
        P5["P40..P47"]
    end

    subgraph CG_NOTIFY["Consumer Group: 'notification-worker-group' (12 Pods)"]
        W1["Notify Pods (4 Partitions/Pod)"]
    end

    subgraph CG_RECON["Consumer Group: 'reconciliation-worker-group' (6 Pods)"]
        W2["Recon Pods (8 Partitions/Pod)"]
    end

    subgraph CG_AUDIT["Consumer Group: 'audit-compliance-group' (8 Pods)"]
        W3["Audit Pods (6 Partitions/Pod)"]
    end

    KAFKA --> CG_NOTIFY
    KAFKA --> CG_RECON
    KAFKA --> CG_AUDIT
```

Each consumer group operates independently. If the Notification Service slows down due to external SMS gateway latency, its consumer lag increases without impacting the Reconciliation or Audit services in any way.

---

## 3. Exactly-Once Semantics (EOS) via Transactional Outbox Pattern

The dual-write problem (writing to a database and publishing to Kafka atomically) cannot be solved with naive dual calls because network crashes leave state inconsistent.

```mermaid
sequenceDiagram
    autonumber
    participant Core as Payment Service
    participant DB as PostgreSQL Shard
    participant CDC as Debezium CDC Engine
    participant Kafka as Apache Kafka Bus
    participant Consumer as Notification Worker

    Note over Core,DB: Step 1: Atomic Database Transaction
    Core->>DB: BEGIN TRANSACTION;
    Core->>DB: UPDATE accounts SET available_balance = ... WHERE account_id = ...;
    Core->>DB: INSERT INTO ledger_entries (...);
    Core->>DB: INSERT INTO outbox_table (event_id, aggregate_id, event_type, payload);
    Core->>DB: COMMIT;
    Note over Core,DB: Transaction Committed Atomically (WAL Written)

    Note over DB,Kafka: Step 2: Asynchronous Log-Based CDC
    DB-->>CDC: Read PostgreSQL Write-Ahead Log (WAL)
    CDC->>Kafka: Publish Event to 'transaction-events' (acks=all, enable.idempotence=true)
    Kafka-->>CDC: Offset Acked
    
    Note over Kafka,Consumer: Step 3: Idempotent Consumer Processing
    Kafka->>Consumer: Deliver Event (Offset X)
    Consumer->>Consumer: Check Processed Event ID in Redis/DB
    Consumer->>Consumer: Dispatch Notification
    Consumer->>Kafka: Commit Offset X
```

---

## 4. Dead Letter Queue (DLQ) & Intelligent Retry Policy

When message processing fails in downstream consumers:
1. **Immediate Retry (1–3 attempts):** Retries within 50ms for transient network errors.
2. **Exponential Jittered Backoff (Attempts 4–5):** Waits $200\text{ms} \times 2^{\text{attempt}} \pm \text{jitter}$.
3. **Dead Letter Routing (After 5 failures):** The poisoned message is routed to `txn-dead-letter-queue` with comprehensive failure headers:
   - `x-original-topic`: `transaction-events`
   - `x-exception-message`: `Connection Timeout to SMS Provider`
   - `x-failed-timestamp`: `2026-09-24T12:00:00Z`
   - `x-retry-count`: `5`
4. **DLQ Replay Tooling:** SREs can inspect messages in the Web UI, trigger bulk reprocessing, or discard invalid events without blocking active Kafka partitions.
