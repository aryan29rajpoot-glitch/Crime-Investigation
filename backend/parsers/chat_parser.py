import re


def parse_chat(file_path):

    with open(file_path, "r", encoding="utf-8") as file:
        text = file.read()

    phones = re.findall(
        r'\+91\d{10}',
        text
    )

    upi_ids = re.findall(
        r'\b[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\b',
        text
    )

    # -----------------------------------------
    # Extract phone → UPI relationships
    # from individual chat messages
    # -----------------------------------------

    chat_links = []

    # Split the chat into message blocks.
    # A new message starts with a date/time followed
    # by a phone number.
    messages = re.split(
        r'\n\s*\n',
        text.strip()
    )

    for message in messages:

        message_phones = re.findall(
            r'\+91\d{10}',
            message
        )

        message_upis = re.findall(
            r'\b[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\b',
            message
        )

        for phone in message_phones:

            for upi in message_upis:

                chat_links.append({

                    "phone": phone,

                    "upi": upi,

                    "relationship": "CHAT_LINK"

                })

    return {

        "phones": list(set(phones)),

        "upi_ids": list(set(upi_ids)),

        "chat_links": chat_links,

        "raw_text": text

    }