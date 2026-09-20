import io
import pandas as pd


def parse_bank(file_or_content):
    """
    Parses banking / UPI transaction statements from CSV file path, string, or bytes buffer.
    Supports flexible column naming and normalizes into directed transactions:
    DEBIT (Account -> UPI), CREDIT (UPI -> Account), TRANSFER (Account -> Account / UPI).
    """
    if isinstance(file_or_content, (bytes, bytearray)):
        file_obj = io.BytesIO(file_or_content)
    elif isinstance(file_or_content, str) and ("\n" in file_or_content or "," in file_or_content):
        file_obj = io.StringIO(file_or_content)
    else:
        file_obj = file_or_content

    df = pd.read_csv(file_obj, dtype=str)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Flexible column mapping
    acc_col = next((c for c in df.columns if c in ["account", "account_no", "acc_no", "account_number", "source_account", "bank_account", "acc"]), None)
    upi_col = next((c for c in df.columns if c in ["upi", "upi_id", "vpa", "beneficiary_upi", "receiver_upi", "handle"]), None)
    amt_col = next((c for c in df.columns if c in ["amount", "txn_amount", "transaction_amount", "amt", "value"]), None)
    type_col = next((c for c in df.columns if c in ["type", "txn_type", "transaction_type", "dr_cr", "credit_debit", "direction"]), None)
    ts_col = next((c for c in df.columns if c in ["timestamp", "date", "datetime", "txn_date", "time", "date_time"]), None)

    records = []
    for _, row in df.iterrows():
        account = str(row.get(acc_col)).strip() if acc_col and pd.notna(row.get(acc_col)) else None
        upi = str(row.get(upi_col)).strip() if upi_col and pd.notna(row.get(upi_col)) else None

        if not account and not upi:
            continue

        raw_amt = row.get(amt_col) if amt_col else None
        try:
            amt_val = float(str(raw_amt).replace(",", "").strip()) if pd.notna(raw_amt) and raw_amt is not None else None
            if amt_val and amt_val.is_integer():
                amt_val = int(amt_val)
        except (ValueError, TypeError):
            amt_val = None

        txn_type = str(row.get(type_col)).strip().upper() if type_col and pd.notna(row.get(type_col)) else "TRANSFER"
        raw_ts = row.get(ts_col) if ts_col else None
        ts = str(raw_ts).strip() if pd.notna(raw_ts) and raw_ts is not None else None

        # Determine directed flow: source -> target
        if txn_type in ["DEBIT", "DR", "OUT"]:
            source = account or "UNKNOWN_ACC"
            target = upi or "UNKNOWN_UPI"
            rel = "DEBIT"
        elif txn_type in ["CREDIT", "CR", "IN"]:
            source = upi or "UNKNOWN_UPI"
            target = account or "UNKNOWN_ACC"
            rel = "CREDIT"
        elif txn_type == "TRANSFER":
            source = account or upi
            target = upi if account and upi else "BENEFICIARY"
            rel = "TRANSFER"
        else:
            source = account or upi
            target = upi if account else "BENEFICIARY"
            rel = txn_type

        records.append({
            "source": source,
            "target": target,
            "account": account,
            "upi": upi,
            "relationship": rel,
            "type": txn_type,
            "amount": amt_val,
            "timestamp": ts
        })

    return records