"""
CMDP Value Iteration & Policy Solver.

Solves the Bellman Optimality Equation:
V*(s) = max_a [ R(s, a) + γ ∑_s' P(s' | s, a) V*(s') ]
π*(s) = argmax_a [ R(s, a) + γ ∑_s' P(s' | s, a) V*(s') ]

Serializes the converged policy lookup table to policy/stopping_policy.json.
"""
import json
from pathlib import Path
from typing import Dict, Any, Tuple

from policy.mdp_definition import (
    get_all_states,
    state_to_key,
    key_to_state,
    reward_fn,
    transition_fn,
    ACTIONS
)

POLICY_FILE_PATH = Path(__file__).resolve().parent / "stopping_policy.json"


def run_value_iteration(
    gamma: float = 0.95,
    theta: float = 1e-4,
    max_iterations: int = 1000
) -> Tuple[Dict[str, float], Dict[str, str], int, float]:
    """
    Executes Value Iteration across all 243 discrete states.
    
    Returns:
        (V_star, policy_star, iterations_count, final_delta)
    """
    states = get_all_states()
    V: Dict[Tuple[int, str, str, str], float] = {s: 0.0 for s in states}
    policy: Dict[Tuple[int, str, str, str], str] = {s: "stop" for s in states}

    iteration = 0
    delta = float("inf")

    while delta > theta and iteration < max_iterations:
        delta = 0.0
        new_V = {}

        for s in states:
            attempts, days, ltv, sentiment = s

            # Base absorbing state
            if attempts == 0:
                new_V[s] = 0.0
                policy[s] = "stop"
                continue

            best_val = float("-inf")
            best_act = "stop"

            for a in ACTIONS:
                r = reward_fn(s, a)
                expected_future_val = 0.0
                
                transitions = transition_fn(s, a)
                for prob, next_state in transitions:
                    expected_future_val += prob * V[next_state]

                q_val = r + gamma * expected_future_val

                if q_val > best_val:
                    best_val = q_val
                    best_act = a

            new_V[s] = best_val
            policy[s] = best_act
            delta = max(delta, abs(new_V[s] - V[s]))

        V = new_V
        iteration += 1

    # Format policy as flat serializable dictionary
    serialized_policy = {state_to_key(s): policy[s] for s in states}
    serialized_values = {state_to_key(s): round(V[s], 4) for s in states}

    # Save to JSON
    POLICY_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(POLICY_FILE_PATH, "w") as f:
        json.dump(serialized_policy, f, indent=2)

    print(f"✅ CMDP Value Iteration converged in {iteration} iterations (Δ = {delta:.6f} < θ = {theta})")
    print(f"✅ Serialized 243-state policy to: {POLICY_FILE_PATH}")

    return serialized_values, serialized_policy, iteration, delta


def load_stopping_policy() -> Dict[str, str]:
    """
    Loads precomputed stopping policy from JSON lookup table.
    """
    if not POLICY_FILE_PATH.exists():
        _, policy, _, _ = run_value_iteration()
        return policy

    with open(POLICY_FILE_PATH, "r") as f:
        return json.load(f)


if __name__ == "__main__":
    run_value_iteration()
