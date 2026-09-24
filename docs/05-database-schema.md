# Day 5: Production Database Schema & Partitioning Design
**Project:** PayScale High-Throughput Transaction Processing Engine (HTTPE)  
**Author:** Senior Infrastructure Architect  
**Deliverable:** Complete DDL documentation, indexing strategy, and time-based range partitioning  

---

## 1. Relational Entity Architecture Overview

The database design implements a double-entry financial ledger model, supporting high concurrency, immutable auditability, and horizontal shard routing across 4 PostgreSQL 16 shards.

```
                           +------------------------+
                           |        users           |
                           +------------------------+
                                      | 1
                                      |
                                      | N
+--------------------+ 1    N +------------------------+ 1      N +------------------------+
|    fraud_rules     |        |       accounts         |----------|  merchant_settlements  |
+--------------------+        +------------------------+          +------------------------+
                                 | 1 (source/dest)                   |
                                 |                                   |
                                 | N                                 |
                              +------------------------+ 1        1  |
                              |      transactions      |-------------+
                              +------------------------+
                                      | 1
                                      |
                    +-----------------+-----------------+
                    | 1:N                               | 1:N
         +------------------------+          +------------------------+
         |     ledger_entries     |          |   transaction_events   |
         +------------------------+          +------------------------+
                    |                                   |
                    | (Double-Entry Bookkeeping)        | (Saga Audit State)
```

---

## 2. Entity Specifications & Indexing Strategy

### 2.1 Entity: `accounts`
- **Primary Key:** `account_id` (UUIDv7 for time-ordered locality).
- **Core Role:** Tracks spendable `available_balance` and accounting `ledger_balance`.
- **Concurrency Control:** `version BIGINT NOT NULL DEFAULT 1` enables atomic Compare-And-Swap (CAS) updates.
- **Key Constraints:** `CHECK (available_balance >= 0.0000)` strictly prevents negative account balance overdrafts at the database engine level.
- **Indexing Strategy:**
  - `idx_accounts_user_id`: B-Tree index on `user_id` for fast customer dashboard rendering.
  - `idx_accounts_status`: Partial index on non-active accounts (`WHERE status != 'ACTIVE'`) to instantly verify account suspensions during fraud mitigation.

### 2.2 Entity: `transactions` (Partitioned)
- **Primary Key:** Composite `(transaction_id, created_at)` for monthly range partitioning.
- **Partitioning Strategy:** Partitioned by month (`created_at` range). Old partitions (> 24 months) are detached and archived to AWS S3 Glacier in Parquet format, meeting the RBI 2-year hot data retention mandate while keeping active indexes small and memory-resident.
- **Indexing Strategy:**
  - `idx_transactions_idempotency`: Unique B-Tree index on `idempotency_key` preventing duplicate execution.
  - `idx_transactions_source_acc`: Composite B-Tree `(source_account_id, created_at DESC)` for high-speed paginated transaction history queries.
  - `idx_transactions_metadata_gin`: GIN index on `metadata` JSONB for searching by device ID, IP, or partner reference.

### 2.3 Entity: `ledger_entries` (Partitioned)
- **Primary Key:** Composite `(entry_id, created_at)`.
- **Double-Entry Invariant:** Every financial transaction creates at least two immutable rows:
  - 1 DEBIT row against the source account (reducing balance).
  - 1 CREDIT row against the destination account (increasing balance).
- **No UPDATE Policy:** Ledger rows are strictly `INSERT-ONLY`. Reversals generate compensating ledger rows with `entry_type = 'REFUND'`.

---

## 3. Shard Key Design: `shard_key = abs(hash(account_id)) % 4`

Each `accounts` record stores a pre-computed `shard_key` (`0..3`). When a request arrives with an `account_id`, the application layer routes queries directly to the specific PostgreSQL primary shard:
- **Shard 0:** `shard_key == 0`
- **Shard 1:** `shard_key == 1`
- **Shard 2:** `shard_key == 2`
- **Shard 3:** `shard_key == 3`

This guarantees that 100% of single-account balance checks, debits, and balance deposits execute entirely on a single localized PostgreSQL primary, achieving sub-10ms query execution times.
