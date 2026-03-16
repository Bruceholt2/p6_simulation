# run_simulation.py

**Location:** `run_simulation.py` (project root)

## Purpose

Main entry point that runs the full P6 schedule simulation pipeline end-to-end. Parses an XER file, builds the activity network, runs deterministic and Monte Carlo simulations, and generates all visualization charts.

## Usage

```bash
# Default — uses data/sample-5272.xer
python run_simulation.py

# Custom XER file
python run_simulation.py path/to/schedule.xer
```

## Pipeline Steps

| Step | Description | Output |
|------|-------------|--------|
| 1. Parse XER | Reads the XER file into DataFrames | Summary of tables parsed |
| 2. Build Network | Constructs activity dependency graph | Network statistics |
| 3. Load Calendars | Parses calendar definitions | Calendar work patterns |
| 4. Deterministic Run | Single simulation with planned durations | `gantt_deterministic.png`, `scurve_deterministic.png` |
| 5. Monte Carlo | 50 runs with triangular distribution (80%/100%/150%) | `histogram.png`, `criticality.png` |
| 6. Resource-Constrained | Single run enforcing resource capacity | `gantt_resource_constrained.png` |

## Output Files

All charts are saved to the `results/` directory:

| File | Chart Type | Description |
|------|-----------|-------------|
| `gantt_deterministic.png` | Gantt Chart | Top 40 activities, critical path highlighted |
| `scurve_deterministic.png` | S-Curve | Cumulative work hours over time |
| `histogram.png` | Histogram | Monte Carlo duration distribution with P10/P50/P80/P90 |
| `criticality.png` | Criticality Index | Top 30 most-critical activities across MC runs |
| `gantt_resource_constrained.png` | Gantt Chart | Resource-constrained schedule |

## Configuration

To adjust simulation parameters, edit the following in `run_simulation.py`:

- **`num_runs`** (line 73): Number of Monte Carlo iterations (default: 50).
- **`triangular_sampler(0.8, 1.0, 1.5)`** (line 80): Duration uncertainty factors (optimistic, most likely, pessimistic).
- **`seed=42`** (line 82): Random seed for reproducibility.
- **`top_n=40`** (lines 65, 104): Number of activities shown in Gantt charts.
