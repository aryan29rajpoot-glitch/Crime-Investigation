import io
import re
import pandas as pd


def normalize_phone_val(val):
    if pd.isna(val) or val is None:
        return None
    val_str = str(val).strip()
    if val_str.endswith(".0"):
        val_str = val_str[:-2]
    digits = re.sub(r"[^\d+]", "", val_str)
    if not digits:
        return None
    if digits.startswith("91") and len(digits) == 12:
        return "+" + digits
    if len(digits) == 10:
        return "+91" + digits
    if not digits.startswith("+") and len(digits) > 10:
        return "+" + digits
    return digits


def parse_cdr(file_or_content):
    """
    Parses Call Detail Records from CSV file path, string, or bytes buffer.
    Supports flexible column naming.
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
    caller_col = next((c for c in df.columns if c in ["caller", "calling_number", "calling_no", "from", "source", "src", "anum"]), None)
    receiver_col = next((c for c in df.columns if c in ["receiver", "dialled_number", "called_number", "to", "target", "dest", "bnum"]), None)
    timestamp_col = next((c for c in df.columns if c in ["timestamp", "datetime", "call_time", "date_time", "start_time", "time"]), None)
    duration_col = next((c for c in df.columns if c in ["duration", "call_duration", "sec", "seconds"]), None)

    if not caller_col or not receiver_col:
        # Fallback to first two columns
        cols = list(df.columns)
        if len(cols) >= 2:
            caller_col = cols[0]
            receiver_col = cols[1]
        else:
            return []

    records = []
    for _, row in df.iterrows():
        caller = normalize_phone_val(row.get(caller_col))
        receiver = normalize_phone_val(row.get(receiver_col))
        if not caller or not receiver:
            continue

        raw_ts = row.get(timestamp_col) if timestamp_col else None
        ts = str(raw_ts).strip() if pd.notna(raw_ts) and raw_ts is not None else None

        raw_dur = row.get(duration_col) if duration_col else None
        try:
            dur = int(float(raw_dur)) if pd.notna(raw_dur) and raw_dur is not None else None
        except (ValueError, TypeError):
            dur = None

        records.append({
            "caller": caller,
            "receiver": receiver,
            "timestamp": ts,
            "duration": dur
        })

    return records