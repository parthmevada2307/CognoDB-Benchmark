# Graph Database Benchmark Suite: CognoDB vs AGE vs ArangoDB vs FalkorDB vs Memgraph

## 1. Overview & Setup
This project benchmarks 5 graph database engines (**Apache AGE**, **ArangoDB**, **CognoDB**, **FalkorDB**, and **Memgraph**) on identical workload patterns using Docker containers.

### Hardware & Test Environment
- **OS:** Windows / Linux (Docker Desktop)
- **CPU:** Standard Multi-Core Host CPU
- **RAM:** 16 GB Allocation

### Prerequisites & Dependencies
- Python 3.10+
- Docker & Docker Compose
- Install requirements:
  ```bash
  pip install -r requirements.txt