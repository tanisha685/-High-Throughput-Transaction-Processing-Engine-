# ADR-004: Selection of Asynchronous Event-Driven Architecture with Transactional Outbox Pattern

## Status
Accepted

## Context
In PayScale's legacy architecture, microservices communicated primarily via synchronous REST HTTP calls (e.g., Ingress -> Orchestrator -> Fraud Service -> Payment Service -> Notification Service -> Audit Service). 

Under load testing at 2,000 TPS, this synchronous cascading model caused:
- **Cascading Failures:** A slow SMS gateway in the Notification Service held HTTP connection threads open all the way back to the API Gateway, exhausting thread pools and causing a 40% timeout rate (BN-003).
- **Dual-Write Inconsistencies:** If an HTTP call failed after committing to the database, data between the payment ledger and notification log drifted permanently.
- **Latency Bloat:** The total request latency equaled the sum of all serial downstream HTTP hops ($85\text{ms} + 20\text{ms} + 150\text{ms} = 255\text{ms}$), making our sub-100ms p99 SLA impossible.

## Decision
We adopt a **Hybrid Event-Driven Architecture**:
1. **Synchronous Ingress Critical Path:** Synchronous gRPC/REST is reserved strictly for immediate authorization: Ingress -> Fraud Check (< 15ms) -> Shard Balance Debit (< 12ms) -> Immediate 200 OK Response.
2. **Asynchronous Downstream Decoupling:** All post-commit activities (push notifications, SMS alerts, double-entry reconciliation audits, merchant analytics, and compliance archiving) are decoupled via Apache Kafka using the **Transactional Outbox Pattern** with Debezium CDC.

## Alternatives Considered

| Dimension | Hybrid Event-Driven + Outbox (Selected) | Pure Synchronous REST Chains | Choreographed Event Mesh (No Orchestration) |
| :--- | :--- | :--- | :--- |
| **p99 End-to-End Latency** | **< 35 ms (Critical path isolated)** | 250-600 ms (Serial HTTP chain) | 50-120 ms |
| **Cascade Failure Risk** | **Zero (Downstream latency isolated)** | Extreme (One slow service blocks all)| Low |
| **Dual-Write Safety** | **100% Guaranteed (PostgreSQL WAL CDC)**| Flawed (App crashes cause drift)| Complex distributed rollback |
| **Audit Log Completeness** | **Immutable Kafka Event Stream** | Relies on scattered HTTP logs | Eventual consistency delay |

- **Pure Synchronous REST:** Rejected because any slowdown in third-party SMS providers or logging backends immediately degrades user payment response times and consumes worker threads.
- **Pure Choreographed Mesh:** Rejected for core financial transfers because lack of a centralized orchestrator makes multi-step saga failure tracing and compensating rollbacks difficult to audit.

## Consequences

### Positive:
- **Resilience:** If the Notification Service or Audit Service is completely offline for 2 hours, user payment processing continues uninterrupted at full 12,000 TPS capacity.
- **Ultra-Fast User Latency:** Eliminating synchronous post-payment hops slashes user-perceived transaction latency from 255ms to under 35ms.
- **Guaranteed Consistency:** The Transactional Outbox pattern guarantees that every committed database state change generates an event in Kafka without exception.

### Negative & Trade-offs:
- End users experience near-instant UI responses, but SMS/Push notifications arrive with a slight asynchronous propagation delay (~100–400ms).
- Requires operational monitoring of Debezium CDC connectors and Kafka consumer group lags.

## Compliance & Regulatory Alignment
- **RBI Digital Payment Security Controls (2021):** The immutable Kafka event stream ensures an unalterable chronological audit trail for all payment events within Indian territory.
- **PCI-DSS v4.0:** Asynchronous event payloads are cryptographically signed and stripped of plain-text payment card data before publication.
