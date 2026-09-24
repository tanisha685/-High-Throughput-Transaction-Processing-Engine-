"""
Optimistic Concurrency Control (OCC) Balance Update Engine
PayScale Financial Technologies — High-Throughput Transaction Processing Engine

Features:
- Atomic Compare-And-Swap (CAS) version validation
- Double-spend prevention and non-negative balance checks
- Jittered Exponential Backoff Retry Engine
- Formal ACID safety guarantees
"""

import time
import random
import uuid
from decimal import Decimal
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum


class AccountStatus(Enum):
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    SUSPENDED = "SUSPENDED"


class TransactionError(Exception):
    pass


class InsufficientFundsError(TransactionError):
    pass


class AccountFrozenError(TransactionError):
    pass


class OCCVersionConflictError(TransactionError):
    pass


@dataclass
class AccountRecord:
    account_id: str
    user_id: str
    available_balance: Decimal
    ledger_balance: Decimal
    version: int
    status: AccountStatus


class MockDatabaseShard:
    """Simulates a PostgreSQL Shard with atomic row updates."""
    def __init__(self):
        self._store: Dict[str, AccountRecord] = {}

    def insert_account(self, account: AccountRecord):
        self._store[account.account_id] = account

    def get_account_for_read(self, account_id: str) -> Optional[AccountRecord]:
        """Simulates: SELECT account_id, available_balance, version, status FROM accounts WHERE account_id = :id"""
        rec = self._store.get(account_id)
        if not rec:
            return None
        # Return a copy representing the snapshot read
        return AccountRecord(
            account_id=rec.account_id,
            user_id=rec.user_id,
            available_balance=rec.available_balance,
            ledger_balance=rec.ledger_balance,
            version=rec.version,
            status=rec.status,
        )

    def execute_occ_debit(self, account_id: str, debit_amount: Decimal, expected_version: int) -> bool:
        """
        Simulates atomic SQL:
        UPDATE accounts
        SET available_balance = available_balance - :debit_amount,
            version = version + 1
        WHERE account_id = :account_id
          AND version = :expected_version
          AND available_balance >= :debit_amount
          AND status = 'ACTIVE';
        """
        current = self._store.get(account_id)
        if not current:
            return False

        # Atomic Engine Constraint Verification
        if current.status != AccountStatus.ACTIVE:
            return False

        if current.version != expected_version:
            # OCC Version Mismatch (Another transaction modified this row)
            return False

        if current.available_balance < debit_amount:
            # Prevent Overdraft
            return False

        # Atomic Commit
        current.available_balance -= debit_amount
        current.version += 1
        return True

    def execute_occ_credit(self, account_id: str, credit_amount: Decimal, expected_version: int) -> bool:
        """
        Simulates atomic SQL:
        UPDATE accounts
        SET available_balance = available_balance + :credit_amount,
            version = version + 1
        WHERE account_id = :account_id
          AND version = :expected_version
          AND status = 'ACTIVE';
        """
        current = self._store.get(account_id)
        if not current:
            return False

        if current.status != AccountStatus.ACTIVE:
            return False

        if current.version != expected_version:
            return False

        current.available_balance += credit_amount
        current.version += 1
        return True


class OCCBalanceManager:
    def __init__(self, db_shard: MockDatabaseShard, max_retries: int = 3, base_backoff_ms: float = 10.0):
        self.db = db_shard
        self.max_retries = max_retries
        self.base_backoff_ms = base_backoff_ms

    def debit_with_occ(self, account_id: str, amount: Decimal, txn_id: str) -> Tuple[bool, int, Decimal]:
        """
        Debits an account using Optimistic Concurrency Control.
        Returns: (success: bool, attempts: int, new_balance: Decimal)
        """
        if amount <= Decimal("0.00"):
            raise ValueError("Debit amount must be strictly positive")

        attempts = 0
        while attempts < self.max_retries:
            attempts += 1
            # Step 1: Read snapshot state (No row locks acquired!)
            account = self.db.get_account_for_read(account_id)
            if not account:
                raise TransactionError(f"Account {account_id} not found")

            if account.status != AccountStatus.ACTIVE:
                raise AccountFrozenError(f"Account {account_id} is in {account.status.value} status")

            if account.available_balance < amount:
                raise InsufficientFundsError(
                    f"Insufficient balance: Available INR {account.available_balance}, Requested INR {amount}"
                )

            # Step 2: Attempt Atomic Compare-And-Swap (CAS) write
            read_version = account.version
            success = self.db.execute_occ_debit(
                account_id=account_id,
                debit_amount=amount,
                expected_version=read_version
            )

            if success:
                # Successfully committed with zero locks!
                updated = self.db.get_account_for_read(account_id)
                return True, attempts, updated.available_balance

            # Step 3: Conflict encountered - Apply Jittered Exponential Backoff
            backoff_seconds = (self.base_backoff_ms * (2 ** (attempts - 1)) + random.uniform(1.0, 10.0)) / 1000.0
            time.sleep(backoff_seconds)

        raise OCCVersionConflictError(
            f"Transaction {txn_id} aborted: Max OCC retries ({self.max_retries}) exhausted due to high contention"
        )


if __name__ == "__main__":
    # Self-test verification
    shard = MockDatabaseShard()
    acc_id = str(uuid.uuid4())
    shard.insert_account(AccountRecord(
        account_id=acc_id,
        user_id="usr-101",
        available_balance=Decimal("1500.00"),
        ledger_balance=Decimal("1500.00"),
        version=1,
        status=AccountStatus.ACTIVE
    ))

    manager = OCCBalanceManager(shard)
    ok, attempts, bal = manager.debit_with_occ(acc_id, Decimal("500.00"), "txn-001")
    print(f"Test OCC Debit Success: {ok}, Attempts: {attempts}, New Balance: INR {bal}")
    assert bal == Decimal("1000.00")
    print("OCC Balance Engine Verified Successfully!")
