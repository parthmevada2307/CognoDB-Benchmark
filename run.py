import os
import subprocess
import sys
import time

# Only list the remaining databases to benchmark
DATABASES = ["memgraph", "arangodb", "cognodb", "age", "falkordb"]

def run_suite():
    print("Running benchmarks for remaining databases...\n")
    python_exe = sys.executable

    for db in DATABASES:
        print("=" * 60)
        print(f"  RUNNING BENCHMARK: {db.upper()}")
        print("=" * 60)

        env = os.environ.copy()
        env["DB_TYPE"] = db

        try:
            subprocess.run([python_exe, "benchmark.py"], env=env, check=True)
            print(f"Successfully finished {db.upper()}\n")
        except subprocess.CalledProcessError as e:
            print(f"Failed to run {db.upper()}: {e}\n")

        time.sleep(2)

    print("\n🎉 Remaining benchmarks finished! All engines are now in benchmark_results.csv.")

if __name__ == "__main__":
    run_suite()