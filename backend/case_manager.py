import os
import json
import shutil
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CASES_DIR = os.path.join(DATA_DIR, "cases")


def ensure_cases_dir():
    os.makedirs(CASES_DIR, exist_ok=True)
    seed_default_case()


def seed_default_case():
    default_case_id = "CYBER-2026-001"
    case_path = os.path.join(CASES_DIR, default_case_id)
    os.makedirs(case_path, exist_ok=True)

    # Copy demo files if not present in the default case directory
    demo_files = {
        "cdr.csv": os.path.join(DATA_DIR, "cdr.csv"),
        "bank.csv": os.path.join(DATA_DIR, "bank.csv"),
        "chats.txt": os.path.join(DATA_DIR, "chats.txt")
    }

    for fname, src in demo_files.items():
        dst = os.path.join(case_path, fname)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)

    meta_file = os.path.join(case_path, "metadata.json")
    if not os.path.exists(meta_file):
        metadata = {
            "case_id": default_case_id,
            "title": "Operation Ghost Call (UPI Phishing & Mule Ring)",
            "description": "Cross-channel telecom and bank fraud involving multi-stage UPI layering and voice extortion.",
            "created_at": "2026-09-10T10:15:00Z",
            "is_default": True
        }
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)


def list_cases():
    ensure_cases_dir()
    cases = []
    for item in sorted(os.listdir(CASES_DIR)):
        case_dir = os.path.join(CASES_DIR, item)
        if not os.path.isdir(case_dir):
            continue
        meta_path = os.path.join(case_dir, "metadata.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                meta = {"case_id": item, "title": item}
        else:
            meta = {
                "case_id": item,
                "title": f"Case {item}",
                "description": "Investigative evidence dossier",
                "created_at": datetime.utcnow().isoformat() + "Z"
            }

        # Check existing evidence files
        meta["has_cdr"] = os.path.exists(os.path.join(case_dir, "cdr.csv"))
        meta["has_bank"] = os.path.exists(os.path.join(case_dir, "bank.csv"))
        meta["has_chat"] = os.path.exists(os.path.join(case_dir, "chats.txt"))
        cases.append(meta)

    return cases


def get_case(case_id):
    ensure_cases_dir()
    case_path = os.path.join(CASES_DIR, case_id)
    if not os.path.exists(case_path):
        return None

    meta_path = os.path.join(case_path, "metadata.json")
    meta = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            pass

    return {
        "case_id": case_id,
        "title": meta.get("title", case_id),
        "description": meta.get("description", ""),
        "created_at": meta.get("created_at", datetime.utcnow().isoformat()),
        "is_default": meta.get("is_default", False),
        "cdr_path": os.path.join(case_path, "cdr.csv") if os.path.exists(os.path.join(case_path, "cdr.csv")) else None,
        "bank_path": os.path.join(case_path, "bank.csv") if os.path.exists(os.path.join(case_path, "bank.csv")) else None,
        "chat_path": os.path.join(case_path, "chats.txt") if os.path.exists(os.path.join(case_path, "chats.txt")) else None
    }


def create_case(case_id, title, description, cdr_bytes=None, bank_bytes=None, chat_bytes=None):
    ensure_cases_dir()
    case_id = case_id.strip().replace(" ", "_").upper()
    case_path = os.path.join(CASES_DIR, case_id)
    os.makedirs(case_path, exist_ok=True)

    if cdr_bytes:
        with open(os.path.join(case_path, "cdr.csv"), "wb") as f:
            f.write(cdr_bytes)

    if bank_bytes:
        with open(os.path.join(case_path, "bank.csv"), "wb") as f:
            f.write(bank_bytes)

    if chat_bytes:
        with open(os.path.join(case_path, "chats.txt"), "wb") as f:
            f.write(chat_bytes)

    meta = {
        "case_id": case_id,
        "title": title or f"Case {case_id}",
        "description": description or "Uploaded evidence investigation",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "is_default": False
    }

    with open(os.path.join(case_path, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return get_case(case_id)


def delete_case(case_id):
    ensure_cases_dir()
    case_path = os.path.join(CASES_DIR, case_id)
    if not os.path.exists(case_path):
        return False
    if case_id == "CYBER-2026-001":
        return False  # Protect default demo case
    shutil.rmtree(case_path)
    return True
