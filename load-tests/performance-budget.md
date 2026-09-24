# Performance Budget: Sub-100ms p99 Transaction Latency Allocation
**Target SLA:** 12,000 sustained TPS | p50 $\le$ 30ms | p99 $\le$ 100ms | p99.9 $\le$ 250ms  
**Environment:** AWS Mumbai (`ap-south-1`) VPC with Multi-AZ Placement  

---

## 1. Critical Path Latency Breakdown

Every single millisecond in the payment authorization path is budgeted and monitored via OpenTelemetry distributed tracing spans.

```
[ Ingress: 5ms ] -> [ Idempotency: 2ms ] -> [ Fraud ML: 15ms ] -> [ DB Read: 5ms ] -> [ OCC Write: 12ms ] -> [ Outbox/Net: 3ms ]
===================================================================================================================
Total Critical Path (Typical p50): 22 - 28 ms | Worst-Case (p99 with 1 OCC Retry): 45 - 58 ms (Well under 100ms SLA!)
```

| Processing Stage | p50 Budget (ms) | p99 Budget (ms) | Justification & Optimization Mechanism |
| :--- | :--- | :--- | :--- |
| **NLB + API Gateway (TLS Termination & Routing)** | 2.0 ms | 5.0 ms | Hardware SSL offload via AWS NLB + Envoy C++ event loop in Kong Gateway. |
| **JWT Authentication & Tier Rate Limit** | 1.0 ms | 3.0 ms | Local in-memory public key validation + Redis Lua token-bucket check. |
| **Idempotency Check (Redis Cluster GET/SETNX)** | 0.8 ms | 2.0 ms | Single sub-millisecond Redis roundtrip within the same AZ. |
| **Fraud Detection & Velocity Check (Sync Path)** | 6.0 ms | **15.0 ms** | ONNX runtime C++ inference + Redis feature store cache; bounded by `CB-FRAUD`. |
| **PostgreSQL Balance Read (Account Shard)** | 2.5 ms | 5.0 ms | Direct indexed B-Tree point query (`account_id`) on memory-cached database buffer. |
| **Core Business Logic & Fee Calculation** | 0.5 ms | 1.5 ms | Pure in-memory computation in Kotlin/Java; zero blocking I/O. |
| **PostgreSQL Atomic OCC Balance Write** | 6.0 ms | **12.0 ms** | Transactional update with NVMe WAL fsync on `io2` provisioned storage. |
| **1x Jittered OCC Retry (Under Contention)** | — | **15.0 ms** | Allocated headroom for 1 retry attempt in case of high-frequency concurrent balance update. |
| **Transactional Outbox Event Write** | 1.0 ms | 2.5 ms | Bundled in same local SQL transaction as the OCC balance write. |
| **Response Serialization & Client Egress** | 1.0 ms | 3.0 ms | High-speed Jackson JSON serialization over HTTP/2. |
| **TOTAL END-TO-END CRITICAL PATH** | **20.8 ms** | **64.0 ms** | **Leaves a 36.0 ms safety buffer below our 100ms p99 SLA!** |

---

## 2. Non-Critical Path (Asynchronous Post-Commit Schedulers)

| Operation | Target SLA | Execution Engine |
| :--- | :--- | :--- |
| **Debezium CDC WAL Publication to Kafka** | < 100 ms | Apache Kafka 3.6 (Topic: `transaction-events`) |
| **WebSocket Real-Time Client Push** | < 250 ms | Go / Node.js WebSocket Cluster |
| **SMS / Push Alert Dispatch** | < 1,500 ms | Third-Party Gateway via Kafka Consumer (`CB-NOTIFY`) |
| **Continuous Double-Entry Reconciliation**| < 2,000 ms | Apache Flink Stream Audit Engine |
| **Compliance & S3 Glacier Archival** | < 5,000 ms | Go Compliance Service with Parquet Compression |
