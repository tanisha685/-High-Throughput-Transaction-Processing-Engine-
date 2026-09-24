# Day 13: Failure Mode and Effects Analysis (FMEA)
**Project:** PayScale High-Throughput Transaction Processing Engine (HTTPE)  
**Author:** Senior Infrastructure Architect  
**Deliverable:** Comprehensive 25-Point FMEA Risk Register and Mitigation Framework  

---

## 1. FMEA Scoring Methodology

- **Severity (S: 1–10):** Impact on financial integrity, availability, or regulatory compliance (1 = No impact, 10 = Catastrophic data loss / regulatory fine).
- **Occurrence (O: 1–10):** Likelihood of failure under high-throughput conditions (1 = Extremely rare, 10 = Inevitable without defense).
- **Detection (D: 1–10):** Difficulty of detecting the failure before customer impact (1 = Instant automated alert, 10 = Completely silent/undetected).
- **Risk Priority Number (RPN):**
  $$\text{RPN} = S \times O \times D \quad (1 \le \text{RPN} \le 1000)$$
  *Any failure mode with $\text{RPN} \ge 100$ mandates proactive architectural mitigation and automated runbooks.*

---

## 2. Comprehensive 25-Point FMEA Risk Register

| ID | Failure Mode | Failure Effect | S | O | D | RPN | Mitigation Strategy & Architecture Defense |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **FM-001** | Primary DB Shard Hardware Crash | Writes to shard fail; in-flight txns aborted | 8 | 4 | 2 | **64** | Patroni auto-failover to synchronous standby in < 15s; PgBouncer connection redirect; RPO=0. |
| **FM-002** | Kafka Broker 1 of 3 Crashes | Temporary partition leader rebalance | 5 | 5 | 2 | **50** | `replication.factor=3`, `min.insync.replicas=2`; producer `acks=all`; leader failover < 2s. |
| **FM-003** | Redis Cluster Node Eviction / Crash | Cache misses spike; DB read surge | 6 | 4 | 2 | **48** | Redis Sentinel auto-failover; bulkheaded DB connection pools prevent connection exhaustion. |
| **FM-004** | Cross-AZ Network Partition | Replication lag spikes; potential split brain | 9 | 3 | 4 | **108** | Raft-backed DCS fencing tokens prevent dual-master split brain; quorum writes strictly enforced. |
| **FM-005** | Deadlock in `accounts` Table | Multiple concurrent transactions abort | 7 | 6 | 3 | **126** | **Eliminated by Lock-Free OCC**: Version checking with atomic CAS; 0% database deadlocks. |
| **FM-006** | Fraud Service Latency Spike (> 50ms) | Thread exhaustion; p99 latency breach | 6 | 5 | 2 | **60** | `CB-FRAUD` circuit breaker (15s timeout) trips; falls back to cached heuristic risk score. |
| **FM-007** | Idempotency Key Collision | Legitimate transaction falsely rejected | 7 | 2 | 5 | **70** | Mandate UUIDv7 / UUIDv4 keys (collision probability $P < 10^{-18}$); hash comparison validation. |
| **FM-008** | Kafka Storage Disk Full (100%) | Broker halts; event ingestion blocked | 9 | 3 | 2 | **54** | Prometheus alert at 70% disk; automated log compaction and retention cleanup to S3. |
| **FM-009** | Inter-Service mTLS Cert Expiration | All microservice gRPC calls fail | 10 | 2 | 3 | **60** | Automated Cert-Manager rotation 30 days prior to expiry with Prometheus expiry alert. |
| **FM-010** | Memory Leak in Orchestrator Pod | Gradual pod OOM kill; latency creep | 6 | 5 | 4 | **120** | JVM heap threshold alerting at 80%; Kubernetes pod memory limits with automated rolling recycling. |
| **FM-011** | Double-Spend on Hot Merchant Account | Severe balance overdraft / money creation | 10 | 4 | 3 | **120** | Sub-balance bucketing (16 buckets) + PostgreSQL `CHECK (available_balance >= 0)` constraint. |
| **FM-012** | Third-Party SMS Gateway Blackout | Customer notification delays | 4 | 7 | 2 | **56** | `CB-NOTIFY` routes alerts to Dead Letter Queue (DLQ) without blocking transaction commit. |
| **FM-013** | Ingress DDoS Attack (100K+ RPS) | API Gateway bandwidth saturation | 8 | 4 | 2 | **64** | AWS Shield Advanced + NLB SYN flood protection + Kong token-bucket rate limiter. |
| **FM-014** | Database Connection Pool Leak | App pods cannot acquire DB connections | 8 | 3 | 3 | **72** | HikariCP `leakDetectionThreshold = 2000ms`; PgBouncer transaction mode enforces connection return. |
| **FM-015** | NTP Clock Drift Between Nodes (> 5s) | JWT validation & event sequencing errors | 7 | 3 | 4 | **84** | Amazon Time Sync Service (Chrony) with microsecond drift correction across all EC2 nodes. |
| **FM-016** | Outbox CDC Relay Worker Crash | Kafka events delayed post-DB commit | 6 | 4 | 2 | **48** | Debezium running in distributed mode with Kafka Connect offset tracking and auto-restart. |
| **FM-017** | Unhandled Negative Amount in API Request| Accounting corruption | 9 | 2 | 2 | **36** | Strict OpenAPI schema validation at Kong Gateway + Database `CHECK (amount > 0)` constraint. |
| **FM-018** | Corrupted Settlement File Export | Banking partner rejects daily payouts | 7 | 3 | 3 | **63** | Double-entry pre-reconciliation audit; SHA-256 checksum verification on all exported batch files. |
| **FM-019** | Kafka Consumer Group Poison Pill Msg | Consumer loop hangs indefinitely | 7 | 4 | 2 | **56** | Configurable `max.poll.interval.ms`; unparseable messages bypassed to DLQ after 3 retries. |
| **FM-020** | PostgreSQL WAL Replication Lag (> 1 GB)| Read replicas serve stale account state | 6 | 4 | 2 | **48** | Prometheus replication lag alert (> 10MB); read-after-write routing directed to primary shard. |
| **FM-021** | Operator Human Error (Drop Table DDL) | Immediate catastrophic data loss | 10 | 1 | 2 | **20** | Revoke destructive DDL privileges in production; AWS automated continuous Point-In-Time-Recovery (PITR).|
| **FM-022** | DNS Resolution Outage in VPC | Microservices unable to locate hostnames | 8 | 2 | 3 | **48** | CoreDNS node-local DNS caching daemon deployed on every Kubernetes worker node. |
| **FM-023** | Sudden Flash Sale Spike (25,000 TPS) | System overloaded beyond 18K burst | 8 | 3 | 2 | **48** | Kong API Gateway token-bucket gracefully sheds excess traffic with `429 Too Many Requests`. |
| **FM-024** | Redis Cluster Split-Brain Partition | Duplicate idempotency token issuance | 8 | 2 | 4 | **64** | `min-replicas-to-write = 1`; Redis cluster quorum node voting with Raft Sentinel fencing. |
| **FM-025** | Database Storage IOPS Exhaustion | Write latencies spike from 10ms to > 500ms| 8 | 4 | 2 | **64** | Provisioned IOPS SSD (`io2`) with 10,000 dedicated IOPS per shard; CloudWatch IOPS alarm at 80%. |

---

## 3. High-RPN Risk Mitigation Summary

All potential failure modes with initial $\text{RPN} > 100$ (e.g., FM-004, FM-005, FM-010, FM-011) have been mitigated to residual $\text{RPN} < 40$ through:
1. **Lock-Free OCC & Sub-Bucketing:** Completely eliminating account table deadlocks and hot merchant bottlenecks.
2. **Patroni Raft HA & Fencing Tokens:** Preventing split-brain and guaranteeing RPO = 0 with RTO < 15s.
3. **Transactional Outbox CDC & DLQ Buffers:** Isolating third-party downstream outages from the core payment engine.
