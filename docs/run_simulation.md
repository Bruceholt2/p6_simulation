# run_simulation.py

**Location:** `run_simulation.py` (project root)

## Purpose

Main entry point that runs the full P6 schedule simulation pipeline end-to-end. Loads all XER files from a data directory using `PortfolioLoader`, merges them into a single portfolio, builds the activity network, runs deterministic and Monte Carlo simulations, and generates all visualization charts.

## Usage

```bash
# Default -- loads all XER files from data/
python run_simulation.py

# Custom data directory
python run_simulation.py path/to/xer_directory
```

## Pipeline Steps

| Step | Description | Output |
|------|-------------|--------|
| 1. Load Portfolio | Reads all XER files from the data directory via `PortfolioLoader` and merges like-named tables | Summary of files loaded and merged table counts |
| 2. Build Network | Constructs activity dependency graph from the merged portfolio | Network statistics |
| 3. Load Calendars | Parses calendar definitions from the merged portfolio | Calendar work patterns |
| 4. Deterministic Run | Single simulation with planned durations (`resource_constrained=False`) | `deterministic_results.csv`, `gantt_deterministic.png`, `scurve_deterministic.png` |
| 5. Monte Carlo | 50 runs with triangular distribution (80%/100%/150%), `resource_constrained=False` | `histogram.png`, `criticality.png` |
| 6. Resource-Constrained | Single run enforcing resource capacity | `resource_constrained_results.csv`, `gantt_resource_constrained.png` |

## Helper Function

### save_results_csv

```python
save_results_csv(result: SimulationResult, filepath: Path) -> None
```

Exports simulation results to CSV with columns ordered for readability:

| Column | Description |
|--------|-------------|
| `task_id` | Activity identifier |
| `proj_id` | Project identifier |
| `task_code` | User-visible activity code |
| `task_name` | Activity description |
| `planned_duration_hours` | Remaining planned duration |
| `simulated_duration_hours` | Duration used in this run |
| `sim_start_date` | Calendar start datetime |
| `sim_finish_date` | Calendar finish datetime |
| `sim_start_time` | Start time in integer hours from simulation epoch |
| `sim_finish_time` | Finish time in integer hours from simulation epoch |
| `wait_hours` | Hours waiting for resources |
| `is_critical` | On the critical path? |

## Output Files

All outputs are saved to the `results/` directory:

| File | Chart Type | Description |
|------|-----------|-------------|
| `deterministic_results.csv` | CSV | Activity-level results with proj_id, dates, and hours |
| `gantt_deterministic.png` | Gantt Chart | Top 40 activities, critical path highlighted |
| `scurve_deterministic.png` | S-Curve | Cumulative work hours over time |
| `histogram.png` | Histogram | Monte Carlo duration distribution with P10/P50/P80/P90 |
| `criticality.png` | Criticality Index | Top 30 most-critical activities across MC runs |
| `resource_constrained_results.csv` | CSV | Resource-constrained activity-level results |
| `gantt_resource_constrained.png` | Gantt Chart | Resource-constrained schedule |

## Configuration

To adjust simulation parameters, edit the following in `run_simulation.py`:

- **`num_runs`**: Number of Monte Carlo iterations (default: 50).
- **`triangular_sampler(0.8, 1.0, 1.5)`**: Duration uncertainty factors (optimistic, most likely, pessimistic).
- **`seed=42`**: Random seed for reproducibility.
- **`top_n=40`**: Number of activities shown in Gantt charts.
- **`data_dir`**: Command-line argument or default `"data"` for the XER file directory.
