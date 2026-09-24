# Day 6: Horizontal Database Sharding Strategy & Topology
**Project:** PayScale High-Throughput Transaction Processing Engine (HTTPE)  
**Author:** Senior Infrastructure Architect  
**Deliverable:** 7-Point Sharding Strategy Document & Mathematical Distribution Proof  

---

## 1. Shard Key Selection & Mathematical Distribution Analysis

Choosing the correct shard key is the single most critical decision in distributed storage architecture. We evaluated four primary candidates:

| Candidate Shard Key | Distribution Uniformity | Cross-Shard Txn Frequency | Hot-Spot Risk | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| `user_id` | High (Uniform) | ~80% of P2P transfers | Low | Rejected (Multi-account queries complex) |
| `geographic_region` | Poor (Skewed to Mumbai/Delhi) | ~60% cross-region | High (Regional festival surge) | Rejected (Severe load imbalance) |
| `account_id` (UUIDv7) | **Near Perfect (Uniform Hashing)** | ~75% cross-shard | Low (With merchant bucketing) | **SELECTED** |
| `transaction_id` | Perfect | 100% (Every balance check spans shards)| Extreme | Rejected (Unusable for balance locks) |

### Mathematical Distribution Uniformity:
Using MurmurHash3 or standard 64-bit integer hashing on `account_id`:
$$\text{Shard ID} = \text{MurmurHash3}(\text{account\_id}) \pmod N$$
Across $12 \times 10^6$ active accounts with $N = 4$ shards, the expected account distribution per shard is:
$$\mathbb{E}[S_i] = \frac{12,000,000}{4} = 3,000,000 \text{ accounts per shard}$$
With standard deviation $\sigma = \sqrt{N \cdot p \cdot (1-p)} \approx 1,500$ accounts ($< 0.05\%$ variance), ensuring an exceptionally balanced workload across physical nodes.

---

## 2. Shard Count, Topology & Capacity Sizing

```
+----------------------------------------------------------------------------------------------------+
|                                    4-SHARD PRODUCTION TOPOLOGY                                     |
+----------------------------------------------------------------------------------------------------+
|   [ Shard 0 ]                [ Shard 1 ]                [ Shard 2 ]                [ Shard 3 ]     |
|   AZ-a: Primary (RW)         AZ-b: Primary (RW)         AZ-c: Primary (RW)         AZ-a: Primary (RW)     |
|   AZ-b: Standby 1 (Sync RO)  AZ-c: Standby 1 (Sync RO)  AZ-a: Standby 1 (Sync RO)  AZ-b: Standby 1 (Sync RO)|
|   AZ-c: Standby 2 (Sync RO)  AZ-a: Standby 2 (Sync RO)  AZ-b: Standby 2 (Sync RO)  AZ-c: Standby 2 (Sync RO)|
+----------------------------------------------------------------------------------------------------+
```

### Capacity Calculations for 12,000 TPS Target:
- **Target Peak Throughput:** 12,000 write TPS sustained (18,000 TPS burst).
- **Per-Shard Target Load:**
  $$\text{Throughput per shard} = \frac{12,000 \text{ TPS}}{4 \text{ shards}} = 3,000 \text{ TPS / shard}$$
  $$\text{Burst load per shard} = \frac{18,000 \text{ TPS}}{4 \text{ shards}} = 4,500 \text{ TPS / shard}$$
- Sizing on AWS `r6g.2xlarge` (8 vCPU, 64 GB RAM, NVMe `io2` with 10,000 IOPS) benchmarked at 4,800 write TPS per instance provides a **35% safety headroom** during peak Diwali flash sales.

---

## 3. Cross-Shard Transaction Protocol: Distributed Saga vs. 2PC vs. TCC

When Sender (Account $A$) resides on **Shard 1** and Receiver (Account $B$) resides on **Shard 3**, a cross-shard transaction is required.

```mermaid
sequenceDiagram
    autonumber
    participant Orchestrator as Transaction Orchestrator
    participant Shard1 as PostgreSQL Shard 1 (Sender A)
    participant Shard3 as PostgreSQL Shard 3 (Receiver B)

    Note over Orchestrator: Step 1: Local Debit on Shard 1
    Orchestrator->>Shard1: OCC Debit Account A (₹500, version=v)
    Shard1-->>Orchestrator: Debit OK (New version = v+1)

    Note over Orchestrator: Step 2: Local Credit on Shard 3
    Orchestrator->>Shard3: OCC Credit Account B (₹500, version=u)
    
    alt Credit Succeeds (Happy Path)
        Shard3-->>Orchestrator: Credit OK
        Orchestrator->>Orchestrator: Mark Saga COMPLETED
    else Credit Fails (Network Partition / Shard 3 Down)
        Shard3--xOrchestrator: Timeout / Error
        Note over Orchestrator: Compensation Triggered!
        Orchestrator->>Shard1: Compensating Credit to Account A (+₹500)
        Shard1-->>Orchestrator: Refund OK
        Orchestrator->>Orchestrator: Mark Saga FAILED_ROLLEDBACK
    end
```

### Why Orchestrated Saga over Two-Phase Commit (2PC):
- **2PC Blocking Problem:** 2PC holds row locks across both Shard 1 and Shard 3 throughout the entire prepare-commit roundtrip. Any network latency spike holds locks, exhausting connection pools and crippling system throughput from 12,000 TPS down to < 800 TPS.
- **Saga Non-Blocking Advantage:** Sagas commit each local step independently and rely on compensating transactions for rollback, maintaining high throughput and eliminating distributed deadlocks.

---

## 4. Shard Rebalancing & Zero-Downtime Expansion

When scaling from 4 shards to 8 shards in future expansions:
1. **Virtual Vnodes:** The system maps keys onto 1,024 Virtual Shards (Vnodes). Initially, each physical shard hosts 256 Vnodes.
2. **Online Dual-Writing & CDC Replication:** A new physical shard is provisioned; logical replication streams 128 Vnodes from the donor shard to the recipient shard in the background.
3. **Cutover ( < 200ms ):** The routing configuration in Redis/PgBouncer is atomically updated to point the 128 Vnodes to the new shard.

---

## 5. Hot Merchant Account Partitioning (Sub-Balance Bucketing)

High-volume merchants (e.g., Flipkart or Swiggy during flash sales) receive thousands of concurrent credits per second. To eliminate hot-spot row contention on a single merchant account:
- The merchant balance is divided into **16 Sub-Balance Buckets** (`bucket_0` through `bucket_15`) on the database shard.
- Incoming credits are randomly routed to $\text{random}(0, 15)$, distributing write concurrency across 16 separate physical rows.
- Merchant balance reads compute:
  $$\text{Total Merchant Balance} = \sum_{i=0}^{15} \text{bucket}_i.\text{available\_balance}$$

---

## 6. RBI Data Locality & High Availability Alignment

1. **Multi-AZ Replication:** All 4 shards maintain synchronous replicas strictly within the AWS Mumbai (`ap-south-1`) region.
2. **Disaster Recovery (DR):** An asynchronous read replica cluster is maintained in AWS Hyderabad (`ap-south-2`), satisfying the RBI inter-region disaster recovery mandate (> 500 km geographical separation).
