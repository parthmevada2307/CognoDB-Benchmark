from neo4j import GraphDatabase
from dotenv import load_dotenv
import os
load_dotenv()
uri = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(uri, auth=(username, password))
def load_data(path):
    batch = []
    batch_size = 2000
    total = 0

    with driver.session() as session:

        with open(path, "r") as file:

            for line in file:

                if line.startswith("#"):
                    continue
                line = line.strip()

                if not line:
                    continue

                source, target = line.split()
                batch.append({
                    "source": int(source),
                    "target": int(target)
                })
                if len(batch) == batch_size:
                    session.run("""
                            UNWIND $rows AS row
                            MERGE (a:User {id: row.source})
                            MERGE (b:User {id: row.target})
                            MERGE (a)-[:VOTED_FOR]->(b)
                        """, rows=batch).consume()

                    total += len(batch)

                    print(f"{total} relationships processed...")
                    batch = []
        if batch:
            session.run("""
                    UNWIND $rows AS row
                    MERGE (a:User {id: row.source})
                    MERGE (b:User {id: row.target})
                    MERGE (a)-[:VOTED_FOR]->(b)
                """, rows=batch).consume()
            total += len(batch)
            print(f"{total} relationships processed...")
    print("\nFinished loading dataset.")
load_data("datasets/Wiki-Vote.txt")
driver.close()