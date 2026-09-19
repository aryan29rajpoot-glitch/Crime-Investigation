import re


def extract_entities(text):

    # Indian phone numbers
    phones = re.findall(
        r'\+91[\s-]?\d{10}',
        text
    )

    # UPI IDs
    upi_ids = re.findall(
        r'\b[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\b',
        text
    )

    # Bank accounts
    bank_accounts = re.findall(
        r'\bAC\d+\b',
        text
    )

    # IP addresses
    ip_addresses = re.findall(
        r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
        text
    )

    # Remove duplicates
    phones = list(set(phones))
    upi_ids = list(set(upi_ids))
    bank_accounts = list(set(bank_accounts))
    ip_addresses = list(set(ip_addresses))

    return {
        "phones": phones,
        "upi_ids": upi_ids,
        "bank_accounts": bank_accounts,
        "ip_addresses": ip_addresses
    }