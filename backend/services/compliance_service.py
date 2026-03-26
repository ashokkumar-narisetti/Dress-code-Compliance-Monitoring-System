"""
compliance_service.py - Dress code rules and deduplication utilities.
"""

from collections import Counter
from typing import Dict, List, Optional, Tuple


def normalize_gender(value: Optional[str]) -> str:
    if not value:
        return "unknown"
    v = value.strip().lower()
    if v.startswith("m"):
        return "male"
    if v.startswith("f"):
        return "female"
    return "unknown"


def evaluate_dress_code_from_classes(
    gender: Optional[str],
    detected_class_names: List[str],
) -> Tuple[bool, List[str], Optional[bool], Optional[bool]]:
    """
    Map YOLO class names (detection head) to tuck/shoes booleans, then apply rules.
    Returns (is_compliant, violations, shirt_tucked, shoes_present).
    """
    normalized = [str(n).strip().lower().replace(" ", "_") for n in detected_class_names]
    blob = " ".join(normalized)

    def _has(*keywords: str) -> bool:
        return any(kw in blob for kw in keywords)

    shoes_no = _has(
        "no_shoe", "no_shoes", "barefoot", "bare_feet", "sandals", "flip_flop", "flipflop",
        "without_shoes",
    )
    shoes_yes = _has("shoe", "shoes", "footwear", "formal_shoes", "black_shoes", "wearing_shoes", "has_shoes")
    shoes_present: Optional[bool] = None
    if shoes_no:
        shoes_present = False
    elif shoes_yes:
        shoes_present = True

    untucked_hit = _has("untucked", "shirt_untucked", "untuck", "shirt_out")
    tucked_hit = _has("tucked", "shirt_tucked", "tucked_in", "tuck_in")
    shirt_tucked: Optional[bool] = None
    if untucked_hit:
        shirt_tucked = False
    elif tucked_hit:
        shirt_tucked = True

    ok, violations = evaluate_dress_code(gender, shirt_tucked, shoes_present)
    return ok, violations, shirt_tucked, shoes_present


def evaluate_dress_code(
    gender: Optional[str],
    shirt_tucked: Optional[bool],
    shoes_present: Optional[bool],
) -> Tuple[bool, List[str]]:
    """
    Hard-coded rules:
    - Boys: shirt must be tucked + shoes mandatory
    - Girls: shoes mandatory
    """
    normalized = normalize_gender(gender)
    violations: List[str] = []

    if shoes_present is False:
        violations.append("No shoes detected")

    if normalized == "male" and shirt_tucked is False:
        violations.append("Shirt not tucked")

    # For unknown gender we only enforce shoes to reduce false positives.
    return len(violations) == 0, violations


def majority_vote_frame_results(frame_results: List[Dict]) -> Dict:
    """
    Consolidates multiple observations for the same student using majority vote.
    """
    if not frame_results:
        return {
            "confidence": 0.0,
            "is_compliant": False,
            "violations": ["No observations"],
            "frame_path": None,
        }

    compliant_count = sum(1 for r in frame_results if r["is_compliant"])
    non_compliant_count = len(frame_results) - compliant_count

    # Majority vote wins. If tie, choose non-compliant (risk-aware default).
    final_compliant = compliant_count > non_compliant_count

    all_reasons: List[str] = []
    for r in frame_results:
        all_reasons.extend(r.get("violations", []))
    reason_counts = Counter(all_reasons)

    if final_compliant:
        final_reasons: List[str] = []
    else:
        # Keep reasons seen in at least half of non-compliant observations.
        min_support = max(1, non_compliant_count // 2)
        final_reasons = [
            reason
            for reason, count in reason_counts.items()
            if count >= min_support
        ] or list(reason_counts.keys())

    # Use highest-confidence frame as evidence.
    best = sorted(frame_results, key=lambda x: x.get("confidence", 0.0), reverse=True)[0]
    avg_conf = round(
        sum(float(r.get("confidence", 0.0)) for r in frame_results) / len(frame_results),
        3,
    )

    return {
        "confidence": avg_conf,
        "is_compliant": final_compliant,
        "violations": final_reasons,
        "frame_path": best.get("frame_path"),
    }
