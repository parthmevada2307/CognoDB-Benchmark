from neo4j import GraphDatabase
from dotenv import load_dotenv
import os
import time
import statistics
import random

load_dotenv()

URI = os.getenv("NEO4J_URI")
USERNAME = os.getenv("NEO4J_USER")
PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(
    URI,
    auth=(USERNAME, PASSWORD)
)

def get_start_nodes(session):
    result = session.run("""
        MATCH (u:User)
        RETURN u.id AS id
        LIMIT 100
    """)

    return [record["id"] for record in result]
def measure(session, query, nodes=None, runs=100):
    if nodes:
        for user_id in nodes[:10]:
            session.run(query, user_id=user_id).consume()
    else:
        for _ in range(10):
            session.run(query).consume()

    times = []

    for _ in range(runs):
        if nodes:
            user_id = random.choice(nodes)
            start = time.perf_counter()
            session.run(
                query,
                user_id=user_id
            ).consume()
        else:
            start = time.perf_counter()
            session.run(query).consume()
        end = time.perf_counter()

        times.append((end - start) * 1000)

    times.sort()
    p50 = statistics.median(times)
    p95 = times[int(len(times) * 0.95) - 1]

    return p50, p95
queries = {
    "1-hop": """
        MATCH (u:User {id: $user_id})
              -[:VOTED_FOR]->(v)
        RETURN v
    """,
    "2-hop": """
        MATCH (u:User {id: $user_id})
              -[:VOTED_FOR]->()
              -[:VOTED_FOR]->(v)
        RETURN v
    """,
    "3-hop": """
        MATCH (u:User {id: $user_id})
              -[:VOTED_FOR]->()
              -[:VOTED_FOR]->()
              -[:VOTED_FOR]->(v)
        RETURN v
    """,
    "Point lookup": """
        MATCH (u:User {id: $user_id})
        RETURN u
    """,
    "Indexed lookup": """
        MATCH (u:User)
        WHERE u.id = $user_id
        RETURN u
    """
}
with driver.session() as session:
    nodes = get_start_nodes(session)

    print(f"Using {len(nodes)} start nodes\n")

    for name, query in queries.items():
        p50, p95 = measure(
            session,
            query,
            nodes
        )
        print(name)
        print(f"p50: {p50:.2f} ms")
        print(f"p95: {p95:.2f} ms")
        print()
    aggregation_query = """
        MATCH (u:User)
        RETURN count(u) AS total_users
    """
    p50, p95 = measure(
        session,
        aggregation_query
    )
    print("Aggregation")
    print(f"p50: {p50:.2f} ms")
    print(f"p95: {p95:.2f} ms")
driver.close()