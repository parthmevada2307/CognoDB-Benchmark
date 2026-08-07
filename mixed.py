import csv
from datetime import datetime
import os
import random
import statistics
import subprocess
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

DB_TYPE = os.getenv("DB_TYPE", "age").lower()
WORKLOAD_TYPE = os.getenv("WORKLOAD_TYPE", "mixed").lower()  # 'read', 'write', or 'mixed'
TOTAL_OPS = int(os.getenv("TOTAL_OPS", "100"))
WORKERS = int(os.getenv("WORKERS", "10"))
CSV_FILE = "benchmark_results.csv"

CONTAINER_NAMES = {
    "age": "apache-age",
    "falkordb": "falkordb",
    "memgraph": "memgraph",
    "neo4j": "neo4j",
    "arangodb": "arangodb",
}

class BaseWorkloadRunner(ABC):
    @abstractmethod
    def connect(self): pass

    @abstractmethod
    def setup_schema(self): pass

    @abstractmethod
    def get_users(self) -> list[int]: pass

    @abstractmethod
    def read_operation(self, user_id: int): pass

    @abstractmethod
    def write_operation(self, operation_id: int): pass

    @abstractmethod
    def close(self): pass
class Neo4jFamilyWorkload(BaseWorkloadRunner):
    def __init__(self, db_type: str):
        self.db_type = db_type
        self.driver = None

    def connect(self):
        from neo4j import GraphDatabase
        if self.db_type == "cognodb":
            uri = os.getenv("COGNODB_URI", "bolt://127.0.0.1:7687")
            user, pwd = os.getenv("COGNODB_USER"), os.getenv("COGNODB_PASSWORD")
        elif self.db_type == "neo4j":
            uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
            user = os.getenv("NEO4J_USER", "neo4j")
            pwd = os.getenv("NEO4J_PASSWORD", "password")
        else:  # memgraph
            uri = os.getenv("MEMGRAPH_URI", "bolt://127.0.0.1:7687")
            user, pwd = os.getenv("MEMGRAPH_USER", ""), os.getenv("MEMGRAPH_PASSWORD", "")

        auth = (user, pwd) if user and pwd else None
        self.driver = GraphDatabase.driver(uri, auth=auth)
        self.driver.verify_connectivity()
    def setup_schema(self):
        query = ("CREATE CONSTRAINT IF NOT EXISTS FOR (u:BenchmarkUser) REQUIRE u.id IS UNIQUE"
                 if self.db_type != "memgraph" else "CREATE INDEX ON :BenchmarkUser(id);")
        with self.driver.session() as session:
            try: session.run(query)
            except Exception: pass

    def get_users(self) -> list[int]:
        try:
            with self.driver.session() as session:
                result = session.run("MATCH (u:User) RETURN u.id AS id LIMIT 100")
                users = [record["id"] for record in result if record["id"] is not None]
                if users: return users
        except Exception: pass
        return list(range(1, 101))

    def read_operation(self, user_id: int):
        query = "MATCH (u:User {id: $user_id})-[:VOTED_FOR]->(v) RETURN count(v) AS total"
        with self.driver.session() as session:
            try:
                session.run(query, user_id=user_id).consume()
            except Exception:
                fallback = "MATCH (u:BenchmarkUser {id: $user_id})-[:BENCHMARK_VOTED]->(v) RETURN count(v) AS total"
                session.run(fallback, user_id=user_id).consume()

    def write_operation(self, operation_id: int):
        s, t = 900000 + operation_id, 910000 + operation_id
        query = "MERGE (a:BenchmarkUser {id: $s}) MERGE (b:BenchmarkUser {id: $t}) MERGE (a)-[:BENCHMARK_VOTED]->(b)"
        with self.driver.session() as session:
            session.run(query, s=s, t=t).consume()

    def close(self):
        if self.driver: self.driver.close()


class FalkorDBWorkload(BaseWorkloadRunner):
    def __init__(self): self.r = None

    def connect(self):
        import redis
        self.r = redis.Redis(host=os.getenv("FALKORDB_HOST", "127.0.0.1"),
                             port=int(os.getenv("FALKORDB_PORT", 6379)),
                             decode_responses=True)
        self.r.ping()

    def setup_schema(self):
        try: self.r.execute_command("GRAPH.QUERY", "benchmark_graph", "CREATE INDEX FOR (u:BenchmarkUser) ON (u.id)")
        except Exception: pass

    def get_users(self) -> list[int]:
        try:
            res = self.r.execute_command("GRAPH.QUERY", "wiki_vote", "MATCH (u:User) RETURN u.id LIMIT 100")
            users = [row[0] for row in res[1] if row[0] is not None]
            if users: return users
        except Exception: pass
        return list(range(1, 101))

    def read_operation(self, user_id: int):
        try: self.r.execute_command("GRAPH.QUERY", "wiki_vote", f"MATCH (u:User {{id: {user_id}}})-[:VOTED_FOR]->(v) RETURN count(v)")
        except Exception:
            try: self.r.execute_command("GRAPH.QUERY", "benchmark_graph", f"MATCH (u:BenchmarkUser {{id: {user_id}}})-[:BENCHMARK_VOTED]->(v) RETURN count(v)")
            except Exception: pass

    def write_operation(self, operation_id: int):
        s, t = 900000 + operation_id, 910000 + operation_id
        self.r.execute_command("GRAPH.QUERY", "benchmark_graph",
                                f"MERGE (a:BenchmarkUser {{id: {s}}}) MERGE (b:BenchmarkUser {{id: {t}}}) MERGE (a)-[:BENCHMARK_VOTED]->(b)")

    def close(self):
        if self.r: self.r.close()


class AgeWorkload(BaseWorkloadRunner):
    def __init__(self): self.pool = None

    def connect(self):
        from psycopg2.pool import ThreadedConnectionPool
        self.pool = ThreadedConnectionPool(
            minconn=2, maxconn=20,
            host=os.getenv("AGE_HOST", "127.0.0.1"),
            port=int(os.getenv("AGE_PORT", 5432)),
            dbname=os.getenv("AGE_DATABASE", "postgres"),
            user=os.getenv("AGE_USER", "postgres"),
            password=os.getenv("AGE_PASSWORD", "postgres")
        )

    def setup_schema(self):
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS age; LOAD 'age'; SET search_path = ag_catalog, '$user', public;")
                cur.execute("SELECT * FROM ag_catalog.ag_graph WHERE name = 'benchmark_graph';")
                if not cur.fetchone():
                    cur.execute("SELECT create_graph('benchmark_graph');")
                conn.commit()
        except Exception: conn.rollback()
        finally: self.pool.putconn(conn)

    def get_users(self) -> list[int]:
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SET search_path = ag_catalog, '$user', public;")
                cur.execute("SELECT * FROM cypher('wiki_vote', $$ MATCH (u:User) RETURN u.id LIMIT 100 $$) as (id agtype);")
                rows = cur.fetchall()
                users = [int(str(r[0]).strip('"')) for r in rows if r[0] is not None and str(r[0]).strip('"').isdigit()]
                if users: return users
        except Exception: conn.rollback()
        finally: self.pool.putconn(conn)
        return list(range(1, 101))

    def read_operation(self, user_id: int):
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SET search_path = ag_catalog, '$user', public;")
                try:
                    cur.execute(f"SELECT * FROM cypher('wiki_vote', $$ MATCH (u:User {{id: {user_id}}})-[:VOTED_FOR]->(v) RETURN count(v) $$) as (total agtype);")
                    cur.fetchall()
                except Exception:
                    conn.rollback()
                    cur.execute("SET search_path = ag_catalog, '$user', public;")
                    cur.execute(f"SELECT * FROM cypher('benchmark_graph', $$ MATCH (u:BenchmarkUser {{id: {user_id}}})-[:BENCHMARK_VOTED]->(v) RETURN count(v) $$) as (total agtype);")
                    cur.fetchall()
        except Exception: conn.rollback()
        finally: self.pool.putconn(conn)

    def write_operation(self, operation_id: int):
        conn = self.pool.getconn()
        try:
            s, t = 900000 + operation_id, 910000 + operation_id
            query = f"SELECT * FROM cypher('benchmark_graph', $$ MERGE (a:BenchmarkUser {{id: {s}}}) MERGE (b:BenchmarkUser {{id: {t}}}) MERGE (a)-[:BENCHMARK_VOTED]->(b) $$) as (a agtype);"
            with conn.cursor() as cur:
                cur.execute("SET search_path = ag_catalog, '$user', public;")
                cur.execute(query)
                conn.commit()
        except Exception: conn.rollback()
        finally: self.pool.putconn(conn)

    def close(self):
        if self.pool: self.pool.closeall()

def get_runner(db_type: str) -> BaseWorkloadRunner:
    if db_type in ["neo4j", "cognodb", "memgraph"]: return Neo4jFamilyWorkload(db_type)
    elif db_type == "falkordb": return FalkorDBWorkload()
    elif db_type == "age": return AgeWorkload()
    raise ValueError(f"Unsupported DB_TYPE: {db_type}")

def get_container_stats(db_type: str) -> str:
    container_name = CONTAINER_NAMES.get(db_type)
    if not container_name: return "N/A"
    try:
        # Pass command list directly to prevent Windows Shell variable escaping issues
        cmd = [
            "docker", "stats", container_name,
            "--no-stream",
            "--format", "CPU: {{.CPUPerc}} | Mem: {{.MemUsage}}"
        ]
        output = subprocess.check_output(cmd, text=True).strip()
        return output if output else "N/A"
    except Exception:
        return "N/A"

def append_to_csv(data: dict):
    file_exists = os.path.isfile(CSV_FILE)
    fieldnames = ["timestamp", "db_type", "workload_type", "threads", "total_ops", "p50_ms", "p95_ms", "p99_ms", "ops_sec", "docker_resources"]
    with open(CSV_FILE, mode="a", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)

def main():
    print(f"\n=== Running Benchmark [{DB_TYPE.upper()}] | Workload: {WORKLOAD_TYPE.upper()} | Threads: {WORKERS} ===")
    runner = get_runner(DB_TYPE)
    try:
        runner.connect()
    except Exception as e:
        print(f"[ERROR] Connection failed for {DB_TYPE.upper()}: {e}")
        return

    runner.setup_schema()
    users = runner.get_users()

    # Warm-up phase
    for user_id in users[:5]:
        try: runner.read_operation(user_id)
        except Exception: pass

    results = []
    start_total_time = time.perf_counter()

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = []
        for i in range(TOTAL_OPS):
            if WORKLOAD_TYPE == "read":
                u_id = random.choice(users)
                futures.append(executor.submit(lambda r, u: (time.perf_counter(), r.read_operation(u), time.perf_counter()), runner, u_id))
            elif WORKLOAD_TYPE == "write":
                futures.append(executor.submit(lambda r, op: (time.perf_counter(), r.write_operation(op), time.perf_counter()), runner, i))
            else:  # Mixed
                if i % 2 == 0:
                    u_id = random.choice(users)
                    futures.append(executor.submit(lambda r, u: (time.perf_counter(), r.read_operation(u), time.perf_counter()), runner, u_id))
                else:
                    futures.append(executor.submit(lambda r, op: (time.perf_counter(), r.write_operation(op), time.perf_counter()), runner, i))

        for future in as_completed(futures):
            try:
                t_start, _, t_end = future.result()
                results.append((t_end - t_start) * 1000)
            except Exception:
                pass

    total_duration = time.perf_counter() - start_total_time

    if results:
        results.sort()
        p50 = statistics.median(results)
        p95 = results[int(len(results) * 0.95) - 1]
        p99 = results[int(len(results) * 0.99) - 1]
        ops_sec = len(results) / total_duration
        docker_usage = get_container_stats(DB_TYPE)

        print("-----------------------------------------")
        print(f"Completed:  {len(results)} ops in {total_duration:.2f}s ({ops_sec:.1f} ops/sec)")
        print(f"p50: {p50:.2f} ms | p95: {p95:.2f} ms | p99: {p99:.2f} ms")
        print(f"Docker Metrics: {docker_usage}")
        print("-----------------------------------------")

        append_to_csv({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "db_type": DB_TYPE,
            "workload_type": WORKLOAD_TYPE,
            "threads": WORKERS,
            "total_ops": len(results),
            "p50_ms": round(p50, 2),
            "p95_ms": round(p95, 2),
            "p99_ms": round(p99, 2),
            "ops_sec": round(ops_sec, 2),
            "docker_resources": docker_usage
        })
    else:
        print("[ERROR] No operations succeeded.")

    runner.close()

if __name__ == "__main__":
    main()