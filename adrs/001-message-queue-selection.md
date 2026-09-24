# ADR-001: Selection of Apache Kafka for Event Streaming & Asynchronous Transaction Processing

## Status
Accepted

## Context
PayScale Financial Technologies is re-architecting its transaction processing pipeline to scale from a legacy baseline of 1,200 TPS to a target sustained throughput of 12,000+ TPS (burst capacity up to 18,000 TPS). Under the current single-node RabbitMQ setup, message consumer lag spikes beyond 30 seconds at 2,000 TPS, and thread pool contention leads to severe memory alarms.

Our transaction processing lifecycle requires:
1. High-throughput ingestion (> 36,000 events/sec across transaction events, outbox notifications, ledger entries, and audit logs).
2. Strict per-account chronological ordering to prevent race conditions during balance state changes.
3. Exactly-Once Semantics (EOS) to prevent duplicate processing during network hiccups or consumer rebalancing.
4. An immutable event log capable of retaining event history for audit replay and dead-letter queue (DLQ) inspection.
5. Operating within a total monthly infrastructure budget ceiling of $45,000/month in the AWS Mumbai (`ap-south-1`) region.

## Decision
We will deploy a self-hosted **Apache Kafka 3.6 cluster running in KRaft mode (ZooKeeper-less)** across 3 AWS Availability Zones (`ap-south-1a`, `ap-south-1b`, `ap-south-1c`).

### Topology & Configuration Details:
- **Broker Topology:** 3 x `r6g.2xlarge` instances (8 vCPU, 64 GB RAM, 10 Gbps network, provisioned with 1 TB gp3 NVMe SSD per broker).
- **Partitioning Strategy:** 48 partitions for the primary `transaction-events` topic, providing uniform distribution across consumers with key-based partitioning using `account_id` hash.
- **Replication:** `replication.factor = 3`, `min.insync.replicas = 2`, and producer setting `acks = all` (`-1`) to guarantee zero message loss upon single broker failure.
- **Idempotence & EOS:** Producers configured with `enable.idempotence = true`, coupled with the Transactional Outbox Pattern and Debezium CDC for database-to-Kafka synchronization.
- **Retention:** 7-day retention for transaction and saga events; compacted log retention for account balance snapshot events.

## Alternatives Considered

| Evaluation Criteria | Apache Kafka 3.6 (Selected) | RabbitMQ 3.12 (Quorum Queues) | AWS Amazon SQS + SNS FIFO |
| :--- | :--- | :--- | :--- |
| **Throughput Capacity** | > 150,000 msgs/sec per cluster | Degrades significantly above 8,000 TPS | 3,000 msgs/sec limit per FIFO queue group |
| **Message Ordering** | Strict per-partition ordering via `account_id` | Complex competing consumer ordering | Ordering per message group ID |
| **Replay & Auditability** | Native offset replay (7+ days retention) | Destructive reads; no native event replay | Destructive reads; max 14 days retention |
| **Exactly-Once Delivery** | Native Transactional Producer + EOS | Requires manual application deduplication | Supported via message deduplication ID |
| **Monthly Cost (at 12K TPS)** | **~$3,600 / month** (3 EC2 nodes + EBS) | ~$3,200 / month | **~$11,800 / month** (High API call volume) |

- **RabbitMQ:** Rejected because its internal queue contention and Erlang mailbox memory overhead cannot sustain 18,000 TPS burst without severe consumer lag. Destructive read behavior prevents event stream replay for audit and reconciliation.
- **Amazon SQS/SNS FIFO:** Rejected due to prohibitive API request costs ($0.50 per million requests = ~$11,800/mo at 31 billion monthly operations) and rigid throughput quotas that would constrain burst traffic.

## Consequences

### Positive:
- **Horizontal Scalability:** Kafka's partition model enables seamless horizontal scale by adding consumer pods up to 48 concurrent workers.
- **Strict Ordering:** All state modifications for any individual account are serialized onto a single partition, eliminating distributed locking overhead in downstream consumers.
- **Resilience:** Loss of any single broker causes zero data loss and automated partition leader failover in < 2 seconds.

### Negative & Trade-offs:
- Requires dedicated operational monitoring of consumer lag and partition rebalancing events.
- Client applications must handle partition rebalance listeners gracefully using cooperative sticky assignors (`CooperativeStickyAssignor`).

## Compliance & Regulatory Alignment
- **RBI Data Residency (2018):** Kafka brokers and EBS storage volumes are strictly deployed in AWS Mumbai (`ap-south-1`), ensuring no payment event data crosses Indian borders.
- **PCI-DSS v4.0:** Inter-broker communication and client-to-broker connections are encrypted using TLS 1.3 with mTLS authentication. Sensitive payload fields (such as card/PAN numbers) are tokenized before publication to Kafka topics.
