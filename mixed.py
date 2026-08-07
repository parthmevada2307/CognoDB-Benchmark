from neo4j import GraphDatabase
from dotenv import load_dotenv
import os
import time
import statistics
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()
URI = os.getenv("NEO4J_URI")
USERNAME = os.getenv("NEO4J_USER")
PASSWORD = os.getenv("NEO4J_PASSWORD")
driver = GraphDatabase.driver(
    URI,
    auth=(USERNAME, PASSWORD)
)

READ_QUERY = """
MATCH (u:User {id: $user_id})-[:VOTED_FOR]->(v)
RETURN count(v) AS total
"""

WRITE_QUERY = """
MERGE (a:BenchmarkUser {id: $source})
MERGE (b:BenchmarkUser {id: $target})
MERGE (a)-[:BENCHMARK_VOTED]->(b)
"""


def get():
    with driver.session() as session:

        result = session.run("""
            MATCH (u:User)
            RETURN u.id AS id
            LIMIT 100
        """)

        return [record["id"] for record in result]


def read(user_id):
    start = time.perf_counter()
    with driver.session() as session:
        session.run(
            READ_QUERY,
            user_id=user_id
        ).consume()

    end = time.perf_counter()

    return (end - start) * 1000

def write(number):
    source = 900000 + number
    target = 910000 + number
    start = time.perf_counter()
    with driver.session() as session:
        session.run(
            WRITE_QUERY,
            source=source,
            target=target
        ).consume()

    end = time.perf_counter()

    return (end - start) * 1000


def main():

    users = get()

    print(f"Using {len(users)} users")

    # Warm-up
    for user_id in users[:10]:
        read(user_id)

    print("starting mixed workload...\n")
    results = []
    total_operations = 100
    workers = 10

    with ThreadPoolExecutor(max_workers=workers) as executor:

        futures = []
        for i in range(total_operations):
            if i % 2 == 0:

                user_id = random.choice(users)

                futures.append(
                    executor.submit(
                        read,
                        user_id
                    )
                )
            else:
                futures.append(
                    executor.submit(
                        write,
                        i
                    )
                )
        for future in as_completed(futures):

            try:
                results.append(future.result())
            except Exception as error:
                print("Operation is failed:", error)

    results.sort()
    p50 = statistics.median(results)
    p95 = results[int(len(results) * 0.95) - 1]

    print("Mixed workload results")
    print("----------------------")
    print(f"Operations completed: {len(results)}")
    print(f"p50 latency: {p50:.2f} ms")
    print(f"p95 latency: {p95:.2f} ms")
    print(f"Workers: {workers}")
main()
driver.close()