from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

load_dotenv()

uri = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(uri, auth=(username, password))

with driver.session() as session:

    nodes = session.run(
        "MATCH (n:User) RETURN count(n) AS total"
    ).single()["total"]

    relationships = session.run(
        "MATCH ()-[r:VOTED_FOR]->() RETURN count(r) AS total"
    ).single()["total"]

    print("Nodes:", nodes)
    print("Relationships:", relationships)

    if nodes > 0 and relationships > 0:
        print("✅ Verification Passed")
    else:
        print("❌ Verification Failed")

driver.close()