# Day 8: Concurrency Control, Isolation Levels & Distributed State
**Project:** PayScale High-Throughput Transaction Processing Engine (HTTPE)  
**Author:** Senior Infrastructure Architect  
**Deliverable:** Formal OCC Correctness Proof, Write-Skew Prevention, Isolation Level Selection, and Fencing Tokens  

---

## 1. Concurrency Anomalies & Formal OCC Correctness Proof

In high-throughput financial architectures, concurrent transactions targeting the same account must maintain ACID consistency without degrading throughput.

### 1.1 The Classic Write-Skew / Double-Spend Anomaly
Suppose Account $A$ has an initial balance of ₹1,000. Two concurrent transactions arrive simultaneously:
- **Transaction 1 ($T_1$):** Debits ₹800.
- **Transaction 2 ($T_2$):** Debits ₹600.

#### Under Naive Snapshot Isolation (Without Locking or Versioning):
1. $T_1$ reads Balance = ₹1,000 at timestamp $t_1$.
2. $T_2$ reads Balance = ₹1,000 at timestamp $t_1$.
3. $T_1$ computes $1000 - 800 = 200 \ge 0$, and writes Balance = ₹200 at $t_2$.
4. $T_2$ computes $1000 - 600 = 400 \ge 0$, and writes Balance = ₹400 at $t_3$.
5. **Outcome:** ₹1,400 was spent from a ₹1,000 account, creating a severe ₹400 unauthorized overdraft and violating the conservation of money.

---

### 1.2 Formal Proof: OCC With Compare-And-Swap (CAS) Prevents Write-Skew

#### Theorem:
Under PayScale’s OCC balance update protocol, concurrent transactions cannot overdraft an account, and exactly one conflicting transaction succeeds while others are forced to retry against updated state.

#### Proof:
Let account state $S = \langle B, v \rangle$, where $B \in \mathbb{R}_{\ge 0}$ is `available_balance` and $v \in \mathbb{N}$ is the monotonic version counter.
Initial state: $S_0 = \langle 1000, 1 \rangle$.

1. Both $T_1$ and $T_2$ execute snapshot reads:
   $$T_1 \text{ observes } \langle 1000, 1 \rangle, \quad T_2 \text{ observes } \langle 1000, 1 \rangle$$
2. $T_1$ issues atomic SQL update with predicate:
   $$\text{UPDATE accounts SET } B = 1000 - 800 = 200, v = 2 \text{ WHERE } \text{id} = A \land v = 1 \land B \ge 800$$
3. PostgreSQL evaluates the predicate under row-level latch. Since $v = 1$ and $B = 1000 \ge 800$, the update commits. State becomes:
   $$S_1 = \langle 200, 2 \rangle$$
4. $T_2$ now executes its atomic SQL update:
   $$\text{UPDATE accounts SET } B = 1000 - 600 = 400, v = 2 \text{ WHERE } \text{id} = A \land v = 1 \land B \ge 600$$
5. PostgreSQL evaluates the predicate against current state $S_1 = \langle 200, 2 \rangle$.
   - Current version $v = 2 \ne 1$ (Expected version $1$).
   - The predicate evaluates to **FALSE**, returning **0 rows updated**.
6. $T_2$ detects 0 updated rows and triggers application-level retry #1.
7. $T_2$ re-reads current state $S_1 = \langle 200, 2 \rangle$.
8. $T_2$ checks constraint: $200 < 600$ (Requested amount exceeds available balance).
9. $T_2$ immediately aborts and returns `422 INSUFFICIENT_FUNDS` without mutating state.
10. **Conclusion:** Final state remains $S_1 = \langle 200, 2 \rangle$. Balance is preserved, double-spending is mathematically impossible, and no deadlocks occurred. $\blacksquare$

---

## 2. PostgreSQL Isolation Level Selection Matrix

| Query / Operation | Isolation Level | Justification |
| :--- | :--- | :--- |
| **Balance Debit / Credit (Core Transfer)**| **READ COMMITTED + OCC Predicate** | Atomic CAS in WHERE clause guarantees serializability without multi-version overhead. |
| **Daily Batch Merchant Settlement** | **REPEATABLE READ** | Ensures consistent snapshot across 50,000+ merchant records during aggregation. |
| **Double-Entry Ledger Reconciliation**| **SNAPSHOT ISOLATION (Read Replica)**| Audits immutable ledger rows without acquiring locks or blocking writers. |
| **User Dashboard Balance Query** | **READ COMMITTED (or Redis Cache)** | Ultra-fast read of committed balance (< 2ms). |

---

## 3. Distributed Locking & Fencing Tokens (Redis Redlock)

For coarse-grained operations (such as batch settlement initialization or account freezing across shards), we use **Redis Distributed Locking with Monotonically Increasing Fencing Tokens**.

```
Client 1 (Acquires Lock, Token = 101) ---> [ GC Pause / Network Delay ]
                                                     |
                                   (Lock Expires & Reassigned)
                                                     |
Client 2 (Acquires Lock, Token = 102) -------------------> [ DB Storage: Accepts Token 102 ]
                                                                      |
Client 1 (Wakes up, attempts write with Stale Token 101) ---> [ DB Storage: REJECTED! (101 < 102) ]
```

Every lock acquisition in Redis increments a 64-bit sequence counter. The database layer validates that incoming write instructions possess a fencing token $\ge$ the last recorded token, completely preventing split-brain writes during GC pauses.
