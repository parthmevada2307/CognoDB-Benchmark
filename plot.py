import os
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

CSV_FILE = "benchmark_results.csv"
OUTPUT_IMAGE = "graph_benchmark_summary.png"


def find_column(df, candidates):
    cols_clean = {c.strip().lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in cols_clean:
            return cols_clean[cand.lower()]
    return None


def plot_benchmark_results():
    if not os.path.exists(CSV_FILE):
        print(f"[ERROR] '{CSV_FILE}' not found.")
        return

    df = pd.read_csv(CSV_FILE)
    if df.empty:
        print(f"[ERROR] '{CSV_FILE}' is empty.")
        return

    db_col = find_column(df, ["db_type", "database", "db"])
    workload_col = find_column(df, ["workload_type", "workload"])
    ops_col = find_column(
        df, ["ops_per_sec", "ops_sec", "throughput", "ops_per_second", "ops/sec"]
    )
    p50_col = find_column(df, ["p50_ms", "p50"])
    p95_col = find_column(df, ["p95_ms", "p95"])

    # Standardize string formatting
    df[db_col] = df[db_col].astype(str).str.strip().str.upper()
    df[workload_col] = df[workload_col].astype(str).str.strip().str.upper()

    plot_df = (
        df.groupby([db_col, workload_col]).tail(3).reset_index(drop=True)
    )

    db_types = sorted(plot_df[db_col].unique())
    workloads = [
        w for w in ["READ", "MIXED", "WRITE"] if w in plot_df[workload_col].unique()
    ]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 6))
    plt.subplots_adjust(wspace=0.3)

    x = np.arange(len(db_types))
    width = 0.22

    # --- Chart 1: Throughput (Ops/Sec) ---
    max_ops = 0
    for i, w in enumerate(workloads):
        subset = plot_df[plot_df[workload_col] == w]
        ops_val = []
        for db in db_types:
            vals = subset[subset[db_col] == db][ops_col].values
            avg = np.mean(vals) if len(vals) > 0 else 0
            ops_val.append(avg)

        offset = x + (i - len(workloads) / 2 + 0.5) * width
        rects = ax1.bar(
            offset, ops_val, width, label=f"{w} Workload", alpha=0.85
        )

        for rect in rects:
            height = rect.get_height()
            if height > max_ops:
                max_ops = height
            if height > 0:
                ax1.annotate(
                    f"{height:.1f}",
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 4),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    fontweight="bold",
                )

    ax1.set_title(
        "Throughput Comparison Across All Databases",
        fontsize=13,
        fontweight="bold",
        pad=12,
    )
    ax1.set_ylabel("Operations / Second (Higher is better)", fontsize=11)
    ax1.set_xticks(x)
    ax1.set_xticklabels(db_types, fontweight="bold")
    ax1.set_ylim(0, max_ops * 1.18)  # Add 18% headroom to prevent label clipping
    ax1.legend(loc="upper left")
    ax1.grid(axis="y", linestyle="--", alpha=0.5)

    # --- Chart 2: Latency Profile (Mixed Workload) ---
    mixed_df = plot_df[plot_df[workload_col] == "MIXED"]

    p50_vals, p95_vals = [], []
    for db in db_types:
        v_p50 = mixed_df[mixed_df[db_col] == db][p50_col].values
        v_p95 = mixed_df[mixed_df[db_col] == db][p95_col].values
        p50_vals.append(np.mean(v_p50) if len(v_p50) > 0 else 0)
        p95_vals.append(np.mean(v_p95) if len(v_p95) > 0 else 0)

    max_lat = max(max(p50_vals, default=0), max(p95_vals, default=0))

    bar_w = 0.35
    ax2.bar(
        x - bar_w / 2,
        p50_vals,
        bar_w,
        label="p50 (Median)",
        color="#1f77b4",
        alpha=0.9,
    )
    ax2.bar(
        x + bar_w / 2,
        p95_vals,
        bar_w,
        label="p95 (Tail)",
        color="#ff7f0e",
        alpha=0.8,
    )

    for i in range(len(db_types)):
        if p50_vals[i] > 0:
            ax2.annotate(
                f"{p50_vals[i]:.1f}ms",
                xy=(x[i] - bar_w / 2, p50_vals[i]),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
            )
        if p95_vals[i] > 0:
            ax2.annotate(
                f"{p95_vals[i]:.1f}ms",
                xy=(x[i] + bar_w / 2, p95_vals[i]),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
            )

    ax2.set_title(
        "Latency Profile - Mixed Workload", fontsize=13, fontweight="bold", pad=12
    )
    ax2.set_ylabel("Latency in ms (Lower is better)", fontsize=11)
    ax2.set_xticks(x)
    ax2.set_xticklabels(db_types, fontweight="bold")
    ax2.set_ylim(0, max_lat * 1.15)  # Add 15% headroom
    ax2.legend(loc="upper left")
    ax2.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(OUTPUT_IMAGE, dpi=300, bbox_inches="tight")
    print(f"Chart successfully saved as '{OUTPUT_IMAGE}'.")


if __name__ == "__main__":
    plot_benchmark_results()