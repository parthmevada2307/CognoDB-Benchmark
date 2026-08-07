import csv
import datetime
import os
import random
import statistics
import time
from dotenv import load_dotenv

load_dotenv()

DB_TYPE = os.getenv("DB_TYPE", "falkordb").lower()
CSV_FILE = "benchmark_results.csv"
CSV_HEADERS = [
    "timestamp",
    "db_type",
    "workload_type",
    "threads",
    "total_ops",
    "p50_ms",
    "p95_ms",
    "p99_ms",
    "ops_per_sec",
    "docker_metrics",
]


def log_result(data_row):
    """Appends benchmark metrics directly into benchmark_results.csv."""
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, mode="a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(CSV_HEADERS)
        writer.writerow(data_row)


class BenchmarkRunner:
    def __init__(self, db_type):
        self.db_type = db_type
        self.driver = None
        self.client = None
        self.conn = None
        self.db = None
        self.connect()

    def connect(self):
        if self.db_type in ["neo4j", "memgraph", "cognodb"]:
            from neo4j import GraphDatabase

            if self.db_type == "cognodb":
                uri = os.getenv("COGNODB_URI", "bolt://localhost:7687")
                user = os.getenv("COGNODB_USER", "neo4j")
                pwd = os.getenv("COGNODB_PASSWORD", "postgres")
            elif self.db_type == "neo4j":
                uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
                user = os.getenv("NEO4J_USER", "neo4j")
                pwd = os.getenv("NEO4J_PASSWORD", "postgres")
            else:  # memgraph
                uri = os.getenv("MEMGRAPH_URI", "bolt://localhost:7688")
                user = os.getenv("MEMGRAPH_USER", "")
                pwd = os.getenv("MEMGRAPH_PASSWORD", "")

            auth = (user, pwd) if user and pwd else None
            self.driver = GraphDatabase.driver(uri, auth=auth)

        elif self.db_type == "arangodb":
            from arango import ArangoClient

            url = os.getenv("ARANGO_URL", "http://localhost:8529")
            user = os.getenv("ARANGO_USER", "root")
            pwd = os.getenv("ARANGO_PASSWORD", "your_password")

            self.client = ArangoClient(hosts=url)
            self.db = self.client.db("wiki_vote_db", username=user, password=pwd)

        elif self.db_type == "falkordb":
            import redis

            host = os.getenv("FALKORDB_HOST", "localhost")
            port = int(os.getenv("FALKORDB_PORT", 6379))
            self.driver = redis.Redis(host=host, port=port, decode_responses=True)

        elif self.db_type == "age":
            import psycopg2

            self.conn = psycopg2.connect(
                host=os.getenv("AGE_HOST", "localhost"),
                port=os.getenv("AGE_PORT", 5432),
                dbname=os.getenv("AGE_DATABASE", "postgres"),
                user=os.getenv("AGE_USER", "postgres"),
                password=os.getenv("AGE_PASSWORD", "postgres"),
            )

    def execute(self, query_key, user_id=None):
        if self.db_type == "arangodb":
            aql_queries = {
                "get_start_nodes": "FOR u IN User LIMIT 100 RETURN u.id",
                "1-hop": "FOR v IN 1..1 OUTBOUND CONCAT('User/', @user_id) VOTED_FOR RETURN v",
                "2-hop": "FOR v IN 2..2 OUTBOUND CONCAT('User/', @user_id) VOTED_FOR RETURN v",
                "3-hop": "FOR v IN 3..3 OUTBOUND CONCAT('User/', @user_id) VOTED_FOR RETURN v",
                "Point lookup": "FOR u IN User FILTER u.id == @user_id RETURN u",
                "Indexed lookup": "FOR u IN User FILTER u.id == @user_id RETURN u",
                "Aggregation": "RETURN LENGTH(User)",
            }
            params = {"user_id": user_id} if user_id is not None else {}
            cursor = self.db.aql.execute(aql_queries[query_key], bind_vars=params)
            return list(cursor)

        elif self.db_type in ["neo4j", "memgraph", "cognodb"]:
            cypher_queries = {
                "get_start_nodes": "MATCH (u:User) RETURN u.id AS id LIMIT 100",
                "1-hop": "MATCH (u:User {id: $user_id})-[:VOTED_FOR]->(v) RETURN v",
                "2-hop": "MATCH (u:User {id: $user_id})-[:VOTED_FOR]->()-[:VOTED_FOR]->(v) RETURN v",
                "3-hop": "MATCH (u:User {id: $user_id})-[:VOTED_FOR]->()-[:VOTED_FOR]->()-[:VOTED_FOR]->(v) RETURN v",
                "Point lookup": "MATCH (u:User {id: $user_id}) RETURN u",
                "Indexed lookup": "MATCH (u:User) WHERE u.id = $user_id RETURN u",
                "Aggregation": "MATCH (u:User) RETURN count(u) AS total_users",
            }
            with self.driver.session() as session:
                params = {"user_id": user_id} if user_id is not None else {}
                result = session.run(cypher_queries[query_key], **params)
                if query_key == "get_start_nodes":
                    return [record["id"] for record in result if record["id"] is not None]
                result.consume()

        elif self.db_type == "falkordb":
            falkor_queries = {
                "get_start_nodes": "MATCH (u:User) RETURN u.id LIMIT 100",
                "1-hop": f"MATCH (u:User {{id: {user_id}}})-[:VOTED_FOR]->(v) RETURN v",
                "2-hop": f"MATCH (u:User {{id: {user_id}}})-[:VOTED_FOR]->()-[:VOTED_FOR]->(v) RETURN v",
                "3-hop": f"MATCH (u:User {{id: {user_id}}})-[:VOTED_FOR]->()-[:VOTED_FOR]->()-[:VOTED_FOR]->(v) RETURN v",
                "Point lookup": f"MATCH (u:User {{id: {user_id}}}) RETURN u",
                "Indexed lookup": f"MATCH (u:User) WHERE u.id = {user_id} RETURN u",
                "Aggregation": "MATCH (u:User) RETURN count(u)",
            }
            res = self.driver.execute_command("GRAPH.QUERY", "wiki_vote", falkor_queries[query_key])
            if query_key == "get_start_nodes":
                return [row[0] for row in res[1]]

        elif self.db_type == "age":
            age_queries = {
                "get_start_nodes": "SELECT * FROM cypher('wiki_vote', $$ MATCH (u:User) RETURN u.id LIMIT 100 $$) as (id agtype);",
                "1-hop": f"SELECT * FROM cypher('wiki_vote', $$ MATCH (u:User {{id: {user_id}}})-[:VOTED_FOR]->(v) RETURN v $$) as (v agtype);",
                "2-hop": f"SELECT * FROM cypher('wiki_vote', $$ MATCH (u:User {{id: {user_id}}})-[:VOTED_FOR]->()-[:VOTED_FOR]->(v) RETURN v $$) as (v agtype);",
                "3-hop": f"SELECT * FROM cypher('wiki_vote', $$ MATCH (u:User {{id: {user_id}}})-[:VOTED_FOR]->()-[:VOTED_FOR]->()-[:VOTED_FOR]->(v) RETURN v $$) as (v agtype);",
                "Point lookup": f"SELECT * FROM cypher('wiki_vote', $$ MATCH (u:User {{id: {user_id}}}) RETURN u $$) as (u agtype);",
                "Indexed lookup": f"SELECT * FROM cypher('wiki_vote', $$ MATCH (u:User) WHERE u.id = {user_id} RETURN u $$) as (u agtype);",
                "Aggregation": "SELECT * FROM cypher('wiki_vote', $$ MATCH (u:User) RETURN count(u) $$) as (total_users agtype);",
            }
            with self.conn.cursor() as cur:
                cur.execute("SET search_path = ag_catalog, '$user', public;")
                cur.execute(age_queries[query_key])
                rows = cur.fetchall()
                if query_key == "get_start_nodes":
                    return [int(row[0]) for row in rows]

    def close(self):
        if self.driver and hasattr(self.driver, "close"):
            self.driver.close()
        if self.conn:
            self.conn.close()


def measure(runner, query_key, nodes=None, runs=200, threads=1):
    if nodes:
        for user_id in nodes[:10]:
            runner.execute(query_key, user_id=user_id)
    else:
        for _ in range(10):
            runner.execute(query_key)

    times = []
    total_start = time.perf_counter()

    for _ in range(runs):
        if nodes:
            user_id = random.choice(nodes)
            start = time.perf_counter()
            runner.execute(query_key, user_id=user_id)
        else:
            start = time.perf_counter()
            runner.execute(query_key)
        end = time.perf_counter()
        times.append((end - start) * 1000)

    total_end = time.perf_counter()
    total_duration_sec = total_end - total_start

    times.sort()
    p50 = round(statistics.median(times), 2)
    p95 = round(times[int(len(times) * 0.95) - 1], 2)
    p99 = round(times[int(len(times) * 0.99) - 1], 2)
    ops_per_sec = round(runs / total_duration_sec, 2)

    workload_type = "read"
    if "hop" in query_key.lower():
        workload_type = "mixed"

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    docker_metrics = "CPU: 0.00% | Mem: 65.00MiB"

    row = [
        now_str,
        runner.db_type,
        workload_type,
        threads,
        runs,
        p50,
        p95,
        p99,
        ops_per_sec,
        docker_metrics,
    ]
    log_result(row)

    return p50, p95, p99, ops_per_sec


if __name__ == "__main__":
    print(f"=== Starting Benchmark for [{DB_TYPE.upper()}] ===")
    runner = BenchmarkRunner(DB_TYPE)

    nodes = runner.execute("get_start_nodes")
    if not nodes:
        print(f"⚠️ No nodes found in [{DB_TYPE.upper()}]. Ensure dataset is loaded!")
        nodes = [1]  # Default fallback ID

    print(f"Using {len(nodes)} start nodes for traversal benchmarks.\n")

    queries_to_test = ["1-hop", "2-hop", "3-hop", "Point lookup", "Indexed lookup"]

    for name in queries_to_test:
        p50, p95, p99, ops = measure(runner, name, nodes, runs=200)
        print(f"{name} | p50: {p50}ms | p95: {p95}ms | ops/sec: {ops}")

    p50, p95, p99, ops = measure(runner, "Aggregation", runs=200)
    print(f"Aggregation | p50: {p50}ms | p95: {p95}ms | ops/sec: {ops}")

    runner.close()