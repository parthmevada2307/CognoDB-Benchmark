from neo4j import GraphDatabase
from dotenv import load_dotenv
import os
import time

load_dotenv()

URI = os.getenv("NEO4J_URI")
USERNAME = os.getenv("NEO4J_USER")
PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(
    URI,
    auth=(USERNAME, PASSWORD)
)

file_path = "datasets/Wiki-Vote.txt"


def load_data():

    records = []
    with open(file_path, "r") as file:
        for line in file:

            if line.startswith("#"):
                continue
            line = line.strip()

            if not line:
                continue

            source, target = line.split()

            records.append({
                "source": int(source),
                "target": int(target)
            })

    print(f"Records ready: {len(records)}")
    start = time.perf_counter()

    with driver.session() as session:

        session.run("""
            UNWIND $records AS row

            MERGE (a:BenchmarkUser {id: row.source})
            MERGE (b:BenchmarkUser {id: row.target})
            MERGE (a)-[:BENCHMARK_VOTED]->(b)
        """, records=records).consume()

    end = time.perf_counter()

    elapsed = end - start

    records_per_second = len(records) / elapsed

    print()
    print("Ingest benchmark")
    print("-----------------")
    print(f"Records loaded: {len(records)}")
    print(f"Time: {elapsed:.2f} seconds")
    print(f"Throughput: {records_per_second:.2f} records/second")
load_data()

driver.close()