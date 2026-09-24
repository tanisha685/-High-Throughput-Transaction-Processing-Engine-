# Day 14: Architecture Review Board (ARB) Presentation Deck
**Project:** PayScale High-Throughput Transaction Processing Engine (HTTPE)  
**Presenter:** Senior Infrastructure Architect  
**Format:** 15-Minute Capstone ARB Presentation + 20-Minute Technical Defense  

---

## 1. Presentation Structure & Time Allocation (15 Minutes Total)

```
[ Slide 1: Mission & Challenge (2m) ] ──> [ Slide 2: 13-Component HLD (3m) ] ──> [ Slide 3: Storage & Sharding (3m) ]
                                                                                               │
[ Slide 6: ARB Verdict & Wrap-Up (1m) ] <── [ Slide 5: Resilience & FMEA (3m) ] <── [ Slide 4: Concurrency & OCC (3m) ]
```

---

## 2. Slide-by-Slide Script & Visual Walkthrough

### Slide 1: The Diwali Scaling Challenge & Legacy Collapse
- **Speaker Script (00:00 - 02:00):**
  "Good morning members of the Architecture Review Board. In 15 days, PayScale launches its Diwali festive campaign, projecting a 10x surge from 1,200 TPS to 12,000+ sustained TPS and 18,000 peak TPS. Our Locust benchmark proved that our legacy monolith collapses at 1,800 TPS due to connection pool exhaustion, a 15% database deadlock rate on account tables, and message queues lagging over 30 seconds. Today, I present our distributed architecture redesign built to achieve sub-100ms p99 latency, 99.99% availability, and 100% RBI data residency compliance—all within our $45,000 monthly budget ceiling."

### Slide 2: High-Level Architecture & Clean Asynchronous Decoupling
- **Speaker Script (02:00 - 05:00):**
  "Our high-level architecture comprises 13 decoupled microservices. We strictly isolate the user-facing critical path to under 35ms: Kong API Gateway -> Fraud ML Scoring (< 15ms) -> Local Shard OCC Balance Debit (< 12ms) -> Immediate HTTP 200 return. All secondary concerns—push alerts, SMS, continuous double-entry ledger audits, and compliance archiving—are decoupled via Apache Kafka using the Transactional Outbox Pattern with Debezium CDC. If third-party SMS providers suffer complete blackouts, our core payment processing operates at full 12,000 TPS capacity."

### Slide 3: Storage Tier: 4-Shard PostgreSQL Topology with Patroni HA
- **Speaker Script (05:00 - 08:00):**
  "To eliminate database write contention, we horizontally partition data into 4 PostgreSQL 16 shards using hash-based sharding on `account_id` with 1,024 virtual vnodes. This yields a uniform mathematical distribution with less than 0.05% variance. For high availability, Patroni orchestrates Raft-backed automated failover in under 15 seconds, well within our 30-second RTO SLA, with zero data loss (RPO = 0). Monthly range partitioning guarantees compliance with the RBI 2-year hot data retention mandate."

### Slide 4: Concurrency Control: Lock-Free OCC & Write-Skew Prevention
- **Speaker Script (08:00 - 11:00):**
  "To eliminate the 15% deadlock rate, we replaced pessimistic row locking with Optimistic Concurrency Control (OCC) using monotonic version counters and atomic Compare-And-Swap (CAS) SQL predicates. We have mathematically proven that concurrent debits targeting the same account cannot overdraft or create write-skew anomalies. To protect high-volume merchant accounts from hot-spot contention, we partition merchant balances across 16 sub-balance buckets."

### Slide 5: Fault Tolerance, Chaos Engineering & Budgetary Discipline
- **Speaker Script (11:00 - 14:00):**
  "We engineered 7 specialized 3-state circuit breakers, bulkheaded worker thread pools, and verified system resilience through 5 chaos experiments. Our 25-point FMEA risk register mitigates all high-RPN failure modes. Economically, our 12,000 TPS infrastructure is priced out in AWS Mumbai at $40,850/month—leaving a 9.2% ($4,150/mo) surplus under our $45K budget ceiling."

### Slide 6: Conclusion & ARB Defense Open
- **Speaker Script (14:00 - 15:00):**
  "In summary, this architecture transforms PayScale from a fragile monolith into an enterprise-grade financial engine capable of scaling effortlessly to 24,000+ TPS in future years. I welcome the Board's questions."
