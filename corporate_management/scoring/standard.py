# corporate_management/scoring/standard.py

def compute_standard_score(
    base_score: int,
    *,
    hint_used: bool = False,
    hint_penalty: int = 0,
):
    """
    Standard scoring:
    - Full base score if correct
    - Subtract hint penalty if hint used
    - Never below 0
    """

    penalty = hint_penalty if hint_used else 0
    final_score = max(base_score - penalty, 0)

    meta = {
        "type": "standard",
        "base_score": base_score,
        "hint_used": hint_used,
        "hint_penalty": penalty,
        "final_score": final_score,
    }

    return final_score, meta
