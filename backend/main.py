import os
import re
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from parsers.cdr_parser import parse_cdr
from parsers.bank_parser import parse_bank
from parsers.chat_parser import parse_chat
from extraction.entities import extract_entities
from correlation.graph import build_graph
from analysis.risk_score import calculate_risk
import case_manager

# ============================================================
# APP CONFIG
# ============================================================

app = FastAPI(
    title="FraudLens API",
    description="Digital Forensics & Cross-Channel Artifact Correlation Platform",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Initialize default case storage on boot
case_manager.ensure_cases_dir()


# ============================================================
# UTILITIES
# ============================================================

def parse_iso_or_custom_timestamp(ts_str):
    if not ts_str:
        return None
    s = str(ts_str).strip()
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%y, %H:%M",
        "%d/%m/%Y, %H:%M"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def detect_rapid_transfer(bank_records, threshold_minutes=60):
    """
    Detects high-velocity pass-through transfers (layering) where funds
    enter an account via CREDIT and leave via DEBIT/TRANSFER within threshold_minutes.
    """
    if not bank_records or len(bank_records) < 2:
        return {
            "detected": False,
            "fastest_delta_minutes": None,
            "flagged_accounts": []
        }

    # Group incoming credits and outgoing debits by bank account
    account_credits = {}
    account_debits = {}

    for record in bank_records:
        ts = parse_iso_or_custom_timestamp(record.get("timestamp"))
        if not ts:
            continue

        acc = record.get("account")
        rel = record.get("relationship", "").upper()

        if not acc:
            continue

        if rel in ["CREDIT", "CR", "IN"]:
            account_credits.setdefault(acc, []).append((ts, record))
        elif rel in ["DEBIT", "DR", "OUT", "TRANSFER"]:
            account_debits.setdefault(acc, []).append((ts, record))

    flagged_accounts = set()
    fastest_delta = None

    for acc, credits in account_credits.items():
        debits = account_debits.get(acc, [])
        for c_time, c_rec in credits:
            for d_time, d_rec in debits:
                if d_time >= c_time:
                    delta_mins = (d_time - c_time).total_seconds() / 60.0
                    if delta_mins <= threshold_minutes:
                        flagged_accounts.add(acc)
                        if fastest_delta is None or delta_mins < fastest_delta:
                            fastest_delta = delta_mins

    # Also detect multiple fast transactions anywhere in sequence
    all_timestamps = []
    for r in bank_records:
        parsed_t = parse_iso_or_custom_timestamp(r.get("timestamp"))
        if parsed_t:
            all_timestamps.append(parsed_t)
    all_timestamps.sort()

    for i in range(len(all_timestamps) - 1):
        diff = (all_timestamps[i + 1] - all_timestamps[i]).total_seconds() / 60.0
        if diff <= threshold_minutes:
            if fastest_delta is None or diff < fastest_delta:
                fastest_delta = diff

    detected = len(flagged_accounts) > 0 or (fastest_delta is not None and fastest_delta <= threshold_minutes)

    return {
        "detected": detected,
        "fastest_delta_minutes": round(fastest_delta, 1) if fastest_delta is not None else None,
        "flagged_accounts": list(flagged_accounts)
    }


def generate_timeline(cdr_records, bank_records, chat_messages):
    """
    Builds a unified chronological timeline across telecom calls,
    financial transfers, and chat messages.
    """
    events = []

    for c in cdr_records:
        ts = c.get("timestamp")
        events.append({
            "timestamp": ts,
            "type": "CALL",
            "channel": "telecom",
            "source": c.get("caller"),
            "target": c.get("receiver"),
            "description": f"Voice call from {c.get('caller')} to {c.get('receiver')} ({c.get('duration', 0)}s)"
        })

    for b in bank_records:
        ts = b.get("timestamp")
        amt_str = f"₹{b.get('amount'):,}" if b.get("amount") else "amount unspecified"
        events.append({
            "timestamp": ts,
            "type": b.get("relationship", "TRANSFER"),
            "channel": "banking",
            "source": b.get("source"),
            "target": b.get("target"),
            "amount": b.get("amount"),
            "description": f"{b.get('relationship')} transfer of {amt_str} from {b.get('source')} to {b.get('target')}"
        })

    for m in chat_messages:
        ts = m.get("timestamp")
        events.append({
            "timestamp": ts,
            "type": "CHAT",
            "channel": "chat",
            "source": m.get("sender"),
            "target": m.get("upis")[0] if m.get("upis") else None,
            "description": f"Message from {m.get('sender')}: \"{m.get('body')[:80]}\""
        })

    # Sort events by timestamp where available
    def sort_key(ev):
        parsed = parse_iso_or_custom_timestamp(ev["timestamp"])
        return parsed or datetime.max

    events.sort(key=sort_key)
    return events


# ============================================================
# CORE CASE ANALYSIS ENGINE
# ============================================================

def analyze_case_data(case_info):
    cdr_records = []
    bank_records = []
    chat_data = {"phones": [], "upi_ids": [], "bank_accounts": [], "chat_links": [], "messages": [], "raw_text": ""}

    # 1. Parse CDR
    if case_info.get("cdr_path") and os.path.exists(case_info["cdr_path"]):
        try:
            cdr_records = parse_cdr(case_info["cdr_path"])
        except Exception as err:
            print("CDR Parse Error:", err)

    # 2. Parse Bank
    if case_info.get("bank_path") and os.path.exists(case_info["bank_path"]):
        try:
            bank_records = parse_bank(case_info["bank_path"])
        except Exception as err:
            print("Bank Parse Error:", err)

    # 3. Parse Chat
    if case_info.get("chat_path") and os.path.exists(case_info["chat_path"]):
        try:
            chat_data = parse_chat(case_info["chat_path"])
        except Exception as err:
            print("Chat Parse Error:", err)

    # 4. Extract Entities
    combined_raw_text = (
        str(cdr_records) + "\n" +
        str(bank_records) + "\n" +
        chat_data.get("raw_text", "")
    )
    entities = extract_entities(combined_raw_text)

    # Merge explicitly discovered entities from parsers
    for c in cdr_records:
        if c.get("caller") and c["caller"] not in entities["phones"]:
            entities["phones"].append(c["caller"])
        if c.get("receiver") and c["receiver"] not in entities["phones"]:
            entities["phones"].append(c["receiver"])

    for b in bank_records:
        src = b.get("source")
        tgt = b.get("target")
        for val in [src, tgt]:
            if not val:
                continue
            if "@" in val and val not in entities["upi_ids"]:
                entities["upi_ids"].append(val)
            elif not "@" in val and not val.startswith("+") and val not in entities["bank_accounts"]:
                entities["bank_accounts"].append(val)

    for u in chat_data.get("upi_ids", []):
        if u not in entities["upi_ids"]:
            entities["upi_ids"].append(u)

    entities["phones"].sort()
    entities["upi_ids"].sort()
    entities["bank_accounts"].sort()

    # 5. Build NetworkX Graph
    graph_res = build_graph(cdr_records, bank_records, chat_data)
    node_data = graph_res["nodes"]
    edge_data = graph_res["edges"]
    metrics = graph_res["metrics"]

    # 6. Temporal Velocity Detection
    rapid_info = detect_rapid_transfer(bank_records, threshold_minutes=60)

    # 7. Cross-Channel Nexus Detection
    # Check if a phone in CDR also appears as a sender or entity in Chat
    cdr_phones = set()
    for c in cdr_records:
        if c.get("caller"): cdr_phones.add(c["caller"])
        if c.get("receiver"): cdr_phones.add(c["receiver"])

    chat_phones = set(chat_data.get("phones", []))
    nexus_phones = cdr_phones.intersection(chat_phones)
    cross_channel_nexus = len(nexus_phones) > 0

    # 8. Calibrated Risk Analysis
    risk_analysis = calculate_risk(
        transaction_count=len(bank_records),
        connected_entities=len(node_data),
        rapid_transfer=rapid_info["detected"],
        cross_channel_nexus=cross_channel_nexus,
        mule_count=len(metrics["mule_nodes"]),
        nodes=node_data,
        edges=edge_data
    )

    # Attach per-node risk to node_data for frontend rendering
    for node in node_data:
        n_id = node["id"]
        if n_id in risk_analysis["entity_risks"]:
            node["risk"] = risk_analysis["entity_risks"][n_id]

    # 9. Chronological Timeline
    timeline = generate_timeline(cdr_records, bank_records, chat_data.get("messages", []))

    return {
        "case_id": case_info["case_id"],
        "metadata": {
            "title": case_info.get("title", case_info["case_id"]),
            "description": case_info.get("description", ""),
            "created_at": case_info.get("created_at", ""),
            "is_default": case_info.get("is_default", False)
        },
        "evidence": {
            "cdr_records": len(cdr_records),
            "bank_records": len(bank_records),
            "chat_evidence": bool(chat_data.get("raw_text", "").strip()),
            "chat_messages": len(chat_data.get("messages", [])),
            "rapid_transfer_flag": rapid_info["detected"],
            "cross_channel_nexus": cross_channel_nexus
        },
        "entities": entities,
        "graph": {
            "nodes": len(node_data),
            "relationships": len(edge_data),
            "node_data": node_data,
            "edge_data": edge_data,
            "metrics": metrics
        },
        "risk_analysis": risk_analysis,
        "timeline": timeline
    }


# ============================================================
# ENDPOINTS
# ============================================================

@app.get("/")
def home():
    return {
        "message": "FraudLens Digital Forensics API v2.0 is running",
        "active_cases": len(case_manager.list_cases())
    }


@app.get("/cases")
def get_cases():
    """List all available investigation cases."""
    return {
        "cases": case_manager.list_cases()
    }


@app.post("/cases/upload")
async def upload_case(
    case_id: str = Form(...),
    title: str = Form(""),
    description: str = Form(""),
    cdr_file: Optional[UploadFile] = File(None),
    bank_file: Optional[UploadFile] = File(None),
    chat_file: Optional[UploadFile] = File(None)
):
    """
    Create a new case by uploading CDR, Bank, and Chat evidence files.
    """
    case_id_clean = case_id.strip().replace(" ", "_").upper()
    if not case_id_clean:
        raise HTTPException(status_code=400, detail="Invalid Case ID")

    cdr_bytes = await cdr_file.read() if cdr_file else None
    bank_bytes = await bank_file.read() if bank_file else None
    chat_bytes = await chat_file.read() if chat_file else None

    if not cdr_bytes and not bank_bytes and not chat_bytes:
        raise HTTPException(status_code=400, detail="At least one evidence file (CDR, Bank, or Chat) must be uploaded.")

    created = case_manager.create_case(
        case_id=case_id_clean,
        title=title or f"Investigation {case_id_clean}",
        description=description or "Custom uploaded investigation dossier",
        cdr_bytes=cdr_bytes,
        bank_bytes=bank_bytes,
        chat_bytes=chat_bytes
    )

    # Immediately run analysis to verify case integrity
    analysis = analyze_case_data(created)
    return {
        "message": f"Case {case_id_clean} uploaded and analyzed successfully",
        "case": created,
        "analysis": analysis
    }


@app.delete("/cases/{case_id}")
def delete_case(case_id: str):
    """Delete a custom case."""
    if case_id == "CYBER-2026-001":
        raise HTTPException(status_code=400, detail="Default demonstration case cannot be deleted.")
    success = case_manager.delete_case(case_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
    return {
        "message": f"Case {case_id} deleted successfully"
    }


@app.get("/cases/{case_id}/analyze")
def analyze_case(case_id: str):
    """Run full correlation and forensic analysis on a specific case."""
    case_info = case_manager.get_case(case_id)
    if not case_info:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    return analyze_case_data(case_info)


@app.get("/analyze")
def analyze_default():
    """Default compatibility endpoint analyzing case CYBER-2026-001."""
    case_info = case_manager.get_case("CYBER-2026-001")
    if not case_info:
        raise HTTPException(status_code=404, detail="Default case not found.")
    return analyze_case_data(case_info)


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )