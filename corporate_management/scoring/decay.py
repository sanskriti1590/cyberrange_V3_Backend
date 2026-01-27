# corporate/scoring/decay.py

import math
import datetime
from typing import Tuple, Dict, Optional


def _minutes_between(start: datetime.datetime, end: datetime.datetime) -> float:
    """Returns difference in minutes (float)."""
    delta = end - start
    return delta.total_seconds() / 60.0


def compute_decay_score(
    base_score: int,
    scoring_config: Dict,
    *,
    start_time: Optional[datetime.datetime] = None,
    first_visible_at: Optional[datetime.datetime] = None,
    attempts: int = 1,
    event_time: Optional[datetime.datetime] = None,
    hint_used: bool = False,
    hint_penalty: int = 0,
) -> Tuple[int, Dict]:
    """
    Generic decay scorer for FLAG and MILESTONE.

    Rules:
    - Apply decay first
    - If final score > min_score AND hint_used → apply hint penalty
    - Never allow score below min_score
    """

    now = event_time or datetime.datetime.utcnow()

    meta = {
        "type": scoring_config.get("type", "standard"),
        "base_score": int(base_score),
        "mode": None,
        "decayed": False,
        "decay_penalty": 0,
        "hint_used": hint_used,
        "hint_penalty": int(hint_penalty) if hint_used else 0,
        "final_score": int(base_score),
    }

    # ---------- NO DECAY ----------
    if scoring_config.get("type") != "decay":
        return int(base_score), meta

    decay = scoring_config.get("decay") or {}
    mode = decay.get("mode", "time")
    meta["mode"] = mode

    min_score = int(decay.get("min_score", 0))
    penalty_per_interval = int(decay.get("penalty_per_interval", 0))

    final_score = int(base_score)

    # ---------- TIME BASED DECAY ----------
    if mode == "time":
        if not start_time:
            return final_score, meta

        start_after = int(decay.get("start_after_minutes", 0))
        interval = max(int(decay.get("interval_minutes", 1)), 1)

        elapsed_minutes = _minutes_between(start_time, now)

        if elapsed_minutes > start_after:
            effective_minutes = elapsed_minutes - start_after
            intervals_passed = math.floor(effective_minutes / interval)

            decay_penalty = intervals_passed * penalty_per_interval
            final_score = max(base_score - decay_penalty, min_score)

            meta.update({
                "decayed": intervals_passed > 0,
                "elapsed_minutes": round(elapsed_minutes, 2),
                "intervals_passed": intervals_passed,
                "decay_penalty": decay_penalty,
            })

    # ---------- ATTEMPT BASED DECAY ----------
    elif mode == "attempt":
        decay_penalty = max((attempts - 1), 0) * penalty_per_interval
        final_score = max(base_score - decay_penalty, min_score)

        meta.update({
            "decayed": attempts > 1,
            "attempts": attempts,
            "decay_penalty": decay_penalty,
        })

    # ---------- HINT PENALTY (AFTER DECAY) ----------
    # Apply ONLY if score is above min_score
    if hint_used and hint_penalty and final_score > min_score:
        final_score = max(final_score - hint_penalty, min_score)
        meta["hint_penalty_applied"] = True
    else:
        meta["hint_penalty_applied"] = False

    meta["final_score"] = int(final_score)
    return int(final_score), meta
