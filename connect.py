import os
from dotenv import load_dotenv

load_dotenv()

db_type = os.getenv("DB_TYPE", "arangodb").lower()

def connect():
    if db_type in ["cognodb", "neo4j", "memgraph"]:
        from neo4j import GraphDatabase
        # Map environment variables based on DB_TYPE
        if db_type == "cognodb":
            uri, user, pwd = (
                os.getenv("COGNODB_URI"),
                os.getenv("COGNODB_USER"),
                os.getenv("COGNODB_PASSWORD"),
            )
        elif db_type == "neo4j":
            uri = os.getenv("NEO4J_URI")
            user = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME")
            pwd = os.getenv("NEO4J_PASSWORD")
        else:  # memgraph
            uri, user, pwd = (
                os.getenv("MEMGRAPH_URI"),
                os.getenv("MEMGRAPH_USER"),
                os.getenv("MEMGRAPH_PASSWORD"),
            )

        auth = (user, pwd) if user and pwd else None

        driver = GraphDatabase.driver(uri, auth=auth)
        with driver.session() as session:
            msg = session.run("RETURN 'Connected successfully!' AS message").single()[
                "message"
            ]
            print(f"{db_type.upper()}: {msg}")
        driver.close()
    elif db_type == "arangodb":
        from arango import ArangoClient

        url = os.getenv("ARANGO_URL", "http://localhost:8529")
        user = os.getenv("ARANGO_USER", "root")
        pwd = os.getenv("ARANGO_PASSWORD", "your_password")

        client = ArangoClient(hosts=url)
        # Connect to system database to test connection
        sys_db = client.db("_system", username=user, password=pwd)

        res = sys_db.aql.execute("RETURN 'Connected successfully!'")
        print(f"ARANGODB: {res.next()}")
    elif db_type == "falkordb":
        import redis

        host = os.getenv("FALKORDB_HOST", "localhost")
        port = int(os.getenv("FALKORDB_PORT", 6379))

        r = redis.Redis(host=host, port=port, decode_responses=True)
        res = r.execute_command(
            "GRAPH.QUERY", "test_graph", "RETURN 'Connected successfully!' AS message"
        )
        print(f"FALKORDB: {res[0][0]}")

    elif db_type == "age":
        import psycopg2
        conn = psycopg2.connect(
            host=os.getenv("AGE_HOST", "localhost"),
            port=os.getenv("AGE_PORT", 5432),
            dbname=os.getenv("AGE_DATABASE", "postgres"),
            user=os.getenv("AGE_USER", "postgres"),
            password=os.getenv("AGE_PASSWORD", "postgres"),
        )
        with conn.cursor() as cur:
            cur.execute(
                "CREATE EXTENSION IF NOT EXISTS age; LOAD 'age'; SET search_path = ag_catalog, '$user', public;"
            )
            cur.execute("SELECT 'Connected successfully!' AS message;")
            print(f"AGE: {cur.fetchone()[0]}")
        conn.close()
    else:
        print(f"Unknown database type: {db_type}")
if __name__ == "__main__":
    connect()