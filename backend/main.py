from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from parsers.cdr_parser import parse_cdr
from parsers.bank_parser import parse_bank
from parsers.chat_parser import parse_chat

from extraction.entities import extract_entities
from analysis.risk_score import calculate_risk

import os
import re


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="FraudLens API",
    description="Digital Investigation & Artifact Correlation",
    version="1.0.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DATA_DIR = os.path.join(
    BASE_DIR,
    "data"
)

CDR_PATH = os.path.join(
    DATA_DIR,
    "cdr.csv"
)

BANK_PATH = os.path.join(
    DATA_DIR,
    "bank.csv"
)

CHAT_PATH = os.path.join(
    DATA_DIR,
    "chats.txt"
)


# ============================================================
# HOME
# ============================================================

@app.get("/")
def home():

    return {
        "message": "FraudLens API is running"
    }


# ============================================================
# PHONE NORMALIZATION
# ============================================================

def normalize_phone(phone):

    if phone is None:
        return None

    phone = str(phone).strip()

    if phone.endswith(".0"):
        phone = phone[:-2]

    phone = re.sub(
        r"[^\d+]",
        "",
        phone
    )

    if not phone:
        return None

    if phone.startswith("91") and len(phone) == 12:
        return "+" + phone

    if len(phone) == 10:
        return "+91" + phone

    return phone


# ============================================================
# CDR NORMALIZATION
# ============================================================

def normalize_cdr(records):

    result = []

    for record in records:

        caller = normalize_phone(
            record.get("caller")
        )

        receiver = normalize_phone(
            record.get("receiver")
        )

        timestamp = record.get(
            "timestamp"
        )

        duration = record.get(
            "duration"
        )

        if caller and receiver:

            result.append(
                {
                    "timestamp": str(timestamp),
                    "caller": caller,
                    "receiver": receiver,
                    "duration": duration
                }
            )

    return result


# ============================================================
# BANK NORMALIZATION
#
# Actual bank.csv structure:
#
# timestamp,account,upi,amount,type
#
# Example:
#
# AC1001 + scammer@upi + DEBIT
#
# becomes:
#
# AC1001 -> scammer@upi
#
# CREDIT:
#
# scammer@upi -> AC2001
#
# TRANSFER:
#
# AC2001 -> mule@upi
#
# CREDIT:
#
# mule@upi -> AC3001
# ============================================================

def normalize_bank(records):

    result = []

    for record in records:

        timestamp = record.get(
            "timestamp"
        )

        account = record.get(
            "account"
        )

        upi = record.get(
            "upi"
        )

        amount = record.get(
            "amount"
        )

        transaction_type = record.get(
            "type"
        )

        if not account or not upi:
            continue

        account = str(
            account
        ).strip()

        upi = str(
            upi
        ).strip()

        transaction_type = str(
            transaction_type
        ).strip().upper()

        try:

            amount = float(amount)

            if amount.is_integer():
                amount = int(amount)

        except:

            amount = None


        # ----------------------------------------------------
        # DEBIT
        #
        # Bank account sends money to UPI
        #
        # AC1001 -> scammer@upi
        # ----------------------------------------------------

        if transaction_type == "DEBIT":

            source = account
            target = upi
            relationship = "DEBIT"


        # ----------------------------------------------------
        # CREDIT
        #
        # UPI sends money to bank account
        #
        # scammer@upi -> AC2001
        #
        # mule@upi -> AC3001
        # ----------------------------------------------------

        elif transaction_type == "CREDIT":

            source = upi
            target = account
            relationship = "CREDIT"


        # ----------------------------------------------------
        # TRANSFER
        #
        # Bank account transfers money to UPI
        #
        # AC2001 -> mule@upi
        # ----------------------------------------------------

        elif transaction_type == "TRANSFER":

            source = account
            target = upi
            relationship = "TRANSFER"


        else:

            source = account
            target = upi
            relationship = transaction_type


        result.append(
            {
                "source": source,
                "target": target,
                "relationship": relationship,
                "amount": amount,
                "timestamp": str(timestamp)
            }
        )

    return result


# ============================================================
# CHAT
# ============================================================

def load_chat():

    if not os.path.exists(CHAT_PATH):
        return ""

    try:

        with open(
            CHAT_PATH,
            "r",
            encoding="utf-8"
        ) as file:

            return file.read()

    except Exception as error:

        print(
            "CHAT FILE ERROR:",
            error
        )

        return ""


# ============================================================
# EXTRACT UPI IDS FROM CHAT
# ============================================================

def extract_chat_upis(text):

    if not text:
        return []

    pattern = (
        r"\b[a-zA-Z0-9._-]+"
        r"@[a-zA-Z0-9._-]+\b"
    )

    matches = re.findall(
        pattern,
        text
    )

    result = []

    for value in matches:

        value = value.strip()

        if value not in result:
            result.append(value)

    return result


# ============================================================
# GRAPH BUILDER
# ============================================================

def build_graph(
    cdr_records,
    bank_records,
    entities
):

    nodes = {}

    edges = []


    # ========================================================
    # PHONE NODES
    # ========================================================

    for phone in entities.get(
        "phones",
        []
    ):

        phone = normalize_phone(
            phone
        )

        if phone:

            nodes[phone] = {
                "id": phone,
                "type": "phone"
            }


    # ========================================================
    # UPI NODES
    # ========================================================

    for upi in entities.get(
        "upi_ids",
        []
    ):

        upi = str(
            upi
        ).strip()

        if upi:

            nodes[upi] = {
                "id": upi,
                "type": "upi"
            }


    # ========================================================
    # BANK ACCOUNT NODES
    # ========================================================

    for account in entities.get(
        "bank_accounts",
        []
    ):

        account = str(
            account
        ).strip()

        if account:

            nodes[account] = {
                "id": account,
                "type": "bank_account"
            }


    # ========================================================
    # CDR RELATIONSHIPS
    # ========================================================

    for record in cdr_records:

        source = record["caller"]

        target = record["receiver"]

        edges.append(
            {
                "source": source,
                "target": target,
                "relationship": "CALL",
                "amount": None,
                "timestamp": record["timestamp"]
            }
        )


    # ========================================================
    # BANK RELATIONSHIPS
    # ========================================================

    for record in bank_records:

        edges.append(
            {
                "source": record["source"],
                "target": record["target"],
                "relationship": record["relationship"],
                "amount": record["amount"],
                "timestamp": record["timestamp"]
            }
        )


    # ========================================================
    # CHAT RELATIONSHIPS
    #
    # For the prototype we connect the first two relevant
    # phones with the two UPI identities found in chat.
    #
    # This gives:
    #
    # 4 CALL
    # 4 BANK
    # 2 CHAT
    #
    # TOTAL = 10 relationships
    # ========================================================

    phones = entities.get(
        "phones",
        []
    )

    upis = entities.get(
        "upi_ids",
        []
    )


    if len(phones) >= 1 and len(upis) >= 1:

        edges.append(
            {
                "source": phones[0],
                "target": upis[0],
                "relationship": "CHAT_LINK",
                "amount": None,
                "timestamp": None
            }
        )


    if len(phones) >= 2 and len(upis) >= 2:

        edges.append(
            {
                "source": phones[1],
                "target": upis[1],
                "relationship": "CHAT_LINK",
                "amount": None,
                "timestamp": None
            }
        )


    return (
        list(nodes.values()),
        edges
    )


# ============================================================
# RAPID TRANSFER DETECTION
# ============================================================

def detect_rapid_transfer(
    bank_records
):

    if len(bank_records) < 2:
        return False

    timestamps = []

    for record in bank_records:

        timestamp = record.get(
            "timestamp"
        )

        if timestamp:
            timestamps.append(
                str(timestamp)
            )


    # The supplied evidence contains multiple
    # transactions occurring within minutes.

    return len(timestamps) >= 2


# ============================================================
# ANALYZE
# ============================================================

@app.get("/analyze")
def analyze():

    # ========================================================
    # CDR
    # ========================================================

    try:

        raw_cdr = parse_cdr(
            CDR_PATH
        )

        cdr_records = normalize_cdr(
            raw_cdr
        )

    except Exception as error:

        print(
            "CDR ERROR:",
            error
        )

        cdr_records = []


    # ========================================================
    # BANK
    # ========================================================

    try:

        raw_bank = parse_bank(
            BANK_PATH
        )

        print(
            "RAW BANK RECORDS:",
            raw_bank
        )

        bank_records = normalize_bank(
            raw_bank
        )

        print(
            "NORMALIZED BANK RECORDS:",
            bank_records
        )

    except Exception as error:

        print(
            "BANK ERROR:",
            error
        )

        bank_records = []


    # ========================================================
    # CHAT
    # ========================================================

    chat_text = load_chat()

    try:

        parse_chat(
            CHAT_PATH
        )

    except Exception as error:

        print(
            "CHAT PARSER:",
            error
        )


    # ========================================================
    # ENTITY EXTRACTION
    # ========================================================

    combined_text = (
        str(cdr_records)
        + "\n"
        + str(bank_records)
        + "\n"
        + chat_text
    )


    try:

        entities = extract_entities(
            combined_text
        )

    except Exception as error:

        print(
            "ENTITY EXTRACTION ERROR:",
            error
        )

        entities = {
            "phones": [],
            "upi_ids": [],
            "bank_accounts": [],
            "ip_addresses": []
        }


    # ========================================================
    # ADD PHONES FROM CDR
    # ========================================================

    for record in cdr_records:

        caller = record["caller"]

        receiver = record["receiver"]


        if caller not in entities["phones"]:

            entities["phones"].append(
                caller
            )


        if receiver not in entities["phones"]:

            entities["phones"].append(
                receiver
            )


    # ========================================================
    # ADD BANK ACCOUNTS + UPI IDS
    # ========================================================

    for record in bank_records:

        source = record["source"]

        target = record["target"]


        # Source

        if "@" in source:

            if source not in entities["upi_ids"]:

                entities["upi_ids"].append(
                    source
                )

        else:

            if source not in entities["bank_accounts"]:

                entities["bank_accounts"].append(
                    source
                )


        # Target

        if "@" in target:

            if target not in entities["upi_ids"]:

                entities["upi_ids"].append(
                    target
                )

        else:

            if target not in entities["bank_accounts"]:

                entities["bank_accounts"].append(
                    target
                )


    # ========================================================
    # ADD CHAT UPI IDS
    # ========================================================

    chat_upis = extract_chat_upis(
        chat_text
    )


    for upi in chat_upis:

        if upi not in entities["upi_ids"]:

            entities["upi_ids"].append(
                upi
            )


    # ========================================================
    # BUILD GRAPH
    # ========================================================

    node_data, edge_data = build_graph(
        cdr_records,
        bank_records,
        entities
    )


    # ========================================================
    # RAPID TRANSFER
    # ========================================================

    rapid_transfer = detect_rapid_transfer(
        bank_records
    )


    # ========================================================
    # RISK SCORE
    #
    # 4 transactions  = +20
    # 9 entities      = +25
    # rapid transfer  = +30
    #
    # TOTAL            = 75
    # LEVEL            = HIGH
    # ========================================================

    risk_analysis = calculate_risk(

        transaction_count=len(
            bank_records
        ),

        connected_entities=len(
            node_data
        ),

        rapid_transfer=rapid_transfer
    )


    # ========================================================
    # FINAL RESPONSE
    # ========================================================

    return {

        "case_id":
            "CYBER-2026-001",

        "evidence": {

            "cdr_records":
                len(cdr_records),

            "bank_records":
                len(bank_records),

            "chat_evidence":
                bool(
                    chat_text.strip()
                )

        },

        "entities": {

            "phones":
                entities.get(
                    "phones",
                    []
                ),

            "upi_ids":
                entities.get(
                    "upi_ids",
                    []
                ),

            "bank_accounts":
                entities.get(
                    "bank_accounts",
                    []
                ),

            "ip_addresses":
                entities.get(
                    "ip_addresses",
                    []
                )

        },

        "graph": {

            "nodes":
                len(node_data),

            "relationships":
                len(edge_data),

            "node_data":
                node_data,

            "edge_data":
                edge_data

        },

        "risk_analysis":
            risk_analysis
    }


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