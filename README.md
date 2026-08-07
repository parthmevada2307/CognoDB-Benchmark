# CognoDB Cloud Benchmark

## About this Project

This project was completed as part of the Wexa AI Graph Database Cloud Benchmarking assignment.

The goal was to compare CognoDB Cloud with other graph database platforms using the same dataset and similar resource limits. Instead of trying to make one database look better than another, the focus was on running the same workloads on every platform and collecting the results in a fair and repeatable way.

The benchmark measures data loading performance, graph traversal queries, lookup queries, aggregation queries, and mixed read/write workloads.

---

## Databases Used

The following databases were included in the benchmark:

* CognoDB Cloud
* Neo4j AuraDB Free
* Memgraph
* Apache AGE
* FalkorDB

---

## Dataset

The benchmark uses the **Wiki-Vote** dataset from the Stanford SNAP collection.

Dataset Source:

https://snap.stanford.edu/data/wiki-Vote.html

Dataset statistics:

* Nodes: 7,115
* Relationships: 103,689

The exact same dataset was loaded into every database so that the comparison stayed consistent.

---

## Project Structure

```text
.
├── benchmark.py
├── clear.py
├── connect.py
├── data.py
├── ingest.py
├── main.py
├── mixed.py
├── verify.py
├── pyproject.toml
├── README.md
├── data/
└── results/
```

---

## Requirements

* Python 3.10 or later
* Access to all graph databases being tested
* Dataset downloaded into the `data` folder

Install the project dependencies:

```bash
pip install -e .
```

or

```bash
pip install -r requirements.txt
```

---

## Environment Variables

Database credentials are stored in a `.env` file and are **not** included in the repository.

Example:

```text
COGNODB_URI=
COGNODB_USER=
COGNODB_PASSWORD=

NEO4J_URI=
NEO4J_USER=
NEO4J_PASSWORD=
```

---

## Running the Benchmark

To run the complete benchmark:

```bash
python main.py
```

Individual scripts can also be executed separately if only one part of the benchmark needs to be run.

For example:

```bash
python ingest.py
python benchmark.py
python mixed.py
```

---

## Benchmark Method

Every database was tested using the same dataset and equivalent resource limits whenever possible.

Before collecting results, the databases were warmed up to reduce the impact of startup delays.

Each workload was executed multiple times, and latency values were recorded using p50 and p95 measurements instead of relying only on averages.

The benchmark includes:

* Data loading
* 1-hop traversal
* 2-hop traversal
* 3-hop traversal
* Point lookups
* Indexed lookups
* Aggregation queries
* Mixed read/write workload

---

# Results

## Data Loading

| Database   |       Load Time |       Nodes/sec | Relationships/sec |
| ---------- | --------------: | --------------: | ----------------: |
| CognoDB    | *(your result)* | *(your result)* |   *(your result)* |
| Neo4j      | *(your result)* | *(your result)* |   *(your result)* |
| Memgraph   | *(your result)* | *(your result)* |   *(your result)* |
| Apache AGE | *(your result)* | *(your result)* |   *(your result)* |
| FalkorDB   | *(your result)* | *(your result)* |   *(your result)* |

---

## Traversal Queries

| Database   | 1-Hop p50 | 1-Hop p95 | 2-Hop p50 | 2-Hop p95 | 3-Hop p50 | 3-Hop p95 |
| ---------- | --------: | --------: | --------: | --------: | --------: | --------: |
| CognoDB    |           |           |           |           |           |           |
| Neo4j      |           |           |           |           |           |           |
| Memgraph   |           |           |           |           |           |           |
| Apache AGE |           |           |           |           |           |           |
| FalkorDB   |           |           |           |           |           |           |

---

## Lookup Queries

| Database   | Point Lookup p50 | Point Lookup p95 | Indexed Lookup p50 | Indexed Lookup p95 |
| ---------- | ---------------: | ---------------: | -----------------: | -----------------: |
| CognoDB    |                  |                  |                    |                    |
| Neo4j      |                  |                  |                    |                    |
| Memgraph   |                  |                  |                    |                    |
| Apache AGE |                  |                  |                    |                    |
| FalkorDB   |                  |                  |                    |                    |

---

## Mixed Workload

| Database   | Concurrent Clients | Queries/Second |
| ---------- | -----------------: | -------------: |
| CognoDB    |                    |                |
| Neo4j      |                    |                |
| Memgraph   |                    |                |
| Apache AGE |                    |                |
| FalkorDB   |                    |                |

---

## What I Observed

After running the benchmarks, each database showed different strengths depending on the workload. Some databases performed better during data ingestion, while others produced lower traversal latency or handled concurrent operations more efficiently.

Rather than focusing on a single winner, this benchmark highlights the trade-offs between different graph database platforms under similar testing conditions.

---

## Limitations

A few things should be considered while reading the results:

* Most platforms were tested using free-tier or limited resources.
* Network latency can affect managed cloud databases.
* Some platforms expose fewer resource metrics than others.
* Small differences between runs are expected because of shared cloud infrastructure.

---

## Reproducing the Benchmark

Clone the repository:

```bash
git clone <repository-url>
```

Move into the project:

```bash
cd <repository-folder>
```

Install the dependencies:

```bash
pip install -e .
```

Configure the required environment variables in a `.env` file.

Run:

```bash
python main.py
```

The benchmark scripts will load the dataset, execute the configured workloads, and generate the benchmark results.

---

## Notes

This project was completed for the Wexa AI benchmarking assignment. The focus was on creating a benchmark that is easy to reproduce, uses the same workload across multiple databases, and reports the results as accurately as possible.
