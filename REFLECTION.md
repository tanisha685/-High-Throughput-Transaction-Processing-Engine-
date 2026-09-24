# Senior Engineering Reflection: Architecture Decisions & Trade-Offs
**Project:** PayScale High-Throughput Transaction Processing Engine (HTTPE)  
**Author:** Senior Infrastructure Architect  
**Word Count:** 580 Words  

---

## 1. Architectural Philosophy & Pragmatism Under Fire

Scaling PayScale’s financial backbone from a 1,200 TPS monolith to a 12,000+ TPS distributed engine for the Diwali Festive Surge within a 15-day sprint required absolute engineering discipline. The core challenge of high-throughput financial infrastructure is not merely handling request volume—it is maintaining unflinching mathematical correctness (conservation of money, zero double-spending, zero lost updates) while operating within strict latency, regulatory, and financial boundaries.

Every decision in this redesign reflects deliberate trade-off analysis between theoretical elegance and operational pragmatism.

---

## 2. Key Architectural Trade-Offs & Decisions

### 1. Optimistic Concurrency Control (OCC) vs. Pessimistic Row Locking
In our legacy monolith, `SELECT ... FOR UPDATE` was the primary source of catastrophic lock contention and a 15% deadlock rate. Moving to lock-free OCC with atomic Compare-And-Swap (CAS) version predicates fundamentally transformed our throughput characteristics. By eliminating database row latches on read and snapshot paths, we reduced transaction execution time from 85ms down to 12ms. For the small percentage of concurrent updates targeting the same account, jittered exponential backoff retries resolve contention in software without locking the underlying database pages.

### 2. Distributed Sharded PostgreSQL vs. Distributed SQL (CockroachDB)
While CockroachDB offers compelling distributed ACID abstractions out of the box, its multi-Raft consensus across WAN/cross-AZ hops introduces a 40–75ms p99 write latency penalty that would have completely exhausted our sub-100ms end-to-end performance budget. Furthermore, commercial licensing costs would have blown past our $45,000/month infrastructure ceiling. By selecting an application-level 4-shard PostgreSQL 16 topology with Patroni Raft HA, we achieved sub-15ms local write commits, zero recurring software license fees ($40,850/month total cost), and 100% dialect familiarity for our existing Java/Kotlin team.

### 3. Synchronous Critical Path vs. Asynchronous Decoupling
One of our most impactful decisions was isolating the user-facing critical path to just three synchronous steps: Token-Bucket Ingress -> Heuristic Fraud Scoring (< 15ms) -> Shard Balance Debit (< 12ms). All post-commit responsibilities—push notifications, SMS alerts, double-entry reconciliation streaming, and compliance archiving—were relegated to Apache Kafka using the Transactional Outbox Pattern with Debezium CDC. If downstream notification providers experience total outages, core payment authorization throughput remains unaffected at 12,000 TPS.

---

## 3. Regulatory Alignment & Indian FinTech Landscape

Designing for the Indian market demands strict adherence to Reserve Bank of India (RBI) mandates. Our architecture guarantees that:
- 100% of transaction data, cryptographic material, and logs physically reside within the AWS Mumbai (`ap-south-1`) and Hyderabad (`ap-south-2`) regions.
- Monthly time-range table partitioning satisfies the 2-year hot data retention rule while offloading older records to encrypted S3 Glacier Parquet storage.
- Sub-15ms fraud evaluation hooks comply with RBI Master Directions on real-time fraud monitoring.

---

## 4. Key Learnings & Future Evolution

This sprint demonstrated that true scalability is achieved by removing bottlenecks at their source rather than throwing excessive hardware at inefficient designs. By combining consistent hash sharding, lock-free OCC, asynchronous outbox streaming, and robust circuit breakers, PayScale is primed not only to survive the Diwali surge, but to scale effortlessly toward 24,000+ TPS in the future.
