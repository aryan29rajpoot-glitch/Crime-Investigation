import networkx as nx


def build_graph(cdr_records, bank_records, chat_data):
    """
    Builds a directed NetworkX graph correlating CDR calls, bank transactions,
    and chat messages. Computes centrality metrics, financial volume,
    and infers forensic roles (Victim, Mule, Suspect, etc.).
    """
    g = nx.DiGraph()

    # Track metadata per node
    node_meta = {}

    def ensure_node(node_id, node_type, label=None):
        if not node_id:
            return
        node_id = str(node_id).strip()
        if node_id not in g:
            g.add_node(node_id, type=node_type)
        if node_id not in node_meta:
            node_meta[node_id] = {
                "id": node_id,
                "type": node_type,
                "label": label or node_id,
                "total_inflow": 0.0,
                "total_outflow": 0.0,
                "call_count": 0,
                "chat_mentions": 0,
                "first_seen": None,
                "last_seen": None,
                "channels": set(),
                "role": "UNKNOWN"
            }
        node_meta[node_id]["channels"].add(node_type)

    def update_timestamps(node_id, ts):
        if not ts or ts == "None":
            return
        meta = node_meta.get(node_id)
        if not meta:
            return
        ts_str = str(ts)
        if not meta["first_seen"] or ts_str < meta["first_seen"]:
            meta["first_seen"] = ts_str
        if not meta["last_seen"] or ts_str > meta["last_seen"]:
            meta["last_seen"] = ts_str

    # ============================================================
    # 1. CALL DETAIL RECORDS (CDR)
    # ============================================================
    for record in cdr_records:
        caller = record.get("caller")
        receiver = record.get("receiver")
        ts = record.get("timestamp")
        duration = record.get("duration")

        if not caller or not receiver:
            continue

        ensure_node(caller, "phone")
        ensure_node(receiver, "phone")
        update_timestamps(caller, ts)
        update_timestamps(receiver, ts)

        node_meta[caller]["call_count"] += 1
        node_meta[receiver]["call_count"] += 1

        g.add_edge(
            caller,
            receiver,
            relationship="CALL",
            duration=duration,
            timestamp=str(ts) if ts else None,
            amount=None,
            channel="telecom"
        )

    # ============================================================
    # 2. BANK TRANSACTIONS
    # ============================================================
    for record in bank_records:
        source = record.get("source")
        target = record.get("target")
        rel = record.get("relationship", "TRANSFER")
        amount = record.get("amount")
        ts = record.get("timestamp")

        if not source or not target:
            continue

        src_type = "upi" if "@" in source else "bank_account"
        tgt_type = "upi" if "@" in target else "bank_account"

        ensure_node(source, src_type)
        ensure_node(target, tgt_type)
        update_timestamps(source, ts)
        update_timestamps(target, ts)

        if amount:
            try:
                amt_val = float(amount)
                node_meta[source]["total_outflow"] += amt_val
                node_meta[target]["total_inflow"] += amt_val
            except (ValueError, TypeError):
                amt_val = None
        else:
            amt_val = None

        g.add_edge(
            source,
            target,
            relationship=rel,
            amount=amt_val,
            timestamp=str(ts) if ts else None,
            channel="banking"
        )

    # ============================================================
    # 3. CHAT EVIDENCE
    # ============================================================
    chat_links = chat_data.get("chat_links", []) if isinstance(chat_data, dict) else []

    # Also register standalone phones and UPIs from chat
    if isinstance(chat_data, dict):
        for p in chat_data.get("phones", []):
            ensure_node(p, "phone")
        for u in chat_data.get("upi_ids", []):
            ensure_node(u, "upi")

    for link in chat_links:
        phone = link.get("phone")
        upi = link.get("upi") or link.get("account")
        ts = link.get("timestamp")
        amount = link.get("amount")
        snippet = link.get("snippet", "")

        if not phone or not upi:
            continue

        tgt_type = "upi" if "@" in upi else "bank_account"
        ensure_node(phone, "phone")
        ensure_node(upi, tgt_type)
        update_timestamps(phone, ts)
        update_timestamps(upi, ts)

        node_meta[phone]["chat_mentions"] += 1
        node_meta[upi]["chat_mentions"] += 1

        g.add_edge(
            phone,
            upi,
            relationship="CHAT_LINK",
            amount=amount,
            timestamp=str(ts) if ts else None,
            snippet=snippet,
            channel="chat"
        )

    # ============================================================
    # 4. NETWORKX CENTRALITY & TOPOLOGICAL METRICS
    # ============================================================
    if len(g) > 0:
        degree_centrality = nx.degree_centrality(g)
        betweenness_centrality = nx.betweenness_centrality(g)
    else:
        degree_centrality = {}
        betweenness_centrality = {}

    # ============================================================
    # 5. ROLE INFERENCE (Victim, Mule, Suspect, Cashout)
    # ============================================================
    for node_id, meta in node_meta.items():
        in_deg = g.in_degree(node_id)
        out_deg = g.out_degree(node_id)
        inflow = meta["total_inflow"]
        outflow = meta["total_outflow"]
        n_type = meta["type"]

        if n_type == "phone":
            # Phone role inference
            if meta["chat_mentions"] > 0 and out_deg > 0:
                meta["role"] = "SUSPECT_CALLER"
            elif out_deg > in_deg and out_deg >= 2:
                meta["role"] = "COORDINATOR"
            elif in_deg > 0 and meta["chat_mentions"] == 0:
                meta["role"] = "ASSOCIATE"
            else:
                meta["role"] = "SUSPECT"
        elif n_type in ("bank_account", "upi"):
            # Financial role inference
            if inflow > 0 and outflow > 0:
                # Classic pass-through money mule
                meta["role"] = "MULE_ACCOUNT"
            elif outflow > 0 and inflow == 0:
                # Originating debited account -> victim account
                meta["role"] = "VICTIM_ACCOUNT"
            elif inflow > 0 and outflow == 0:
                # Destination cash-out layer
                meta["role"] = "CASHOUT_NODE"
            elif "@" in node_id and meta["chat_mentions"] > 0:
                meta["role"] = "FRAUD_UPI"
            else:
                meta["role"] = "FINANCIAL_ENTITY"

    # ============================================================
    # 6. EXPORT FORMATTED NODES & EDGES FOR UI & API
    # ============================================================
    formatted_nodes = []
    for node_id in g.nodes():
        meta = node_meta.get(node_id, {})
        formatted_nodes.append({
            "id": node_id,
            "type": meta.get("type", g.nodes[node_id].get("type", "unknown")),
            "role": meta.get("role", "UNKNOWN"),
            "total_inflow": meta.get("total_inflow", 0.0),
            "total_outflow": meta.get("total_outflow", 0.0),
            "call_count": meta.get("call_count", 0),
            "chat_mentions": meta.get("chat_mentions", 0),
            "first_seen": meta.get("first_seen"),
            "last_seen": meta.get("last_seen"),
            "degree_centrality": round(degree_centrality.get(node_id, 0.0), 3),
            "betweenness": round(betweenness_centrality.get(node_id, 0.0), 3),
            "in_degree": g.in_degree(node_id),
            "out_degree": g.out_degree(node_id)
        })

    formatted_edges = []
    for u, v, data in g.edges(data=True):
        formatted_edges.append({
            "source": u,
            "target": v,
            "relationship": data.get("relationship", "CONNECTED"),
            "amount": data.get("amount"),
            "timestamp": data.get("timestamp"),
            "duration": data.get("duration"),
            "snippet": data.get("snippet"),
            "channel": data.get("channel", "general")
        })

    return {
        "graph_instance": g,
        "nodes": formatted_nodes,
        "edges": formatted_edges,
        "metrics": {
            "node_count": len(formatted_nodes),
            "edge_count": len(formatted_edges),
            "mule_nodes": [n["id"] for n in formatted_nodes if n["role"] == "MULE_ACCOUNT"],
            "suspect_nodes": [n["id"] for n in formatted_nodes if "SUSPECT" in n["role"]],
            "victim_nodes": [n["id"] for n in formatted_nodes if n["role"] == "VICTIM_ACCOUNT"],
            "density": round(nx.density(g), 3) if len(g) > 1 else 0.0
        }
    }