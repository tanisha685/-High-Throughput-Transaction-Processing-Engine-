# ADR-002: Selection of Distributed PostgreSQL 16 with Hash-Based Sharding for Transaction Storage

## Status
Accepted

## Context
PayScale's legacy transaction processing architecture relies on a single PostgreSQL 15 primary database instance (running on an `m5.2xlarge` instance) with a hard cap of 200 client connections. During pre-festive load testing simulating 50,000 concurrent users at 1,800 TPS, the database suffered:
- Complete connection pool exhaustion with query queue depths exceeding 500.
- High row-level locking contention on the `accounts` table resulting in a 15% transaction deadlock rate.
- Average write latencies climbing from 12ms to over 280ms under high concurrency.

To meet the Diwali surge SLA of 12,000 sustained TPS (< 100ms p99 latency, 99.99% availability, RTO < 30s, RPO = 0), PayScale requires a horizontally scalable transactional database architecture that maintains strict financial ACID guarantees, prevents double-spending, and complies with the Reserve Bank of India (RBI) 2-year hot data retention mandate.

## Decision
We will deploy a **Distributed Sharded PostgreSQL 16 Architecture** consisting of **4 Application-Level Hash Shards (3 nodes per shard: 1 Primary + 2 Synchronous Standbys)** managed by **Patroni with Raft-backed HA** and **PgBouncer** connection poolers.

### Topology & Configuration Details:
- **Shard Topology:** 4 independent PostgreSQL database clusters, each comprising 1 Primary + 2 Standby replicas deployed across 3 AWS Availability Zones (`ap-south-1a`, `ap-south-1b`, `ap-south-1c`).
- **Compute Sizing:** 12 x `r6g.2xlarge` instances (8 vCPU, 64 GB RAM, 10 Gbps network) with provisioned IOPS SSD (`io2`, 10,000 IOPS per primary).
- **Sharding Key:** `account_id` hash (`abs(hash(account_id)) % 4`), ensuring 100% of single-account balance checks and debits execute as lightning-fast local single-shard transactions.
- **Connection Multiplexing:** Distributed PgBouncer instances running in transaction pooling mode, enabling over 2,000 active client connections to share 100 dedicated PostgreSQL backend processes per shard.
- **Replication Mode:** Synchronous replication (`synchronous_commit = on`, `synchronous_standby_names = 'FIRST 1 (standby1, standby2)'`), guaranteeing RPO = 0 on single-node failure.
- **Auto-Failover:** Patroni cluster manager orchestrating leader election in < 15 seconds (well within our 30-second RTO SLA).

## Alternatives Considered

| Evaluation Criteria | PostgreSQL 16 + Citus/Hash Shards (Selected) | CockroachDB v23.2 | TiDB v7.5 |
| :--- | :--- | :--- | :--- |
| **Write Latency (p99)**| **< 15 ms (Direct NVMe WAL commit)** | 40-75 ms (Multi-Raft Consensus overhead) | 25-45 ms (Distributed TiKV write path) |
| **ACID Strictness** | Full ACID per shard; Saga for cross-shard | Global Serializable ACID | Snapshot & Serializable Isolation |
| **Team Skillset Fit** | **100% Native (Existing SQL, triggers, DDL)**| ~75% (PostgreSQL dialect idiosyncrasies)| ~60% (MySQL dialect requires query rewrites)|
| **Operational Control**| High (Standard Linux, pg_dump, WAL-G) | Medium (Black-box distributed engine) | Low (Multi-component: PD, TiDB, TiKV) |
| **Monthly Cost (12K TPS)**| **~$14,400 / month (EC2 compute + storage)**| ~$26,000 / month (Enterprise node license)| ~$19,500 / month (High node footprint) |

- **CockroachDB:** Evaluated for its built-in distributed ACID transactions. However, CockroachDB’s distributed Raft consensus on every single range write introduces a p99 latency overhead of 40–75ms, which exhausts our strict 100ms end-to-end performance budget. Furthermore, commercial enterprise licensing exceeds our $45K monthly infrastructure budget ceiling.
- **TiDB:** Evaluated for horizontal scalability, but rejected due to MySQL dialect incompatibility requiring significant code rewrites within the 15-day sprint window, alongside heavy operational complexity.

## Consequences

### Positive:
- **Sub-15ms Write Latency:** Local shard commits bypass distributed consensus overhead for single-account operations.
- **Predictable Cost:** Open-source PostgreSQL on AWS EC2 eliminates recurring per-core vendor software licensing costs.
- **Linear Scaling:** Throughput can be doubled to 24,000 TPS by doubling shard count from 4 to 8 without rewriting business logic.

### Negative & Trade-offs:
- Cross-shard transactions (e.g., transfers between Account on Shard 1 and Account on Shard 3) cannot execute as single-phase database transactions; they require orchestration via the Distributed Saga Pattern.
- Schema migrations must be applied uniformly across all 4 database shards using Flyway/Liquibase migration tooling.

## Compliance & Regulatory Alignment
- **RBI Data Localization (2018):** All database shards, WAL archives, and automated daily backups are physically constrained to the AWS Mumbai (`ap-south-1`) region.
- **PCI-DSS v4.0:** Data-at-rest is encrypted with AWS KMS using AES-256; data-in-transit is secured via TLS 1.3 with enforced client certificate validation. Audit tables maintain immutable records for 2+ years.
