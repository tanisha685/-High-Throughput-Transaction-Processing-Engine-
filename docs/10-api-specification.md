# Day 10: OpenAPI 3.0 Specification & API Gateway Ingress Design
**Project:** PayScale High-Throughput Transaction Processing Engine (HTTPE)  
**Author:** Senior Infrastructure Architect  
**Deliverable:** API Architecture, Cursor Pagination Protocol, Tier Rate Limiting, and Error Code Mappings  

---

## 1. REST / gRPC API Design Architecture

The API Gateway layer exposes standardized REST/JSON and gRPC endpoints designed for high throughput, predictable pagination, and cryptographic idempotency.

```
Client Header:
Idempotency-Key: 9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d
Authorization: Bearer <JWT Token>
```

---

## 2. Cursor-Based Pagination vs. Offset Pagination

For high-volume transaction history (`/accounts/{account_id}/transactions`), traditional `OFFSET / LIMIT` pagination suffers severe performance degradation:
$$\text{Query: } \text{SELECT * FROM transactions OFFSET 100000 LIMIT 20;}$$
This forces PostgreSQL to perform 100,000 full index scans, driving query latencies above 450ms.

### Our Opaque Keyset Cursor Solution:
We encode the tuple `(created_at, transaction_id)` into an opaque Base64 cursor:
$$\text{Cursor} = \text{Base64}\left(\text{JSON}(\{\text{"ts"}: 1790251200000, \text{"id"}: \text{"uuid-123"}\})\right)$$
The underlying SQL executes in **< 3ms**:
```sql
SELECT transaction_id, status, amount, currency, created_at
FROM transactions
WHERE source_account_id = :account_id
  AND (created_at, transaction_id) < (:cursor_ts, :cursor_id)
ORDER BY created_at DESC, transaction_id DESC
LIMIT :limit;
```

---

## 3. Account Tier Rate Limiting Strategy (Token Bucket)

Rate limits are enforced at the Kong API Gateway backed by Redis Cluster token buckets:

| Account Tier | Rate Limit (Sustained) | Burst Multiplier (10s) | Redis Key Pattern |
| :--- | :--- | :--- | :--- |
| **BASIC** | 50 TPS | 75 TPS | `ratelimit:basic:{user_id}` |
| **PREMIUM** | 200 TPS | 300 TPS | `ratelimit:prem:{user_id}` |
| **MERCHANT** | 1,000 TPS | 1,500 TPS | `ratelimit:merch:{merchant_id}` |
| **INTERNAL / RECON**| 5,000 TPS | 7,500 TPS | `ratelimit:internal:{service_id}`|

---

## 4. Standardized Financial Error Response Mapping

| HTTP Status Code | Financial Error Code | Trigger Condition |
| :--- | :--- | :--- |
| **400 Bad Request** | `INVALID_PAYLOAD` | Missing required fields, negative amount, or invalid UUID. |
| **401 Unauthorized** | `AUTH_TOKEN_EXPIRED` | Expired or invalid JWT token. |
| **403 Forbidden** | `ACCOUNT_SUSPENDED` | Account is frozen or failed KYC verification. |
| **403 Forbidden** | `FRAUD_BLOCKED` | High risk score evaluated by Fraud Detection Service. |
| **422 Unprocessable** | `INSUFFICIENT_FUNDS` | `available_balance < transfer_amount`. |
| **422 Unprocessable** | `OCC_CONTENTION_TIMEOUT` | Exceeded 3 OCC retries on hot account. |
| **429 Too Many Requests** | `RATE_LIMIT_EXCEEDED` | Token bucket depleted for account tier. |
| **503 Service Unavailable** | `CIRCUIT_BREAKER_OPEN` | Protected downstream dependency degraded. |
