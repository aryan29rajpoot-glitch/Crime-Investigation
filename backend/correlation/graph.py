import networkx as nx


def build_graph(cdr_data, bank_data, chat_data):

    graph = nx.Graph()

    # =========================================
    # 1. CALL RECORDS
    # =========================================

    for record in cdr_data:

        caller = record["caller"]
        receiver = record["receiver"]

        graph.add_node(
            caller,
            type="phone"
        )

        graph.add_node(
            receiver,
            type="phone"
        )

        graph.add_edge(
            caller,
            receiver,
            relationship="CALL",
            timestamp=record["timestamp"]
        )

    # =========================================
    # 2. BANK TRANSACTIONS
    # =========================================

    for record in bank_data:

        account = record["account"]
        upi = record["upi"]

        graph.add_node(
            account,
            type="bank_account"
        )

        graph.add_node(
            upi,
            type="upi"
        )

        graph.add_edge(
            account,
            upi,
            relationship=record["type"],
            amount=record["amount"],
            timestamp=record["timestamp"]
        )

    # =========================================
    # 3. CHAT ENTITIES
    # =========================================

    for phone in chat_data["phones"]:

        graph.add_node(
            phone,
            type="phone"
        )

    for upi in chat_data["upi_ids"]:

        graph.add_node(
            upi,
            type="upi"
        )

    # =========================================
    # 4. CHAT RELATIONSHIPS
    # =========================================

    for link in chat_data["chat_links"]:

        phone = link["phone"]
        upi = link["upi"]

        graph.add_edge(
            phone,
            upi,
            relationship="CHAT_LINK"
        )

    return graph