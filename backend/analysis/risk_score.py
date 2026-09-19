def calculate_risk(
    transaction_count,
    connected_entities,
    rapid_transfer=False
):

    score = 0
    reasons = []

    if transaction_count >= 3:
        score += 20
        reasons.append(
            "Multiple transactions detected"
        )

    if connected_entities >= 5:
        score += 25
        reasons.append(
            "Entity has multiple connections"
        )

    if rapid_transfer:
        score += 30
        reasons.append(
            "Rapid fund transfer detected"
        )

    score = min(score, 100)

    if score >= 80:
        level = "CRITICAL"
    elif score >= 60:
        level = "HIGH"
    elif score >= 30:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "score": score,
        "level": level,
        "reasons": reasons
    }