import re


def extract_entities(text):
    if not text:
        return {
            "phones": [],
            "upi_ids": [],
            "bank_accounts": [],
            "ip_addresses": []
        }

    # Indian phone numbers (+91 or 10 digits)
    raw_phones = re.findall(
        r'(?:\+91[\s-]?)?\b[6-9]\d{9}\b',
        text
    )
    phones = set()
    for p in raw_phones:
        digits = re.sub(r"[^\d]", "", p)
        if len(digits) == 10:
            phones.add("+91" + digits)
        elif len(digits) == 12 and digits.startswith("91"):
            phones.add("+" + digits)

    # UPI IDs
    upi_ids = set(
        u.strip().lower() for u in re.findall(
            r'\b[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\b',
            text
        )
    )

    # Bank accounts (e.g. AC1001, ACC1234, or AC/ACC prefixes)
    bank_accounts = set(
        re.findall(
            r'\b(?:AC|ACC)\d+\b',
            text,
            re.IGNORECASE
        )
    )

    # IP addresses (valid IPv4 octets 0-255)
    raw_ips = re.findall(
        r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
        text
    )
    ip_addresses = set()
    for ip in raw_ips:
        parts = ip.split(".")
        if all(0 <= int(p) <= 255 for p in parts):
            ip_addresses.add(ip)

    return {
        "phones": sorted(list(phones)),
        "upi_ids": sorted(list(upi_ids)),
        "bank_accounts": sorted(list(bank_accounts)),
        "ip_addresses": sorted(list(ip_addresses))
    }