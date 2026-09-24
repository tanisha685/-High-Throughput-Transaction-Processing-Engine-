# Day 12: Capacity Planning & Infrastructure Cost Engineering
**Project:** PayScale High-Throughput Transaction Processing Engine (HTTPE)  
**Author:** Senior Infrastructure Architect  
**Deliverable:** 3-Scale Capacity Model, Resource Sizing, and AWS Mumbai Cost Analysis  

---

## 1. Multi-Scale Infrastructure Capacity Modeling

To ensure economic sustainability alongside technical excellence, we model resource demands across three distinct operating scales:
1. **Baseline Scale (Current):** 1,200 TPS (28 Million daily transactions)
2. **Target Scale (Diwali Launch):** **12,000 TPS sustained / 18,000 TPS burst** (85 Million daily transactions)
3. **Future 2x Scale (Expansion):** 24,000 TPS sustained / 36,000 TPS burst (170 Million daily transactions)

---

## 2. Comprehensive Resource Breakdown & Monthly Cost Model (AWS Mumbai `ap-south-1`)

### 2.1 Target Scale Cost Sizing (12,000 TPS) — Total: $40,850 / Month

```
+-------------------------------------------------------------------------------------------------------------------------+
|                                TARGET SCALE INFRASTRUCTURE BILL OF MATERIALS (12,000 TPS)                                |
+-------------------------------------------------------------------------------------------------------------------------+
| Service Layer           Instance Type       Qty  vCPU  RAM (GB)  Storage & Network Details           Monthly Cost (USD)     |
| API Gateway (Kong)      c6g.xlarge          4    16    32 GB     NLB + 10 Gbps Enhanced Net          $1,200                 |
| Transaction Orchestrator m6g.xlarge         8    32    128 GB    JVM Virtual Threads, Multi-AZ       $3,200                 |
| Payment Processing Svc  c6g.2xlarge         12   96    192 GB    High-throughput Netty / HikariCP    $6,000                 |
| Account Service         m6g.xlarge          6    24    96 GB     Multi-AZ Core Metadata              $1,800                 |
| Fraud Detection Engine  c6g.2xlarge (ML)    4    32    128 GB    ONNX Runtime + Redis C++ Engine     $3,600                 |
| Notification Service    c6g.large           3    6     12 GB     50k Persistent WebSockets           $450                   |
| Kafka Cluster (KRaft)   r6g.2xlarge         3    24    192 GB    3 TB NVMe gp3 (3,000 IOPS/broker)   $3,600                 |
| PostgreSQL Shard Cluster r6g.2xlarge        12   96    768 GB    4 Shards x (1 Pri + 2 Standbys)     $14,400                |
| (Database Storage io2)  Provisioned IOPS    --   --    --        4 x 10,000 IOPS io2 SSD Volumes     (Included in DB pool)  |
| Redis Cluster 7.2       r6g.xlarge          6    24    192 GB    6 Nodes (3 Masters + 3 Replicas)    $4,800                 |
| Observability Stack     m6g.xlarge          3    12    48 GB     Prometheus + Grafana + Loki (gp3)   $1,800                 |
+-------------------------------------------------------------------------------------------------------------------------+
| TOTAL MONTHLY TARGET INFRASTRUCTURE EXPENDITURE:                                                 $40,850 / Month        |
| BUDGET CEILING:                                                                                  $45,000 / Month        |
| BUDGET SURPLUS / HEADROOM:                                                                       +$4,150 / Mo (9.2%)    |
+-------------------------------------------------------------------------------------------------------------------------+
```

---

## 3. Comparative Cost Scaling Analysis Across 3 Workload Tiers

| Infrastructure Component | Baseline (1,200 TPS) | Target Production (12,000 TPS) | Future Scale (24,000 TPS) |
| :--- | :--- | :--- | :--- |
| **API Gateway & Load Balancer** | $400 / mo | $1,200 / mo | $2,200 / mo |
| **Core Microservices (Orch/Pay/Acc/Fraud)**| $4,200 / mo | $14,600 / mo | $28,400 / mo |
| **Notification & WebSocket Tier** | $150 / mo | $450 / mo | $850 / mo |
| **Kafka Event Streaming Bus** | $1,200 / mo | $3,600 / mo | $6,800 / mo |
| **PostgreSQL Database Shard Tier** | $3,600 / mo (1 Primary) | **$14,400 / mo (4 Shards)** | $28,800 / mo (8 Shards) |
| **Redis In-Memory Cluster** | $1,200 / mo | $4,800 / mo | $9,200 / mo |
| **Observability, Tracing & Logs** | $1,250 / mo | $1,800 / mo | $3,200 / mo |
| **TOTAL MONTHLY RUN-RATE** | **$12,000 / mo** | **$40,850 / mo** | **$79,450 / mo** |
| **Cost Per Million Transactions** | **$14.28** | **$15.90** | **$15.58** |

---

## 4. Cost Optimization Strategy (Unlocking an Extra 28% Savings)

If executive leadership requests further cost reductions (e.g., CFO budget revision):
1. **1-Year AWS Compute Savings Plans:** Committing to baseline EC2 instance usage provides an immediate **28% discount**, slashing monthly compute spend by **~$11,400/month** (bringing total run-rate down to **~$29,450/month**).
2. **Graviton (ARM64) Instances:** Utilizing AWS Graviton3 (`c6g`, `m6g`, `r6g`) instances achieves **20% lower cost** and **40% better price-performance** compared to legacy x86 `m5/c5` instances.
3. **Cold Data Tiering to S3 Glacier Instant Retrieval:** Detaching and compressing PostgreSQL partitions older than 90 days reduces high-performance SSD storage expenses by 65%.
