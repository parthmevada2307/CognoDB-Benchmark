import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

db_type = os.getenv("DB_TYPE", "arangodb").lower()

if db_type in ["neo4j", "memgraph", "cognodb"]:
    from neo4j import GraphDatabase

    if db_type == "memgraph":
        uri = os.getenv("MEMGRAPH_URI")
        username = os.getenv("MEMGRAPH_USER")
        password = os.getenv("MEMGRAPH_PASSWORD")
    elif db_type == "neo4j":
        uri = os.getenv("NEO4J_URI")
        username = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME")
        password = os.getenv("NEO4J_PASSWORD")
    elif db_type == "cognodb":
        uri = os.getenv("COGNODB_URI")
        username = os.getenv("COGNODB_USER")
        password = os.getenv("COGNODB_PASSWORD")

elif db_type == "arangodb":
    from arango import ArangoClient


def setup_constraints_and_schema(client_or_driver):
    if db_type in ["neo4j", "cognodb"]:
        query = "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE"
        with client_or_driver.session() as session:
            session.run(query)

    elif db_type == "arangodb":
        # Connect to system database to create wiki_vote_db if not exists
        sys_db = client_or_driver.db("_system", username=arango_user, password=arango_password)
        if not sys_db.has_database("wiki_vote_db"):
            sys_db.create_database("wiki_vote_db")

        # Connect to working DB
        db = client_or_driver.db("wiki_vote_db", username=arango_user, password=arango_password)

        # Create collections if they don't exist
        if not db.has_collection("User"):
            db.create_collection("User")
        if not db.has_collection("VOTED_FOR"):
            db.create_collection("VOTED_FOR", edge=True)

        return db


def insert_nodes_batch(handler, batch_ids):
    if db_type in ["neo4j", "memgraph", "cognodb"]:
        query = "UNWIND $ids AS userId MERGE (u:User {id: userId})"
        handler.run(query, ids=batch_ids)

    elif db_type == "arangodb":
        # Create documents with '_key' set to user ID
        documents = [{"_key": str(uid), "id": uid} for uid in batch_ids]
        user_col = handler.collection("User")
        user_col.import_bulk(documents, on_duplicate="ignore")


def insert_rels_batch(handler, batch_rels):
    if db_type in ["neo4j", "memgraph", "cognodb"]:
        query = """
        UNWIND $rows AS row
        MATCH (a:User {id: row.source})
        MATCH (b:User {id: row.target})
        MERGE (a)-[:VOTED_FOR]->(b)
        """
        handler.run(query, rows=batch_rels)

    elif db_type == "arangodb":
        # Create edges connecting User nodes
        edges = [
            {"_from": f"User/{row['source']}", "_to": f"User/{row['target']}"}
            for row in batch_rels
        ]
        edge_col = handler.collection("VOTED_FOR")
        edge_col.import_bulk(edges, on_duplicate="ignore")


def load_data(handler, path, batch_size=5000):
    unique_nodes = set()
    relationships = []

    print("Reading dataset into memory...")
    with open(path, "r") as file:
        for line in file:
            if line.startswith("#") or not line.strip():
                continue

            source, target = line.strip().split()
            s_id, t_id = int(source), int(target)

            unique_nodes.add(s_id)
            unique_nodes.add(t_id)
            relationships.append({"source": s_id, "target": t_id})

    print(f"Dataset read: {len(unique_nodes)} unique nodes, {len(relationships)} relationships.")

    # Pass 1: Nodes
    print(f"\n[Pass 1/2] Loading User nodes into [{db_type.upper()}]...")
    node_list = list(unique_nodes)
    for i in range(0, len(node_list), batch_size):
        chunk = node_list[i : i + batch_size]
        if db_type in ["neo4j", "memgraph", "cognodb"]:
            with handler.session() as session:
                insert_nodes_batch(session, chunk)
        else:
            insert_nodes_batch(handler, chunk)
        print(f"  Processed {min(i + batch_size, len(node_list))}/{len(node_list)} nodes...")

    # Pass 2: Relationships
    print(f"\n[Pass 2/2] Loading VOTED_FOR relationships into [{db_type.upper()}]...")
    for i in range(0, len(relationships), batch_size):
        chunk = relationships[i : i + batch_size]
        if db_type in ["neo4j", "memgraph", "cognodb"]:
            with handler.session() as session:
                insert_rels_batch(session, chunk)
        else:
            insert_rels_batch(handler, chunk)
        print(f"  Processed {min(i + batch_size, len(relationships))}/{len(relationships)} relationships...")

    print(f"\nFinished loading dataset into [{db_type.upper()}]. Total relationships: {len(relationships)}")


if __name__ == "__main__":
    dataset_path = "datasets/Wiki-Vote.txt"

    if db_type in ["neo4j", "memgraph", "cognodb"]:
        auth = (username, password) if username and password else None
        with GraphDatabase.driver(uri, auth=auth) as driver:
            setup_constraints_and_schema(driver)
            load_data(driver, dataset_path, batch_size=5000)

    elif db_type == "arangodb":
        arango_url = os.getenv("ARANGO_URL", "http://localhost:8529")
        arango_user = os.getenv("ARANGO_USER", "root")
        arango_password = os.getenv("ARANGO_PASSWORD", "your_password")

        client = ArangoClient(hosts=arango_url)
        db_handler = setup_constraints_and_schema(client)
        load_data(db_handler, dataset_path, batch_size=5000)