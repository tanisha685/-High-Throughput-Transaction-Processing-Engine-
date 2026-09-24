# High-Throughput Transaction Processing Engine (HTTPE)
## Codename: TRANSACTION TITAN — The Scale Architect
**Organization:** PayScale Financial Technologies (Mumbai, India)  
**Target:** 12,000+ Transactions Per Second (TPS) with Sub-100ms p99 Latency & 99.99% Availability  
**Prepared For:** Architecture Review Board (ARB) & Zetheta Algorithms Evaluation  
**Project Timeline:** 15-Day Accelerated Engineering Sprint  

---

### ⚠️ Confidentiality & Academic Integrity Notice
> **STRICTLY PRIVATE AND CONFIDENTIAL — NOT FOR PUBLIC CIRCULATION**  
> This project and its contents are designed, developed, and administered for the assessment of distributed systems and financial technology infrastructure engineering. All architectural innovations, sharding algorithms, fault tolerance patterns, and simulation concepts are proprietary to **PayScale Financial Technologies / Zetheta Algorithms Private Limited**.

---

## 🏛️ Executive Summary & Mission Brief

PayScale Financial Technologies is a Series-B neo-banking platform operating in Mumbai, India, serving over 12 million Monthly Active Users (MAU) with daily transaction volumes exceeding 28 million. With the upcoming **Diwali Festive Season Flash Sale**, transaction volume is projected to surge **10x** from **1,200 peak TPS to 12,000+ TPS** (burst capacity up to 18,000 TPS).

Our legacy monolithic architecture (PostgreSQL 15 single primary, RabbitMQ single node, synchronous REST chains) suffers severe bottlenecks:
- **Connection pool exhaustion** at 1,800 TPS (queue depth > 500)
- **Deadlocks and row contention** on account tables (15% deadlock rate)
- **Message backlog** and consumer lag > 30s at 2,000 TPS
- **Thread pool saturation** causing 40% request timeouts

This repository houses the **production-grade enterprise distributed architecture redesign** built to achieve:
1. **12,000 TPS sustained / 18,000 TPS peak burst**
2. **Sub-30ms p50, sub-100ms p99 latency** end-to-end
3. **99.99% High Availability (<52.6 minutes downtime/year)** with 30-second RTO
4. **Zero Data Loss (RPO = 0)** via Write-Ahead Logging (WAL) and Kafka transactional outbox
5. **100% RBI Compliance** (Data Localization within India, 2-year hot data retention, KYC/audit trails)
6. **Strict Budget Adherence** ($40,850/month against a $45,000/month ceiling)

---

## 📂 Repository Structure

```text
├── README.md                           # Master project guide, system overview & navigation
├── SELF-ASSESSMENT.md                  # 1000-point rubric self-evaluation & grading sheet
├── REFLECTION.md                       # Senior engineering reflection on trade-offs & learnings
├── adrs/                               # Architecture Decision Records (Format: Context, Decision, Consequences, Compliance)
│   ├── 001-message-queue-selection.md  # Apache Kafka vs RabbitMQ vs Amazon SQS
│   ├── 002-database-selection.md       # Distributed PostgreSQL (Citus) vs CockroachDB vs TiDB
│   ├── 003-sharding-strategy.md        # Hash-based sharding on account_id with virtual vnodes
│   ├── 004-communication-pattern.md    # Asynchronous Event-Driven (Outbox Pattern) vs Sync REST
│   └── 005-cache-invalidation.md       # Write-Through + Cache-Aside with Distributed Invalidation
├── api/
│   └── openapi.yaml                    # Production OpenAPI 3.0 Specification (valid Swagger)
├── diagrams/                           # Architecture, sequence, and state diagrams
│   ├── system-architecture.drawio      # 13-Component High-Level Architecture Source
│   ├── system-architecture.png         # Exported architecture topology diagram
│   ├── p2p-payment-flow.puml           # PlantUML sequence diagram for P2P transaction saga
│   ├── batch-settlement-flow.puml      # PlantUML sequence diagram for batch merchant settlement
│   ├── failover-flow.puml              # PlantUML sequence diagram for automated DB failover
│   └── circuit-breaker-fsm.puml        # PlantUML finite state machine for 3-state circuit breakers
├── docs/                               # 15-Day Structured Engineering Documentation
│   ├── 01-scenario-analysis.md         # Day 1: PayScale scenario & 8 load test bottlenecks
│   ├── 02-technology-evaluation.md     # Day 2: Tech stack evaluation matrices with scoring
│   ├── 03-high-level-design.md         # Day 3: High-Level Design (HLD) for 13 components
│   ├── 04-data-flow-design.md          # Day 4: Synchronous vs Asynchronous data flows & timeouts
│   ├── 05-database-schema.md           # Day 5: Production DDLs, indexing & range partitioning
│   ├── 06-sharding-strategy.md         # Day 6: 4-Shard topology, consistent hashing & cross-shard sagas
│   ├── 07-message-queue-topology.md    # Day 7: Kafka topic topology, partition math & EOS
│   ├── 08-concurrency-control.md       # Day 8: OCC version vectors, formal correctness proof & CAS
│   ├── 09-fault-tolerance.md           # Day 9: Circuit breakers, bulkheads, rate limits & retries
│   ├── 10-api-specification.md         # Day 10: API endpoints, pagination, tier rate limits & errors
│   ├── 11-load-testing-strategy.md     # Day 11: 8 Load test scenarios, pass/fail metrics & observability
│   ├── 12-capacity-planning.md         # Day 12: Compute, storage, memory & AWS cost model ($40.8K/mo)
│   ├── 13-fmea.md                      # Day 13: 25 Failure modes with RPN analysis & mitigations
│   ├── 14-architecture-review-deck.md  # Day 14: ARB 15-minute presentation deck & executive summary
│   └── 15-arb-defense-preparation.md   # Day 15: Deep-dive answers & proofs for ARB Q1-Q10
├── load-tests/
│   ├── performance-budget.md           # Sub-100ms p99 latency allocation breakdown
│   └── scenarios/
│       ├── k6-target-load.js           # k6 script for 12,000 TPS target load test
│       ├── locust-mixed-workload.py    # Locust script for mixed workload distribution
│       └── k6-failover-chaos.js        # k6 chaos injection & failover test
├── pseudocode/                         # Production-grade implementations
│   ├── occ-balance-update.py           # Optimistic Concurrency Control with version checking & CAS
│   ├── saga-orchestrator.py            # Distributed Saga state machine with compensations
│   ├── circuit-breaker.py              # Robust 3-state Circuit Breaker with sliding window metrics
│   └── idempotency-handler.py          # Two-tier Redis + DB idempotency validation engine
├── schemas/
│   ├── ddl/                            # Complete PostgreSQL DDL scripts (Constraints, Indexes, Partitions)
│   │   ├── 001-accounts.sql
│   │   ├── 002-transactions.sql
│   │   ├── 003-ledger-entries.sql
│   │   ├── 004-users.sql
│   │   ├── 005-transaction-events.sql
│   │   ├── 006-fraud-rules.sql
│   │   ├── 007-merchant-settlements.sql
│   │   └── 008-notification-log.sql
│   └── erd/
│       └── erd-diagram.dbml            # DBML Database Entity-Relationship Diagram
└── simulation-app/                     # Interactive Gamified Simulation Web Application
    ├── index.html                      # Rich Single-Page Dashboard & Transaction Simulator
    ├── style.css                       # Modern Glassmorphism & High-Throughput Dark Theme UI
    └── app.js                          # Live TPS Engine, Chaos Injector, Metrics & Docs Viewer
```

---

## ⚡ Key Architecture Highlights

| Dimension | Legacy Monolith (Current) | Target Architecture (Redesign) | Justification / Mechanism |
| :--- | :--- | :--- | :--- |
| **Peak Throughput** | 1,200 TPS | **12,000+ TPS (18K burst)** | 4 DB shards, 48 Kafka partitions, OCC balance updates |
| **p99 Latency** | 450 ms | **< 100 ms** (p50 < 30 ms) | Redis hot cache, async ledger outbox, non-blocking I/O |
| **Database Tier** | PostgreSQL 15 Single Primary | **Distributed PostgreSQL / Citus (4 Shards x 3 nodes)** | Hash-based consistent sharding on `account_id` |
| **Event Streaming** | RabbitMQ Single Node | **Apache Kafka 3.6 (3 Brokers, RF=3)** | Transactional Outbox + Exactly-Once Semantics (EOS) |
| **Concurrency Control**| Pessimistic Row Locks (`SELECT FOR UPDATE`) | **Optimistic Concurrency Control (OCC) + Version Vectors** | Lock-free balance updates eliminates deadlocks (0% deadlock) |
| **Availability SLA** | 99.9% (8.76 hrs downtime/yr) | **99.99% (< 52.6 min downtime/yr)** | Patroni auto-failover (RTO < 30s), multi-AZ deployment |
| **Cost** | $12,000 / month | **$40,850 / month** | Under $45,000 budget ceiling in AWS Mumbai (`ap-south-1`) |
| **Compliance** | Partial | **100% RBI & PCI-DSS 4.0 Compliant** | Data localized in India, AES-256 at rest, TLS 1.3 in transit |

---

## 🚀 Quick Start: Running the Interactive Simulation App

To explore the **TRANSACTION TITAN** gamified simulation and inspect real-time metrics, chaos experiments, and system architecture:
1. Navigate to the `simulation-app/` directory.
2. Open `index.html` in any modern web browser or serve it using any local static server:
   ```bash
   npx serve simulation-app
   ```
3. Use the interactive controls to:
   - Ramp TPS from 1,200 to 18,000+
   - Inject faults (Kill Primary Shard, Spike Kafka Consumer Lag, Trip Fraud Circuit Breaker)
   - View real-time p50/p95/p99 latency charts, shard utilization, and Saga orchestration events!

---
*Created with architectural rigor by the PayScale Infrastructure Engineering Team for the Zetheta Systems Engineering Assessment.*
