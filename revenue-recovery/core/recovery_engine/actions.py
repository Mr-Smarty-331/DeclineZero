"""
Recovery Action Engine & Razorpay Payment Links Integration.

Implements bounded multi-channel dispatch mapping Phase 4 diagnostic outputs to:
1. Razorpay Payment Links API (test-mode schema)
2. Multi-channel messaging (WhatsApp, SMS, Internal Escalation)
3. Unit action cost tracking and strict compliance boundaries
"""
import os
import time
import uuid
import logging
from typing import Dict, Any, Optional, Union
from api.models.transaction import TransactionRecord

logger = logging.getLogger("recovery_engine")

# ASSUMPTION: Unit delivery costs per outreach channel (in INR)
CHANNEL_COSTS = {
    "whatsapp": 0.50,
    "sms": 0.20,
    "internal_escalation": 0.00,
    "none": 0.00
}


def create_payment_link(
    amount: float,
    customer_contact: str = "+919876543210",
    customer_email: str = "customer@example.com",
    description: str = "Payment Recovery Link",
    method_hint: Optional[str] = None,
    txn_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates a Razorpay Payment Link matching the official Razorpay Payment Links API specification.
    # UNVERIFIED AGAINST LIVE API — schema based on docs, not tested against live Razorpay test mode.
    """
    amount_in_paise = int(round(float(amount) * 100))
    clean_id = (txn_id or str(uuid.uuid4())).replace("-", "")[:12]
    plink_id = f"plink_{clean_id}"

    # Official Razorpay Payment Link POST /v1/payment_links request payload shape
    payload = {
        "amount": amount_in_paise,
        "currency": "INR",
        "accept_partial": False,
        "description": description,
        "customer": {
            "name": "Customer",
            "contact": customer_contact,
            "email": customer_email
        },
        "notify": {
            "sms": False,   # Controlled directly by our multi-channel dispatcher
            "email": False
        },
        "reminder_enable": True,
        "notes": {
            "recovery_engine": "AI_Revenue_Recovery_Agent",
            "transaction_id": txn_id or str(uuid.uuid4()),
            "method_hint": method_hint or "all"
        },
        "callback_url": "https://recovery.razorpay.com/callback",
        "callback_method": "get"
    }

    # In production/live test-mode, this executes:
    # response = requests.post("https://api.razorpay.com/v1/payment_links", auth=(KEY_ID, KEY_SECRET), json=payload)
    # Here we produce the authentic response structure:
    created_at = int(time.time())
    short_url = f"https://rzp.io/i/{clean_id[:8]}"

    response_data = {
        "id": plink_id,
        "entity": "payment_link",
        "amount": amount_in_paise,
        "currency": "INR",
        "status": "created",
        "description": description,
        "short_url": short_url,
        "customer": payload["customer"],
        "notes": payload["notes"],
        "created_at": created_at,
        "expire_by": created_at + (86400 * 3)  # 3-day validity window
    }

    logger.info(f"PAYMENT_LINK_CREATED: id={plink_id}, amount=₹{amount}, short_url={short_url}")
    return response_data


def send_whatsapp(contact: str, message: str) -> Dict[str, Any]:
    """
    Mock WhatsApp sender: Logs outbound template notification with latency and cost telemetry.
    """
    logger.info(f"DISPATCH_WHATSAPP -> To: {contact} | Content: '{message}'")
    return {
        "channel": "whatsapp",
        "recipient": contact,
        "delivered": True,
        "timestamp": int(time.time()),
        "cost": CHANNEL_COSTS["whatsapp"]
    }


def send_sms(contact: str, message: str) -> Dict[str, Any]:
    """
    Mock SMS sender: Logs outbound transactional SMS notification.
    """
    logger.info(f"DISPATCH_SMS -> To: {contact} | Content: '{message}'")
    return {
        "channel": "sms",
        "recipient": contact,
        "delivered": True,
        "timestamp": int(time.time()),
        "cost": CHANNEL_COSTS["sms"]
    }


def dispatch_action(
    action: str,
    transaction_record: Union[Dict[str, Any], TransactionRecord]
) -> Dict[str, Any]:
    """
    Executes recovery actions based on Phase 4 diagnostic recommendations:
    
    1. SEND_FRESH_PAYMENT_LINK_URGENT  -> Creates payment link, dispatches urgent WhatsApp nudge.
    2. SCHEDULE_SALARY_ALIGNED_RETRY   -> Creates payment link, dispatches salary-aligned SMS.
    3. SUGGEST_ALTERNATE_METHOD        -> Creates payment link with method hint, dispatches WhatsApp.
    4. SEND_MANDATE_REVIVAL_LINK       -> Creates mandate renewal link, dispatches WhatsApp.
    5. SEND_REMINDER_TRACK_PROMISE     -> Creates invoice payment link, dispatches SMS.
    6. ESCALATE_HUMAN_REVIEW           -> Internal escalation ONLY (Zero customer outreach, zero payment link).
    """
    if isinstance(transaction_record, TransactionRecord):
        data = transaction_record.model_dump()
    else:
        data = transaction_record

    txn_id = str(data.get("transaction_id", str(uuid.uuid4())))
    amount = float(data.get("amount", 100.0))
    contact = str(data.get("contact", "+919876543210"))
    email = str(data.get("email", "customer@example.com"))
    category = str(data.get("category", "checkout"))

    # ----------------------------------------------------------------------------------
    # COMPLIANCE CRITICAL: Escalation produces ZERO customer outreach
    # ----------------------------------------------------------------------------------
    if action == "ESCALATE_HUMAN_REVIEW":
        logger.warning(f"ESCALATION_DISPATCH: txn_id={txn_id} isolated for human review. Zero outreach sent.")
        return {
            "action": action,
            "channel": "internal_escalation",
            "cost": CHANNEL_COSTS["internal_escalation"],
            "payment_link_id": None,
            "payment_url": None,
            "message_sent": None,
            "success": True,
            "escalated_for_review": True,
            "details": f"Transaction {txn_id} placed in compliance queue for manual agent review."
        }

    # 1. Timing Issue: Urgent Payment Link
    elif action == "SEND_FRESH_PAYMENT_LINK_URGENT":
        plink = create_payment_link(amount, contact, email, "Complete your pending payment", txn_id=txn_id)
        msg = f"Your payment of ₹{int(amount)} timed out. Click here to complete securely: {plink['short_url']}"
        delivery = send_whatsapp(contact, msg)
        channel = "whatsapp"
        cost = CHANNEL_COSTS["whatsapp"]

    # 2. Insufficient Funds: Salary-Aligned Retry Link
    elif action == "SCHEDULE_SALARY_ALIGNED_RETRY":
        plink = create_payment_link(amount, contact, email, "Scheduled payment retry link", txn_id=txn_id)
        msg = f"Notice: Payment of ₹{int(amount)} could not be processed. Use this link to complete at your convenience: {plink['short_url']}"
        delivery = send_sms(contact, msg)
        channel = "sms"
        cost = CHANNEL_COSTS["sms"]

    # 3. Bank Switch Technical Issue: Alternate Payment Rail
    elif action == "SUGGEST_ALTERNATE_METHOD":
        plink = create_payment_link(amount, contact, email, "Try alternate payment method", method_hint="card,netbanking", txn_id=txn_id)
        msg = f"Bank switch issue detected on your payment. Please try an alternate card or netbanking method: {plink['short_url']}"
        delivery = send_whatsapp(contact, msg)
        channel = "whatsapp"
        cost = CHANNEL_COSTS["whatsapp"]

    # 4. Subscription Mandate Lapsed: Mandate Revival
    elif action == "SEND_MANDATE_REVIVAL_LINK":
        plink = create_payment_link(amount, contact, email, "Renew subscription mandate", txn_id=txn_id)
        msg = f"Your subscription auto-debit paused. Update your payment mandate here to stay active: {plink['short_url']}"
        delivery = send_whatsapp(contact, msg)
        channel = "whatsapp"
        cost = CHANNEL_COSTS["whatsapp"]

    # 5. Overdue Invoice / Receivable: Reminder & Promise Tracking
    elif action == "SEND_REMINDER_TRACK_PROMISE":
        plink = create_payment_link(amount, contact, email, f"Invoice payment for {category}", txn_id=txn_id)
        msg = f"Reminder: Invoice payment of ₹{int(amount)} is pending. Pay online securely: {plink['short_url']}"
        delivery = send_sms(contact, msg)
        channel = "sms"
        cost = CHANNEL_COSTS["sms"]

    else:
        raise ValueError(f"Unrecognized recovery action: {action}")

    return {
        "action": action,
        "channel": channel,
        "cost": cost,
        "payment_link_id": plink["id"],
        "payment_url": plink["short_url"],
        "message_sent": msg,
        "success": True,
        "escalated_for_review": False,
        "details": f"Dispatched {action} over {channel} (Cost: ₹{cost})"
    }
