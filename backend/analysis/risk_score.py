def calculate_risk(
    transaction_count=0,
    connected_entities=0,
    rapid_transfer=False,
    cross_channel_nexus=False,
    mule_count=0,
    nodes=None,
    edges=None
):
    """
    Computes calibrated overall case threat score (0-100) and
    per-entity threat scores based on graph topology, financial velocity,
    and cross-channel correlation.
    """
    score = 0
    reasons = []

    # 1. Transaction Volume & Complexity
    if transaction_count >= 6:
        score += 25
        reasons.append(f"High transaction frequency detected ({transaction_count} transfers)")
    elif transaction_count >= 3:
        score += 15
        reasons.append(f"Multiple financial transactions detected ({transaction_count} transfers)")
    elif transaction_count > 0:
        score += 5

    # 2. Network Footprint (Entity Breadth)
    if connected_entities >= 8:
        score += 20
        reasons.append(f"Broad syndication footprint ({connected_entities} correlated entities)")
    elif connected_entities >= 4:
        score += 12
        reasons.append("Multi-party entity network involved")

    # 3. Rapid Fund Movement Velocity (Laundering)
    if rapid_transfer:
        score += 25
        reasons.append("High-velocity rapid fund transfer detected (<60m layering)")

    # 4. Cross-Channel Nexus (Telecom + Banking + Social Chat)
    if cross_channel_nexus:
        score += 20
        reasons.append("Cross-channel correlation confirmed (Telecom CDR + Chat + Banking Nexus)")

    # 5. Intermediary Mule Detection
    if mule_count >= 2:
        score += 20
        reasons.append(f"Organized mule network detected ({mule_count} intermediary accounts)")
    elif mule_count == 1:
        score += 10
        reasons.append("Suspected money mule account identified")

    score = min(max(score, 0), 100)

    if score >= 80:
        level = "CRITICAL"
    elif score >= 60:
        level = "HIGH"
    elif score >= 35:
        level = "MEDIUM"
    else:
        level = "LOW"

    # ============================================================
    # PER-ENTITY RISK ASSESSMENT
    # ============================================================
    entity_risks = {}
    if nodes:
        for node in nodes:
            n_id = node.get("id")
            n_type = node.get("type")
            n_role = node.get("role", "UNKNOWN")
            inflow = node.get("total_inflow", 0.0)
            outflow = node.get("total_outflow", 0.0)
            chat_mentions = node.get("chat_mentions", 0)
            betweenness = node.get("betweenness", 0.0)

            e_score = 15
            e_reasons = []

            if "SUSPECT" in n_role:
                e_score += 55
                e_reasons.append("Identified as suspicious communication coordinator")
            elif n_role == "MULE_ACCOUNT":
                e_score += 65
                e_reasons.append("Identified as transit money mule account (Pass-through flow)")
            elif n_role == "FRAUD_UPI":
                e_score += 70
                e_reasons.append("UPI identity disseminated in fraudulent solicitation chat")
            elif n_role == "VICTIM_ACCOUNT":
                e_score = 10
                e_reasons.append("Originating funds source (Presumed victim)")
            elif n_role == "CASHOUT_NODE":
                e_score += 60
                e_reasons.append("Destination cash-out sink node")

            if chat_mentions > 0 and n_role != "VICTIM_ACCOUNT":
                e_score += 15
                e_reasons.append("Explicitly cited in chat communication records")

            if betweenness > 0.2:
                e_score += 10
                e_reasons.append("High topological betweenness (Key network bridge)")

            e_score = min(max(e_score, 0), 100)

            if e_score >= 80:
                e_level = "CRITICAL"
            elif e_score >= 60:
                e_level = "HIGH"
            elif e_score >= 35:
                e_level = "MEDIUM"
            else:
                e_level = "LOW"

            entity_risks[n_id] = {
                "id": n_id,
                "score": e_score,
                "level": e_level,
                "role": n_role,
                "reasons": e_reasons
            }

    return {
        "score": score,
        "level": level,
        "reasons": reasons,
        "entity_risks": entity_risks
    }