# visualization.py

**Location:** `src/visualization.py`

## Purpose

Generates publication-quality charts from simulation results using matplotlib. All functions return a `plt.Figure` object and optionally save to a file.

## Functions

### gantt_chart

```python
gantt_chart(
    result: SimulationResult,
    top_n: int = 50,            # Max activities to show (longest first)
    show_critical: bool = True, # Highlight critical path in red
    use_calendar_dates: bool = True,  # Calendar dates vs sim hours on x-axis
    title: str = "...",
    figsize: tuple = (14, 8),
    save_path: str | Path = None,
) → plt.Figure
```

Horizontal bar chart of activity durations. Critical activities in red, non-critical in blue. Resource wait time shown in orange (sim-hours mode only).

### duration_histogram

```python
duration_histogram(
    results: list[SimulationResult],
    bins: int = 30,
    percentiles: list[float] = [10, 50, 80, 90],
    title: str = "...",
    figsize: tuple = (10, 6),
    save_path: str | Path = None,
) → plt.Figure
```

Histogram of project durations from Monte Carlo runs. Vertical lines mark percentiles (color-coded) and the mean (black).

### s_curve

```python
s_curve(
    result: SimulationResult,
    num_points: int = 200,
    title: str = "...",
    figsize: tuple = (10, 6),
    save_path: str | Path = None,
) → plt.Figure
```

Cumulative work hours over simulation time. Shows proportional completion for in-progress activities. Horizontal reference line at total work hours.

### resource_utilization

```python
resource_utilization(
    result: SimulationResult,
    resource_assignments: dict[int, list[int]],  # task_id → [rsrc_id]
    resource_names: dict[int, str],               # rsrc_id → name
    num_points: int = 200,
    title: str = "...",
    figsize: tuple = (12, 6),
    save_path: str | Path = None,
) → plt.Figure
```

Stacked area chart showing concurrent resource units over the project timeline. One colored band per resource.

### criticality_index

```python
criticality_index(
    results: list[SimulationResult],
    top_n: int = 30,
    title: str = "...",
    figsize: tuple = (10, 8),
    save_path: str | Path = None,
) → plt.Figure
```

Horizontal bar chart showing what percentage of Monte Carlo runs each activity was on the critical path. Color-coded: red (>=80%), orange (>=50%), blue (<50%).

## Usage

```python
from src.simulation_engine import SimulationEngine, triangular_sampler
from src.visualization import gantt_chart, duration_histogram, s_curve, criticality_index

# Single run charts
result = engine.run()
gantt_chart(result, top_n=30, save_path="results/gantt.png")
s_curve(result, save_path="results/scurve.png")

# Monte Carlo charts
results = engine.run_monte_carlo(num_runs=50)
duration_histogram(results, save_path="results/histogram.png")
criticality_index(results, save_path="results/criticality.png")
```

## Tests

See `tests/test_visualization.py` — 26 tests covering figure creation, bar counts, top_n limiting, file save, S-curve monotonicity, empty/edge cases, and real XER data integration.
