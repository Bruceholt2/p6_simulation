"""Run the P6 schedule discrete event simulation.

Usage:
    python run_simulation.py [path_to_xer_file]

If no file is specified, defaults to data/sample-5272.xer.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from src.xer_parser import XERParser
from src.activity_network import ActivityNetwork
from src.calendar_engine import CalendarEngine
from src.simulation_engine import SimulationEngine, triangular_sampler
from src.visualization import (
    gantt_chart,
    duration_histogram,
    s_curve,
    criticality_index,
)


def save_results_csv(result: "SimulationResult", filepath: Path) -> None:
    """Export simulation results to CSV with datetime and hour columns."""
    df = result.to_dataframe()

    # Reorder columns for readability
    col_order = [
        "task_id",
        "proj_id",
        "task_code",
        "task_name",
        "planned_duration_hours",
        "simulated_duration_hours",
        "sim_start_date",
        "sim_finish_date",
        "sim_start_time",
        "sim_finish_time",
        "wait_hours",
        "is_critical",
    ]
    col_order = [c for c in col_order if c in df.columns]
    df = df[col_order]

    df.to_csv(filepath, index=False)


def main(xer_path: str = "data/sample-5272.xer") -> None:
    """Run the full simulation pipeline."""
    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)

    # --- 1. Parse the XER file ---
    print("=" * 60)
    print("STEP 1: Parsing XER file")
    print("=" * 60)
    parser = XERParser(xer_path)
    parser.summary()

    # --- 2. Build the activity network ---
    print()
    print("=" * 60)
    print("STEP 2: Building activity network")
    print("=" * 60)
    network = ActivityNetwork(parser)
    network.summary()

    # --- 3. Load calendars ---
    print()
    print("=" * 60)
    print("STEP 3: Loading calendars")
    print("=" * 60)
    calendar = CalendarEngine(parser)
    calendar.summary()

    # --- 4. Deterministic simulation (single run) ---
    print()
    print("=" * 60)
    print("STEP 4: Deterministic simulation (single run)")
    print("=" * 60)
    engine = SimulationEngine(parser, resource_constrained=False)
    result = engine.run()
    engine.summary(result)

    # Save CSV
    save_results_csv(result, results_dir / "deterministic_results.csv")
    print(f"\n  Saved: {results_dir / 'deterministic_results.csv'}")

    # Save Gantt chart
    gantt_chart(result, top_n=40, save_path=results_dir / "gantt_deterministic.png")
    print(f"  Saved: {results_dir / 'gantt_deterministic.png'}")

    # Save S-curve
    s_curve(result, save_path=results_dir / "scurve_deterministic.png")
    print(f"  Saved: {results_dir / 'scurve_deterministic.png'}")

    # --- 5. Monte Carlo simulation ---
    num_runs = 50
    print()
    print("=" * 60)
    print(f"STEP 5: Monte Carlo simulation ({num_runs} runs)")
    print("=" * 60)
    mc_engine = SimulationEngine(
        parser,
        duration_sampler=triangular_sampler(0.8, 1.0, 1.5),
        seed=42,
        resource_constrained=False,
    )
    mc_results = mc_engine.run_monte_carlo(num_runs=num_runs)
    mc_engine.monte_carlo_summary(mc_results)

    # Save duration histogram
    duration_histogram(mc_results, save_path=results_dir / "histogram.png")
    print(f"\n  Saved: {results_dir / 'histogram.png'}")

    # Save criticality index
    criticality_index(mc_results, top_n=30, save_path=results_dir / "criticality.png")
    print(f"  Saved: {results_dir / 'criticality.png'}")

    # --- 6. Resource-constrained simulation ---
    print()
    print("=" * 60)
    print("STEP 6: Resource-constrained simulation (single run)")
    print("=" * 60)
    rc_engine = SimulationEngine(parser, resource_constrained=True)
    rc_result = rc_engine.run()
    rc_engine.summary(rc_result)

    # Save CSV
    save_results_csv(rc_result, results_dir / "resource_constrained_results.csv")
    print(f"\n  Saved: {results_dir / 'resource_constrained_results.csv'}")

    gantt_chart(
        rc_result, top_n=40,
        title="Resource-Constrained Gantt Chart",
        save_path=results_dir / "gantt_resource_constrained.png",
    )
    print(f"  Saved: {results_dir / 'gantt_resource_constrained.png'}")

    # --- Done ---
    print()
    print("=" * 60)
    print("COMPLETE — All outputs saved to results/")
    print("=" * 60)
    print()
    for f in sorted(results_dir.glob("*.png")) + sorted(results_dir.glob("*.csv")):
        print(f"  {f}")


if __name__ == "__main__":
    xer_file = sys.argv[1] if len(sys.argv) > 1 else "data/sample-5272.xer"
    main(xer_file)
