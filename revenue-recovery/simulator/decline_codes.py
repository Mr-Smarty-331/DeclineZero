"""
Core Decline-Code Taxonomy & Ambiguous Legacy Codes for Razorpay Track 03: AI Revenue Recovery.

1. Verified NPCI / Razorpay decline codes:
- UPI:
  - U69: Collect request expired (timing / customer inattention)
  - Z9: Insufficient funds in customer account
  - U28: Bank-side technical glitch / PSP communication timeout
  - Risk Flagged: U16, 34, 59, K1, S1, S2, S3 (mandatory human escalation, never auto-retried)
- Subscriptions:
  - mandate_expired: Mandate lapsed
  - mandate_paused: Mandate temporarily suspended
- Receivables:
  - overdue_no_dispute: Invoice past due date with no dispute flag
  - overdue_with_dispute_flag: Invoice past due date with active dispute

2. Ambiguous / Legacy Codes (Conformal Prediction calibration set):
- Fictional placeholder error strings simulating noisy cooperative-bank legacy responses.
"""
from enum import Enum

class UPIDeclineCode(str, Enum):
    U69 = "U69"  # Collect expired — timing issue
    Z9 = "Z9"    # Insufficient funds
    U28 = "U28"  # Bank-side technical issue
    U16 = "U16"  # Risk / fraud flagged
    CODE_34 = "34"   # Risk / fraud flagged
    CODE_59 = "59"   # Risk / fraud flagged
    K1 = "K1"    # Risk / fraud flagged
    S1 = "S1"    # Risk / fraud flagged
    S2 = "S2"    # Risk / fraud flagged
    S3 = "S3"    # Risk / fraud flagged

class SubscriptionDeclineCode(str, Enum):
    MANDATE_EXPIRED = "mandate_expired"
    MANDATE_PAUSED = "mandate_paused"

class ReceivableDeclineCode(str, Enum):
    OVERDUE_NO_DISPUTE = "overdue_no_dispute"
    OVERDUE_WITH_DISPUTE_FLAG = "overdue_with_dispute_flag"

class RootCauseCategory(str, Enum):
    TIMING_ATTENTION = "TIMING_ATTENTION"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    BANK_TECHNICAL_ISSUE = "BANK_TECHNICAL_ISSUE"
    RISK_FLAGGED = "RISK_FLAGGED"
    MANDATE_LAPSED = "MANDATE_LAPSED"
    OVERDUE_INVOICE = "OVERDUE_INVOICE"

# Grouped verified categories
RISK_FLAGGED_CODES = frozenset({"U16", "34", "59", "K1", "S1", "S2", "S3"})

UPI_CODES = frozenset(code.value for code in UPIDeclineCode)
SUBSCRIPTION_CODES = frozenset(code.value for code in SubscriptionDeclineCode)
RECEIVABLE_CODES = frozenset(code.value for code in ReceivableDeclineCode)

ALL_VALID_CODES = UPI_CODES | SUBSCRIPTION_CODES | RECEIVABLE_CODES

# --------------------------------------------------------------------------------------
# FICTIONAL / SYNTHETIC PLACEHOLDERS: Unmapped cooperative-bank legacy error strings.
# Explicit note: These are NOT real NPCI/Razorpay decline codes. They exist solely as
# synthetic out-of-distribution / noisy residuals to evaluate Conformal Prediction abstention.
# --------------------------------------------------------------------------------------
LEGACY_AMBIGUOUS_CODES = [
    "ERR-BNK-0001",  # Legacy host timeout
    "ERR-BNK-0002",  # Unmapped core banking response 91
    "ERR-BNK-0003",  # Switch communication failure 06
    "ERR-BNK-0004",  # Undefined debit exception
    "ERR-BNK-0005",  # Generic balance check abort
    "ERR-BNK-0006",  # Regional co-op gateway reset
    "ERR-BNK-0007",  # Unknown settlement state
    "ERR-BNK-0008",  # Inactive terminal mapping
    "ERR-BNK-0009",  # Format parsing failure at acquirer
    "ERR-BNK-0010",  # Security module integrity warning
]
