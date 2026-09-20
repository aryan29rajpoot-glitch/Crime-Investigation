import re


def normalize_phone_number(phone):
    if not phone:
        return None
    phone = str(phone).strip()
    digits = re.sub(r"[^\d+]", "", phone)
    if digits.startswith("91") and len(digits) == 12:
        return "+" + digits
    if len(digits) == 10:
        return "+91" + digits
    if not digits.startswith("+") and len(digits) > 10:
        return "+" + digits
    return digits


def parse_chat(file_or_content):
    """
    Parses chat transcripts in standard or WhatsApp-style formats.
    Supports file path or direct string content.
    Extracts sender phone, timestamp, mentioned UPIs, bank accounts, and amounts.
    """
    if "\n" in file_or_content or len(file_or_content) > 300:
        # Passed as raw text
        text = file_or_content
    else:
        try:
            with open(file_or_content, "r", encoding="utf-8") as file:
                text = file.read()
        except Exception:
            text = file_or_content

    phones = set()
    upi_ids = set()
    bank_accounts = set()
    chat_links = []
    messages = []

    # Regex patterns for entities
    phone_pattern = r'(\+?91[\s-]?\d{10}|\b\d{10}\b)'
    upi_pattern = r'\b[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\b'
    account_pattern = r'\bAC\d+\b'
    amount_pattern = r'(?:(?:INR|Rs\.?|₹)\s*(\d+(?:,\d+)*(?:\.\d+)?)|(?:send|transfer|amount|pay)?\s*(\d{3,9})\b)'

    # Split by double newline or header lines
    # Detect standard blocks like: "2026-09-10 10:15 +919876543210:\nMessage text"
    # or "10/09/26, 10:15 - +919876543210: Message text"
    header_regex = re.compile(
        r'(?:^|\n)(?:\[?(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?|\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\]?\s*(?:-\s*)?)?(\+?91[\s-]?\d{10}|\+?\d{10,12})[:\s]+',
        re.MULTILINE | re.IGNORECASE
    )

    matches = list(header_regex.finditer(text))

    if matches:
        for idx, match in enumerate(matches):
            raw_time = match.group(1)
            raw_sender = match.group(2)
            start_pos = match.end()
            end_pos = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            body = text[start_pos:end_pos].strip()

            sender_phone = normalize_phone_number(raw_sender)
            if sender_phone:
                phones.add(sender_phone)

            # Find entities in message body
            found_upis = re.findall(upi_pattern, body)
            found_accounts = re.findall(account_pattern, body)
            
            # Find amounts
            found_amounts = []
            for amt_m in re.finditer(r'(?:INR|Rs\.?|₹)?\s*(\d{3,8})\b', body, re.IGNORECASE):
                try:
                    amt_val = float(amt_m.group(1))
                    if amt_val >= 100:
                        found_amounts.append(amt_val)
                except ValueError:
                    pass

            primary_amount = found_amounts[0] if found_amounts else None

            for upi in found_upis:
                upi_clean = upi.strip().lower()
                upi_ids.add(upi_clean)
                if sender_phone:
                    chat_links.append({
                        "phone": sender_phone,
                        "upi": upi_clean,
                        "timestamp": raw_time.strip() if raw_time else None,
                        "amount": primary_amount,
                        "snippet": body[:120],
                        "relationship": "CHAT_LINK"
                    })

            for acc in found_accounts:
                bank_accounts.add(acc.strip())
                if sender_phone:
                    chat_links.append({
                        "phone": sender_phone,
                        "account": acc.strip(),
                        "timestamp": raw_time.strip() if raw_time else None,
                        "amount": primary_amount,
                        "snippet": body[:120],
                        "relationship": "CHAT_LINK"
                    })

            messages.append({
                "sender": sender_phone or raw_sender,
                "timestamp": raw_time.strip() if raw_time else None,
                "body": body,
                "upis": found_upis,
                "accounts": found_accounts
            })
    else:
        # Fallback for plain blocks without standard headers
        raw_phones = re.findall(r'\+91\d{10}', text)
        for p in raw_phones:
            norm = normalize_phone_number(p)
            if norm:
                phones.add(norm)
        for u in re.findall(upi_pattern, text):
            upi_ids.add(u.strip().lower())

    return {
        "phones": sorted(list(phones)),
        "upi_ids": sorted(list(upi_ids)),
        "bank_accounts": sorted(list(bank_accounts)),
        "chat_links": chat_links,
        "messages": messages,
        "raw_text": text
    }