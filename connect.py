from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

load_dotenv()
uri = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(uri, auth=(username, password))

def connection():
    with driver.session() as session:
        res = session.run("RETURN 'Hello, I connected to CongoDB!' AS message")
        print(res.single()["message"])

connection()
driver.close()