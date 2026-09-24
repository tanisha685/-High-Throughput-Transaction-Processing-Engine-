# Day 1: Scenario Analysis & Bottleneck Investigation
**Project:** PayScale Financial Technologies — High-Throughput Transaction Processing Engine (HTTPE)  
**Author:** Senior Infrastructure Architect  
**Evaluation:** Architecture Review Board (ARB) / Zetheta Algorithms Assessment  

---

## 1. Executive Scenario Analysis

### 1.1 Context & The Diwali Surge Challenge
PayScale Financial Technologies is a high-growth fintech neo-bank based in Mumbai, India, serving **12 million Monthly Active Users (MAU)** and processing approximately **28 million daily transactions** across Peer-to-Peer (P2P) transfers, merchant POS/online payments, bill settlements, and micro-lending.

With the upcoming **Diwali Festive Season Flash Sale** launching in 15 days, marketing has aggressively committed to 10x promotional campaigns (cashbacks, flash merchant discounts, zero-fee P2P festive gifts). Transaction volume is forecast to skyrocket from the current baseline peak of **1,200 Transactions Per Second (TPS)** to a sustained **12,000 TPS**, with burst traffic spikes hitting **18,000 TPS** during midnight flash drops.

Under our current monolithic infrastructure:
- The database is a single **PostgreSQL 15 Primary** with 200 max connections.
- The messaging tier relies on a **single-node RabbitMQ** broker.
- Concurrency uses **pessimistic row locking** (`SELECT ... FOR UPDATE`), causing massive contention.
- The caching tier is a **single-node Redis (16GB)** suffering memory evictions and high miss rates under load.

A recent 2-hour Locust load test simulating 50,000 concurrent users caused catastrophic system collapse at just **1,800 TPS**, exhibiting a 40% request timeout rate, deep query backlogs, and a 15% database deadlock rate.

```
+-----------------------------------------------------------------------------------+
|                            THE 10X DIWALI SCALING CHALLENGE                       |
+-----------------------------------------------------------------------------------+
|  Metric                   Current Baseline       Diwali Target      Surge Factor  |
|  Peak Throughput (TPS)    1,200 TPS              12,000 TPS         10.0x         |
|  Burst Capacity (TPS)     1,500 TPS              18,000 TPS         12.0x         |
|  p50 End-to-End Latency   85 ms                  <= 30 ms           2.8x faster   |
|  p99 End-to-End Latency   450 ms                 <= 100 ms          4.5x faster   |
|  Monthly Active Users     12 Million             35 Million         2.9x          |
|  Daily Transaction Volume 28 Million             85 Million         3.0x          |
|  Uptime SLA               99.9% (8.76 hrs down)  99.99% (52.6 min)  4 Nines       |
|  Max Monthly Budget       $12,000/mo             $45,000/mo ceiling 3.75x budget  |
+-----------------------------------------------------------------------------------+
```

### 1.2 Core Constraints & Regulatory Mandates
1. **RBI Compliance & Data Residency (2018/2021 Directives):** All transaction data, user PII, logs, and cryptographic material must physically reside on servers within Indian borders (`ap-south-1` Mumbai / `ap-south-2` Hyderabad). 2-year minimum hot data retention is strictly mandated for audit trails.
2. **Strict Financial ACID Guarantees:** Conservation of money ($ \sum \text{Balances}_{\text{pre}} = \sum \text{Balances}_{\text{post}} $) with zero double-spend, zero ghost transactions, and immediate rollback/compensation on failure within 30 seconds.
3. **Budget Ceiling:** Infrastructure total cost must not exceed **$45,000/month**.
4. **Engineering Pragmatism:** Team expertise is centered on Java/Kotlin, PostgreSQL, and Linux environments; solutions must avoid exotic, untested tech stacks while achieving sub-100ms p99 latency.

---

## 2. Comprehensive Bottleneck Analysis (Locust 50K User Benchmark)

The pre-scaling benchmark revealed eight distinct failure points (BN-001 through BN-008). Below is the comprehensive diagnostic and proposed architectural mitigation for each.

```
                      CURRENT BOTTLENECK MAP (COLLAPSE AT 1,800 TPS)
                      
   [ Clients ] ---> [ API Gateway ] (BN-005: 12% False Rejections)
                           |
                           v
                 [ App Thread Pool ] (BN-003: 40% Timeouts & Thread Exhaustion)
                    /      |      \
                   /       |       \
                  v        |        v
   (BN-004: Redis)         |       (BN-002: RabbitMQ Single Node Lag > 30s)
   Misses drop to 61%      |
                           v
                 [ PostgreSQL Primary ] (BN-001: Pool Exhaustion @ 1.8K TPS)
                 (BN-006: Row Locks & 15% Deadlocks on Accounts Table)
```

---

### Deep-Dive on Top Bottlenecks

#### 🔴 BN-001: PostgreSQL Primary Connection Pool Exhaustion (CRITICAL)
- **Observation:** At 1,800 TPS, active connections hit the hard limit of 200; query queue depth exceeded 500, leading to massive client connection timeouts (`504 Gateway Timeout`).
- **Root Cause:** Direct backend application connections without intelligent multiplexing; long-running transactions held connections open while executing downstream synchronous HTTP calls.
- **Architectural Solution:**
  1. Introduce **PgBouncer** connection pooling in transaction mode, allowing 2,000+ client connections multiplexed onto a lean pool of ~100 backend server connections.
  2. Horizontally partition the database into **4 database shards** using hash-based sharding on `account_id`, dividing write I/O evenly across 4 independent primary instances.
  3. Decouple synchronous calls so transactions execute in under 10ms.

#### 🔴 BN-002: RabbitMQ Single-Node Message Acknowledgment Backlog (CRITICAL)
- **Observation:** Message consumer lag exceeded 30 seconds once ingestion reached 2,000 TPS; memory alarms forced broker throttling and connection blocking.
- **Root Cause:** Single-node RabbitMQ broker architecture with synchronous disk persistence on a single queue; consumer thread contention and head-of-line blocking.
- **Architectural Solution:**
  1. Migrate to a **3-broker Apache Kafka cluster** with topics partitioned across 48 partitions.
  2. Implement **Partition-Key based routing** (`account_id` as key) to guarantee strict chronological ordering per account while enabling 48 parallel consumer streams.
  3. Adopt the **Transactional Outbox Pattern** with Debezium CDC to decouple transactional state writes from event publication.

#### 🔴 BN-006: Database Row Contention & Deadlocks on `accounts` Table (CRITICAL)
- **Observation:** 15% of all concurrent transfer transactions failed due to PostgreSQL deadlock detection (`ERROR: 40P01: deadlock detected`), specifically on high-frequency merchant and settlement accounts.
- **Root Cause:** Pessimistic row locking (`SELECT ... FOR UPDATE`). When Transaction A locks Account 1 then requests Account 2, while concurrent Transaction B locks Account 2 then requests Account 1, circular wait occurs.
- **Architectural Solution:**
  1. Replace pessimistic locking with **Optimistic Concurrency Control (OCC)** using a numeric `version` counter and atomic Compare-And-Swap (CAS):
     ```sql
     UPDATE accounts 
     SET available_balance = available_balance - :amount, version = version + 1 
     WHERE account_id = :id AND version = :read_version AND available_balance >= :amount;
     ```
  2. Implement jittered exponential backoff retries in the application layer (max 3 retries).
  3. Partition hot merchant accounts into sub-balance shards (ledger buckets).

#### 🟠 BN-003: Application Layer Thread Pool Saturation (HIGH)
- **Observation:** 40% request timeout rate under 2,000 TPS as Tomcat/Spring worker threads were completely exhausted waiting for synchronous I/O.
- **Root Cause:** Synchronous blocking I/O model (one thread per request) waiting on database locks, fraud service REST endpoints, and notification SMS APIs.
- **Architectural Solution:**
  1. Migrate to asynchronous, non-blocking I/O using Kotlin Coroutines / Java 21 Virtual Threads (Project Loom) or Netty.
  2. Decouple non-critical paths (notifications, audit logging, analytics) to asynchronous Kafka events.
  3. Deploy application services in an Auto-Scaling Group (ASG) scaling dynamically from 8 to 64 instances based on CPU and request queue metrics.

#### 🟠 BN-004: Redis Cache Degradation & Memory Eviction (HIGH)
- **Observation:** Cache hit ratio degraded from 92% to 61% under load; frequent `OOM command not allowed` errors and cache thrashing.
- **Root Cause:** Single 16GB Redis node storing both short-lived idempotency tokens, session tokens, and large uncompressed account metadata with no memory sharding.
- **Architectural Solution:**
  1. Deploy a **6-node Redis Cluster (3 Masters + 3 Replicas)** with 96 GB aggregate RAM.
  2. Isolate data namespaces: Dedicated Redis instance for Idempotency Keys (24h TTL) and rate limiting; separate cluster for hot account cache.
  3. Enforce `volatile-lru` eviction policies and explicit TTLs on all keys.

#### 🟡 BN-005: API Gateway Rate Limiter False Positives (MEDIUM)
- **Observation:** 12% of legitimate user requests were falsely throttled with `429 Too Many Requests`.
- **Root Cause:** Naive global IP-based rate limiting without account tier awareness or distributed token bucket coordination.
- **Architectural Solution:**
  1. Deploy **Kong Gateway / Envoy** with Redis-backed distributed Token Bucket / Leaky Bucket algorithms.
  2. Implement tiered rate limiting: Basic Tier (50 TPS), Premium Tier (200 TPS), Merchant Tier (1,000 TPS).
  3. Whitelist internal health checks and payment webhook endpoints.

#### 🟡 BN-007: Cross-AZ Network Latency Spikes (MEDIUM)
- **Observation:** Cross-AZ roundtrip latency spiked to 18ms during peak traffic, degrading synchronous transaction hops.
- **Root Cause:** Uncoordinated microservice placement across AWS Availability Zones without zone-aware routing.
- **Architectural Solution:**
  1. Implement **AZ-affinity routing** via AWS Application Load Balancers and Envoy local endpoints to keep request hops within the same AZ (`ap-south-1a`, `ap-south-1b`, `ap-south-1c`).
  2. Restrict cross-AZ traffic exclusively to asynchronous DB/Kafka replication.

#### 🟢 BN-008: ELK Log Aggregation Ingestion Lag (LOW)
- **Observation:** Log indexing lag reached > 5 minutes, blinding operations during critical load testing phases.
- **Root Cause:** Synchronous log appenders shipping raw, unformatted JSON logs over heavy TCP channels directly to Logstash.
- **Architectural Solution:**
  1. Implement asynchronous log buffering via Vector / Fluent Bit writing to an isolated Kafka logging topic before batch ingestion into Elasticsearch / Grafana Loki.
  2. Separate operational metrics (Prometheus pull model) from diagnostic debug logs.

---

## 3. Summary & 15-Day Roadmap Alignment

| Phase | Milestone | Target Deliverable |
| :--- | :--- | :--- |
| **Days 1–2** | Problem Analysis & Tech Selection | Scenario Analysis, Bottleneck Matrix, ADR-001 & ADR-002 |
| **Days 3–4** | High-Level & Data Flow Architecture | 13-Component HLD, System Sequence Diagrams, Timeout Budgets |
| **Days 5–6** | Storage & Sharding Architecture | PostgreSQL DDLs, 4-Shard Consistent Hashing, Cross-Shard Sagas |
| **Days 7–8** | Streaming & Concurrency Engineering | Kafka Topic Topologies, OCC Implementation & Formal Correctness Proof |
| **Days 9–10** | Resilience, Fault Tolerance & APIs | 3-State Circuit Breakers, Bulkheads, OpenAPI 3.0 YAML Spec |
| **Days 11–13** | Verification, Capacity & Risk | Load Test Scripts, $40.8K Cost Model, 25-Point FMEA |
| **Days 14–15** | Polish, Self-Assessment & ARB Defense | ARB Slide Deck, Complete Rubric Review, Final Defense |
