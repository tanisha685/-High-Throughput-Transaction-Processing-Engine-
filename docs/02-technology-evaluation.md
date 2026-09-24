# Day 2: Technology Evaluation & Trade-Off Matrix
**Project:** PayScale High-Throughput Transaction Processing Engine (HTTPE)  
**Author:** Senior Infrastructure Architect  
**Deliverable:** Comprehensive technology comparative evaluation matrix across Core Tiers  

---

## 1. Evaluation Methodology & Scoring Framework

To select technologies objectively for PayScale's 12,000+ TPS engine, we employ a weighted multi-criteria decision matrix (MCDM). Each technology candidate is evaluated on a scale of 1 to 5 across five critical dimensions:

- **Performance & Scalability (Weight: 30%):** Sustained throughput ceiling, p99 latency guarantees, concurrency support, and scaling linearity.
- **Operational Complexity (Weight: 20%):** Day-2 operations, failover automation, clustering overhead, backup/restore, observability.
- **Cost Efficiency (Weight: 20%):** Licensing, infrastructure resource footprint, egress costs, maintenance overhead.
- **Team Expertise Compatibility (Weight: 20%):** Alignment with PayScale’s existing Java/Kotlin, PostgreSQL, and Linux skillset to meet the 15-day launch deadline.
- **Ecosystem & Regulatory Fit (Weight: 10%):** Community maturity, tooling, RBI data residency support, PCI-DSS compliance posture.

$$\text{Total Score} = \sum (\text{Dimension Score} \times \text{Weight})$$

---

## 2. Deep-Dive Tier Evaluations

### 2.1 Database Tier (Relational & Distributed SQL)

The database tier is the primary bottleneck in the legacy system. It must provide strict ACID guarantees, support 12,000+ write TPS, and offer horizontal scaling without cross-AZ performance penalties.

| Evaluation Dimension | PostgreSQL 16 + Citus (Winner) | CockroachDB v23.2 | TiDB v7.5 | MongoDB 7.0 (Sharded) |
| :--- | :--- | :--- | :--- | :--- |
| **Architecture Type** | Distributed PostgreSQL (Shared-nothing sharding) | Distributed SQL (Raft + Spanner-inspired) | Distributed SQL (Raft + TiKV storage engine) | Document Store (Distributed replica sets) |
| **ACID Guarantees** | Full ACID (Single & Multi-shard) | Full Serializable ACID (Global Raft) | Snapshot & Serializable ACID | Multi-document ACID (heavy overhead) |
| **Write Throughput (12K TPS)** | 4.8 / 5 (Linearly scalable with hash shards) | 4.2 / 5 (Raft consensus adds write latency) | 4.4 / 5 (Excellent throughput via TiKV) | 3.8 / 5 (High throughput, poor multi-doc ACID) |
| **p99 Write Latency** | **4.7 / 5 (< 15ms with local SSD)** | 3.5 / 5 (30-65ms due to multi-Raft sync) | 4.0 / 5 (20-35ms) | 3.5 / 5 (Variable under lock contention) |
| **Operational Complexity** | 4.2 / 5 (Standard PG tooling, Patroni) | 4.5 / 5 (Single binary, self-healing) | 3.2 / 5 (Complex: PD, TiDB, TiKV components)| 3.8 / 5 (Config servers, mongos routers) |
| **Cost at Target Scale** | 4.5 / 5 (Open-source, self-hosted on EC2) | 2.5 / 5 (High commercial license cost) | 3.8 / 5 (High memory & CPU footprint) | 3.5 / 5 (High memory requirements) |
| **Team Expertise Fit** | **5.0 / 5 (100% native PostgreSQL SQL/PLpgSQL)**| 3.8 / 5 (PostgreSQL wire compatible, dialect quirks)| 3.0 / 5 (MySQL dialect requires query rewrites)| 2.0 / 5 (NoSQL paradigm mismatch) |
| **RBI Data Residency** | 5.0 / 5 (Full control over AWS Mumbai deployment)| 5.0 / 5 (Supports multi-region pinning) | 4.5 / 5 (Region-aware placement) | 4.5 / 5 (Zone sharding supported) |
| **WEIGHTED TOTAL SCORE** | **4.64 / 5.0** | **3.89 / 5.0** | **3.76 / 5.0** | **3.31 / 5.0** |

**Selection Rationale:**  
PostgreSQL + Citus extension (or application-level hash sharding across independent PostgreSQL 16 nodes managed by Patroni) emerged as the decisive winner. It delivers sub-15ms p99 write latency, eliminates dialect translation risks for our Java/Kotlin team, and fits comfortably within the $45,000/month infrastructure budget.

---

### 2.2 Message Queue & Event Streaming Tier

The messaging tier must handle asynchronous saga events, outbox CDC streaming, ledger replication, and webhook delivery at > 30,000 messages/sec.

| Evaluation Dimension | Apache Kafka 3.6 (Winner) | RabbitMQ 3.12 (Quorum) | Apache Pulsar 3.1 | AWS Amazon SQS + SNS |
| :--- | :--- | :--- | :--- | :--- |
| **Messaging Paradigm** | Distributed Append-Only Log | AMQP Broker with Queues | Tiered Storage Distributed Log | Managed Cloud Queue (FIFO) |
| **Throughput Ceiling** | **5.0 / 5 (100K+ msgs/sec effortlessly)** | 3.0 / 5 (Struggles beyond 5,000 TPS ACK load)| 4.8 / 5 (High throughput) | 3.2 / 5 (3,000 msgs/s FIFO limit) |
| **Exactly-Once Semantics (EOS)**| **5.0 / 5 (Idempotent producers + Txn API)** | 2.5 / 5 (At-least-once with manual dedupe) | 4.5 / 5 (Transactional support) | 3.0 / 5 (Deduplication IDs in FIFO) |
| **Consumer Scalability** | **5.0 / 5 (Partition-based consumer groups)** | 3.0 / 5 (Queue locking on concurrent consumers)| 4.8 / 5 (Key_Shared & Failover modes) | 3.5 / 5 (Polling worker contention) |
| **Operational Complexity** | 4.0 / 5 (KRaft mode removes ZooKeeper) | 4.2 / 5 (Erlang runtime, cluster sync) | 2.5 / 5 (Requires BookKeeper + ZooKeeper) | **5.0 / 5 (Fully serverless managed)** |
| **Monthly Cost (at 12K TPS)** | 4.5 / 5 (~$3,600/mo self-hosted on AWS EC2) | 4.2 / 5 (~$3,200/mo) | 3.0 / 5 (~$6,500/mo due to BookKeeper) | 2.0 / 5 (~$11,500/mo SQS request API charges)|
| **Team Expertise Fit** | 4.5 / 5 (Standard Spring Kafka / Kotlin drivers)| 4.0 / 5 (Currently in legacy monolith) | 2.5 / 5 (Steep learning curve) | 4.5 / 5 (Standard AWS SDK) |
| **WEIGHTED TOTAL SCORE** | **4.65 / 5.0** | **3.37 / 5.0** | **3.84 / 5.0** | **3.46 / 5.0** |

**Selection Rationale:**  
Apache Kafka with KRaft consensus provides unbeatable throughput, native Exactly-Once Semantics (EOS), partition-key ordered processing per `account_id`, and predictable fixed compute costs.

---

### 2.3 Caching & In-Memory State Tier

The caching layer handles 24-hour transaction idempotency keys, hot account balance snapshots, and distributed rate limiting counters.

| Evaluation Dimension | Redis Cluster 7.2 (Winner) | Memcached 1.6 | Hazelcast IMDG 5.3 | Aerospike 6.4 |
| :--- | :--- | :--- | :--- | :--- |
| **Data Structures** | Strings, Hashes, Bitmaps, Streams, Lua | Simple Key-Value (String/Binary)| Distributed Maps, Locks, Queues | Hybrid In-Memory/Flash Records |
| **Sub-millisecond Latency**| **5.0 / 5 (< 1.2ms p99)** | 5.0 / 5 (< 1.0ms p99) | 4.5 / 5 (< 2.5ms p99) | 4.8 / 5 (< 1.5ms p99) |
| **High Availability & Failover**| 4.8 / 5 (Native cluster master-replica auto-failover)| 2.0 / 5 (No native replication) | 4.8 / 5 (Partitioned backup copies) | 4.8 / 5 (Auto-clustering & replication)|
| **Atomicity & Scripting** | **5.0 / 5 (Atomic Lua scripts, Multi/Exec)**| 2.5 / 5 (Atomic increment only) | 4.5 / 5 (EntryProcessors) | 4.0 / 5 (UDF Lua support) |
| **Cost & Resource Usage** | 4.5 / 5 (Memory efficient, Redis Cluster on EC2)| 4.5 / 5 (Low memory overhead) | 3.0 / 5 (Heavy JVM memory overhead)| 3.5 / 5 (Enterprise licensing high) |
| **Team Expertise Fit** | 5.0 / 5 (Extensively used in Java/Kotlin stack)| 4.5 / 5 (Simple API) | 3.5 / 5 (Java-centric, complex config)| 2.5 / 5 (Specialized client drivers) |
| **WEIGHTED TOTAL SCORE** | **4.84 / 5.0** | **3.65 / 5.0** | **4.08 / 5.0** | **3.94 / 5.0** |

**Selection Rationale:**  
Redis Cluster 7.2 provides multi-master sharding (16,384 hash slots), sub-millisecond atomic operations via Lua (essential for token-bucket rate limiting and CAS balance assertions), and proven reliability.

---

### 2.4 API Gateway & Ingress Layer

| Evaluation Dimension | Kong Gateway (Envoy/OpenResty) (Winner) | AWS API Gateway | Traefik Enterprise |
| :--- | :--- | :--- | :--- |
| **Throughput & Latency** | **4.9 / 5 (< 3ms p99 overhead via C/Lua)** | 3.0 / 5 (15-30ms p99, regional throttles) | 4.5 / 5 (5-8ms p99 Go runtime) |
| **Custom Plugins & Rate Limiting**| 5.0 / 5 (Dynamic Lua/Go plugins, Redis token bucket)| 3.5 / 5 (Basic WAF and usage plans) | 4.2 / 5 (Middleware plugins) |
| **Cost at 12K TPS (31B calls/mo)**| **4.8 / 5 (~$1,200/mo on 4x EC2 instances)** | 1.0 / 5 (~$35,000/mo - violates budget!) | 4.5 / 5 (~$1,500/mo) |
| **Canary & Traffic Control** | 4.8 / 5 (Weight-based routing, mTLS) | 4.5 / 5 (Stage variables, Canary) | 4.6 / 5 (Weighted Round Robin) |
| **WEIGHTED TOTAL SCORE** | **4.82 / 5.0** | **2.65 / 5.0** | **4.49 / 5.0** |

---

## 3. Technology Matrix Synthesis & Decision Summary

```
+-----------------------------------------------------------------------------------------------+
|                               PAYSCALE HTTPE TARGET TECHNOLOGY STACK                          |
+-----------------------------------------------------------------------------------------------+
|  Architecture Layer          Chosen Technology                Key Driver                      |
|  Ingress & API Gateway       Kong Gateway (Envoy Core)        < 3ms p99, Low Cost at 31B reqs |
|  Application Framework       Kotlin 1.9 / Java 21 (Loom)      High Concurrency Virtual Threads|
|  Distributed Database        PostgreSQL 16 + Hash Shards      ACID, OCC Versioning, Zero Risk |
|  Database Failover & High Av Patroni + Raft Consensus         Automated Failover (RTO < 30s)  |
|  Connection Pooling          PgBouncer (Transaction Mode)     2,000+ Client Mux onto 100 conns|
|  Event Streaming Bus         Apache Kafka 3.6 (KRaft)         Partition Scalability & EOS     |
|  Distributed Cache           Redis Cluster 7.2 (6 nodes)      < 1.2ms Idempotency & Rate Limit|
|  Observability & Tracing     Prometheus + Grafana + OTel      Sub-second Metrics & W3C Traces |
+-----------------------------------------------------------------------------------------------+
```
