import os
import time
from abc import ABC, abstractmethod
from dotenv import load_dotenv

load_dotenv()
DB_TYPE = os.getenv("DB_TYPE", "falkordb").lower()
FILE_PATH = "datasets/Wiki-Vote.txt"
BATCH_SIZE = 5000  # Optimal chunk size for batch processing across databases

class BaseIngestor(ABC):

    @abstractmethod
    def connect(self):
        pass
    @abstractmethod
    def setup_schema(self):
        pass
    @abstractmethod
    def ingest_batch(self, batch: list[dict]):
        pass
    @abstractmethod
    def close(self):
        pass


class Neo4jFamilyIngestor(BaseIngestor):
    """Handles Neo4j, CognoDB, and Memgraph (Cypher-based)."""

    def __init__(self, db_type: str):
        self.db_type = db_type
        self.driver = None

    def connect(self):
        from neo4j import GraphDatabase

        if self.db_type == "cognodb":
            uri = os.getenv("COGNODB_URI")
            user = os.getenv("COGNODB_USER")
            pwd = os.getenv("COGNODB_PASSWORD")
        elif self.db_type == "neo4j":
            uri = os.getenv("NEO4J_URI")
            user = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME")
            pwd = os.getenv("NEO4J_PASSWORD")
        else:  # memgraph
            uri = os.getenv("MEMGRAPH_URI")
            user = os.getenv("MEMGRAPH_USER")
            pwd = os.getenv("MEMGRAPH_PASSWORD")

        auth = (user, pwd) if user and pwd else None
        self.driver = GraphDatabase.driver(uri, auth=auth)

    def setup_schema(self):
        # Memgraph and Neo4j schema constraint syntax
        if self.db_type in ["neo4j", "cognodb"]:
            query = "CREATE CONSTRAINT IF NOT EXISTS FOR (u:BenchmarkUser) REQUIRE u.id IS UNIQUE"
            with self.driver.session() as session:
                session.run(query)

    def ingest_batch(self, batch: list[dict]):
        query = """
        UNWIND $batch AS row
        MERGE (a:BenchmarkUser {id: row.source})
        MERGE (b:BenchmarkUser {id: row.target})
        MERGE (a)-[:BENCHMARK_VOTED]->(b)
        """
        with self.driver.session() as session:
            session.execute_write(lambda tx: tx.run(query, batch=batch))

    def close(self):
        if self.driver:
            self.driver.close()


class ArangoDBIngestor(BaseIngestor):
    """Handles ArangoDB high-speed native bulk import."""

    def __init__(self):
        self.client = None
        self.db = None

    def connect(self):
        from arango import ArangoClient

        url = os.getenv("ARANGO_URL", "http://localhost:8529")
        user = os.getenv("ARANGO_USER", "root")
        pwd = os.getenv("ARANGO_PASSWORD", "your_password")

        self.client = ArangoClient(hosts=url)
        sys_db = self.client.db("_system", username=user, password=pwd)

        if not sys_db.has_database("benchmark_db"):
            sys_db.create_database("benchmark_db")

        self.db = self.client.db("benchmark_db", username=user, password=pwd)

    def setup_schema(self):
        if not self.db.has_collection("BenchmarkUser"):
            self.db.create_collection("BenchmarkUser")
        if not self.db.has_collection("BENCHMARK_VOTED"):
            self.db.create_collection("BENCHMARK_VOTED", edge=True)

    def ingest_batch(self, batch: list[dict]):
        # Extract unique nodes in batch to populate Vertex Collection
        node_ids = set()
        for row in batch:
            node_ids.add(row["source"])
            node_ids.add(row["target"])

        nodes = [{"_key": str(uid), "id": uid} for uid in node_ids]
        edges = [
            {
                "_from": f"BenchmarkUser/{row['source']}",
                "_to": f"BenchmarkUser/{row['target']}",
            }
            for row in batch
        ]

        # Native bulk import
        self.db.collection("BenchmarkUser").import_bulk(
            nodes, on_duplicate="ignore"
        )
        self.db.collection("BENCHMARK_VOTED").import_bulk(
            edges, on_duplicate="ignore"
        )

    def close(self):
        pass


class FalkorDBIngestor(BaseIngestor):
    """Handles FalkorDB (RedisGraph commands)."""

    def __init__(self):
        self.r = None

    def connect(self):
        import redis

        host = os.getenv("FALKORDB_HOST", "localhost")
        port = int(os.getenv("FALKORDB_PORT", 6379))
        self.r = redis.Redis(host=host, port=port, decode_responses=True)

    def setup_schema(self):
        query = "CREATE INDEX FOR (u:BenchmarkUser) ON (u.id)"
        try:
            self.r.execute_command("GRAPH.QUERY", "benchmark_graph", query)
        except Exception:
            pass  # Index may already exist

    def ingest_batch(self, batch: list[dict]):
        cypher = """
        UNWIND $batch AS row
        MERGE (a:BenchmarkUser {id: row.source})
        MERGE (b:BenchmarkUser {id: row.target})
        MERGE (a)-[:BENCHMARK_VOTED]->(b)
        """
        self.r.execute_command(
            "GRAPH.QUERY",
            "benchmark_graph",
            f"CYPHER batch='{batch}' {cypher}",
        )

    def close(self):
        if self.r:
            self.r.close()


class AgeIngestor(BaseIngestor):
    """Handles Apache AGE PostgreSQL wrapper."""

    def __init__(self):
        self.conn = None

    def connect(self):
        import psycopg2

        self.conn = psycopg2.connect(
            host=os.getenv("AGE_HOST", "localhost"),
            port=os.getenv("AGE_PORT", 5432),
            dbname=os.getenv("AGE_DATABASE", "postgres"),
            user=os.getenv("AGE_USER", "postgres"),
            password=os.getenv("AGE_PASSWORD", "postgres"),
        )

    def setup_schema(self):
        with self.conn.cursor() as cur:
            cur.execute(
                "CREATE EXTENSION IF NOT EXISTS age; LOAD 'age'; SET search_path = ag_catalog, '$user', public;"
            )
            cur.execute(
                "SELECT * FROM ag_catalog.ag_graph WHERE name = 'benchmark_graph';"
            )
            if not cur.fetchone():
                cur.execute("SELECT create_graph('benchmark_graph');")
            self.conn.commit()

    def ingest_batch(self, batch: list[dict]):
        with self.conn.cursor() as cur:
            cur.execute("SET search_path = ag_catalog, '$user', public;")
            for row in batch:
                cypher = f"""
                SELECT * FROM cypher('benchmark_graph', $$
                    MERGE (a:BenchmarkUser {{id: {row['source']}}})
                    MERGE (b:BenchmarkUser {{id: {row['target']}}})
                    MERGE (a)-[:BENCHMARK_VOTED]->(b)
                $$) as (a agtype);
                """
                cur.execute(cypher)
            self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()
def get_ingestor(db_type: str) -> BaseIngestor:
    if db_type in ["neo4j", "cognodb", "memgraph"]:
        return Neo4jFamilyIngestor(db_type)
    elif db_type == "arangodb":
        return ArangoDBIngestor()
    elif db_type == "falkordb":
        return FalkorDBIngestor()
    elif db_type == "age":
        return AgeIngestor()
    else:
        raise ValueError(f"Unsupported DB_TYPE: {db_type}")


def parse_dataset(file_path: str) -> list[dict]:
    records = []
    with open(file_path, "r") as file:
        for line in file:
            if line.startswith("#") or not line.strip():
                continue
            source, target = line.strip().split()
            records.append({"source": int(source), "target": int(target)})
    return records
def run_benchmark():
    print(f"=== Starting Ingestion Benchmark for [{DB_TYPE.upper()}] ===")

    records = parse_dataset(FILE_PATH)
    total_records = len(records)
    print(f"Dataset Loaded: {total_records} relationship records ready.")

    ingestor = get_ingestor(DB_TYPE)
    ingestor.connect()
    ingestor.setup_schema()

    start_time = time.perf_counter()

    for i in range(0, total_records, BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        ingestor.ingest_batch(batch)
        print(
            f"  Ingested {min(i + BATCH_SIZE, total_records)} / {total_records} records..."
        )

    end_time = time.perf_counter()
    elapsed = end_time - start_time
    throughput = total_records / elapsed if elapsed > 0 else 0
    print(f"Ingestion Results [{DB_TYPE.upper()}]:")
    print(f"Total Records Ingested: {total_records}")
    print(f"Total Duration:         {elapsed:.2f} seconds")
    print(f"Throughput Rate:        {throughput:.2f} records/sec")
    ingestor.close()

if __name__ == "__main__":
    run_benchmark()