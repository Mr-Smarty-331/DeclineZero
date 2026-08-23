"""
Markov Decision Process (MDP) Definition for Cost-Sensitive Recovery & Stopping.

State Space S (243 discrete states):
- attempts_remaining ∈ {0, 1, 2, 3, 4, 5, 6, 7, 8}
- days_since_failure ∈ {"0-2", "3-7", "8-30"}
- ltv_tier           ∈ {"low", "medium", "high"}
- sentiment          ∈ {"neutral", "negative", "distressed"}

Action Space A (5 discrete actions):
- "urgent_whatsapp"
- "salary_deferred_sms"
- "voice_nudge"
- "wait_48h"
- "stop"
"""
import itertools
from typing import Dict, Any, List, Tuple

ATTEMPTS_REMAINING = list(range(9))  # 0 to 8
DAYS_SINCE_FAILURE = ["0-2", "3-7", "8-30"]
LTV_TIERS = ["low", "medium", "high"]
SENTIMENTS = ["neutral", "negative", "distressed"]

ACTIONS = [
    "urgent_whatsapp",
    "salary_deferred_sms",
    "voice_nudge",
    "wait_48h",
    "stop"
]

# ASSUMPTION: Baseline ticket recovery values by LTV tier (in INR)
LTV_BASE_VALUES = {
    "low": 500.0,
    "medium": 2500.0,
    "high": 10000.0
}

# ASSUMPTION: Action unit delivery costs (in INR)
ACTION_COSTS = {
    "urgent_whatsapp": 0.50,
    "salary_deferred_sms": 0.20,
    "voice_nudge": 1.50,
    "wait_48h": 0.00,
    "stop": 0.00
}

# ASSUMPTION: Success recovery probabilities by action and recency
ACTION_BASE_CONVERSION = {
    "urgent_whatsapp": 0.28,
    "salary_deferred_sms": 0.32,
    "voice_nudge": 0.35,
    "wait_48h": 0.04,
    "stop": 0.00
}

RECENCY_CONVERSION_MULTIPLIER = {
    "0-2": 1.0,
    "3-7": 0.60,
    "8-30": 0.25
}

# ASSUMPTION: Customer churn penalty scaling by LTV and sentiment
# Churn penalty formula: base_ltv_loss * distress_multiplier
LTV_CHURN_BASE_LOSS = {
    "low": 150.0,
    "medium": 750.0,
    "high": 3500.0
}

SENTIMENT_DISTRESS_MULTIPLIER = {
    "neutral": 0.0,
    "negative": 0.25,
    "distressed": 1.0  # Full catastrophic churn loss if reaching out to distressed customer
}


def get_all_states() -> List[Tuple[int, str, str, str]]:
    """
    Returns the complete list of all 243 discrete states.
    Tuple format: (attempts_remaining, days_since_failure, ltv_tier, sentiment)
    """
    return list(itertools.product(
        ATTEMPTS_REMAINING,
        DAYS_SINCE_FAILURE,
        LTV_TIERS,
        SENTIMENTS
    ))


def state_to_key(state: Tuple[int, str, str, str]) -> str:
    """
    Converts state tuple to stringified lookup key.
    """
    return f"{state[0]}|{state[1]}|{state[2]}|{state[3]}"


def key_to_state(key: str) -> Tuple[int, str, str, str]:
    """
    Parses stringified lookup key back to state tuple.
    """
    parts = key.split("|")
    return (int(parts[0]), parts[1], parts[2], parts[3])


def reward_fn(state: Tuple[int, str, str, str], action: str) -> float:
    """
    Computes expected net reward:
    R(s, a) = (Expected Recovered Value) - (Channel Cost) - (Expected Churn Penalty)
    """
    attempts, days, ltv, sentiment = state

    # If attempts are exhausted or action is stop -> absorbing zero reward
    if attempts == 0 or action == "stop":
        return 0.0

    # 1. Expected recovered value
    base_val = LTV_BASE_VALUES[ltv]
    p_conv = ACTION_BASE_CONVERSION[action] * RECENCY_CONVERSION_MULTIPLIER[days]
    
    # Negative/distressed sentiment lowers recovery conversion
    if sentiment == "negative":
        p_conv *= 0.50
    elif sentiment == "distressed":
        p_conv *= 0.10

    expected_recovered_revenue = base_val * p_conv

    # 2. Action delivery cost
    channel_cost = ACTION_COSTS[action]

    # 3. Customer relationship churn penalty
    # Penalizes active outreach on negative/distressed customers
    if action in ("urgent_whatsapp", "salary_deferred_sms", "voice_nudge"):
        churn_penalty = LTV_CHURN_BASE_LOSS[ltv] * SENTIMENT_DISTRESS_MULTIPLIER[sentiment]
    else:
        churn_penalty = 0.0

    net_reward = expected_recovered_revenue - channel_cost - churn_penalty
    return round(net_reward, 4)


def transition_fn(
    state: Tuple[int, str, str, str],
    action: str
) -> List[Tuple[float, Tuple[int, str, str, str]]]:
    """
    Returns the transition probability distribution over successor states:
    [(prob_1, next_state_1), (prob_2, next_state_2), ...]
    """
    attempts, days, ltv, sentiment = state

    # Terminal state or stop action -> Transitions to absorbing zero-attempt state
    if attempts == 0 or action == "stop":
        return [(1.0, (0, days, ltv, sentiment))]

    # 1. Attempts remaining progression
    if action in ("urgent_whatsapp", "salary_deferred_sms", "voice_nudge"):
        next_attempts = max(0, attempts - 1)
    else:  # wait_48h
        next_attempts = attempts

    # 2. Days since failure progression
    if days == "0-2":
        if action == "wait_48h":
            days_transitions = [(0.20, "0-2"), (0.80, "3-7")]
        else:
            days_transitions = [(0.70, "0-2"), (0.30, "3-7")]
    elif days == "3-7":
        if action == "wait_48h":
            days_transitions = [(0.40, "3-7"), (0.60, "8-30")]
        else:
            days_transitions = [(0.80, "3-7"), (0.20, "8-30")]
    else:  # "8-30"
        days_transitions = [(1.0, "8-30")]

    # 3. Sentiment fatigue dynamics
    if action in ("urgent_whatsapp", "voice_nudge"):
        # Intrusive outreach can increase irritation
        if sentiment == "neutral":
            sentiment_transitions = [(0.80, "neutral"), (0.20, "negative")]
        elif sentiment == "negative":
            sentiment_transitions = [(0.60, "negative"), (0.40, "distressed")]
        else:
            sentiment_transitions = [(1.0, "distressed")]
    elif action == "salary_deferred_sms":
        # Low-friction reminder has lower irritation chance
        if sentiment == "neutral":
            sentiment_transitions = [(0.92, "neutral"), (0.08, "negative")]
        elif sentiment == "negative":
            sentiment_transitions = [(0.80, "negative"), (0.20, "distressed")]
        else:
            sentiment_transitions = [(1.0, "distressed")]
    else:  # wait_48h
        # Waiting cools down irritation
        if sentiment == "negative":
            sentiment_transitions = [(0.40, "neutral"), (0.60, "negative")]
        elif sentiment == "distressed":
            sentiment_transitions = [(0.25, "negative"), (0.75, "distressed")]
        else:
            sentiment_transitions = [(1.0, "neutral")]

    # Combine independent transitions
    distribution = []
    for p_days, next_days in days_transitions:
        for p_sent, next_sent in sentiment_transitions:
            prob = p_days * p_sent
            next_state = (next_attempts, next_days, ltv, next_sent)
            distribution.append((prob, next_state))

    return distribution
