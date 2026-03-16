# simulation_engine.py

**Location:** `src/simulation_engine.py`

## Purpose

SimPy-based discrete event simulation engine that processes P6 schedule activities in dependency order, respecting resource constraints, relationship types (FS/FF/SS/SF with lag), and calendar-aware scheduling. Supports deterministic and stochastic (Monte Carlo) duration modeling.

## Dataclasses

### ResourcePool

| Field | Type | Description |
|-------|------|-------------|
| `rsrc_id` | `int` | Resource identifier |
| `name` | `str` | Resource name |
| `capacity` | `float` | Maximum concurrent units |

### ActivityResult

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `int` | Activity identifier |
| `task_code` | `str` | User-visible code |
| `task_name` | `str` | Description |
| `planned_duration_hours` | `float` | Original planned duration |
| `simulated_duration_hours` | `float` | Duration used in this run |
| `sim_start` | `float` | Start time (hours from epoch) |
| `sim_finish` | `float` | Finish time (hours from epoch) |
| `calendar_start` | `datetime` | Calendar start datetime |
| `calendar_finish` | `datetime` | Calendar finish datetime |
| `wait_hours` | `float` | Hours waiting for resources |
| `is_critical` | `bool` | On the critical path? |

### SimulationResult

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `int` | Run identifier (0-based) |
| `activity_results` | `dict[int, ActivityResult]` | Results keyed by task_id |
| `project_duration_hours` | `float` | Total project duration |
| `project_start` | `datetime` | Calendar start |
| `project_finish` | `datetime` | Calendar finish |

**Method:** `to_dataframe() → pd.DataFrame` — converts all results to a DataFrame.

## Duration Samplers

Pluggable functions with signature `(planned_hours, rng) → simulated_hours`:

| Function | Description |
|----------|-------------|
| `deterministic_sampler` | Returns planned duration unchanged. |
| `triangular_sampler(opt, mode, pess)` | Triangular distribution. Default: 0.8/1.0/1.5. |
| `pert_sampler(opt, mode, pess, lambda)` | PERT Beta distribution. Default: 0.8/1.0/1.5/4.0. |

## Class: SimulationEngine

### Constructor

```python
SimulationEngine(
    parser: XERParser,
    project_start: datetime | None = None,    # Auto-inferred if None
    duration_sampler: DurationSampler = None,  # Defaults to deterministic
    seed: int | None = None,                   # For reproducible Monte Carlo
    resource_constrained: bool = True,         # Enforce resource limits
)
```

### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `run` | `(run_id=0) → SimulationResult` | Execute a single simulation run. |
| `run_monte_carlo` | `(num_runs=100) → list[SimulationResult]` | Execute multiple runs. |
| `summary` | `(result) → str` | Print single-run summary. |
| `monte_carlo_summary` | `(results) → str` | Print percentile statistics (P10/P50/P80/P90). |

### Properties

| Property | Returns | Description |
|----------|---------|-------------|
| `network` | `ActivityNetwork` | The dependency network. |
| `calendar` | `CalendarEngine` | The calendar engine. |
| `project_start` | `datetime` | Simulation start date. |

### How the Simulation Works

1. Activities are sorted in **topological order**.
2. Each activity runs as a **SimPy process** that:
   - Waits for predecessor constraints (start events for SS/SF, completion events for FS/FF).
   - Applies lag delays based on relationship type.
   - Acquires required **SimPy Resources** (if resource-constrained).
   - Executes for the sampled duration via `env.timeout()`.
   - Releases resources and signals completion.
3. Calendar datetimes are computed by mapping simulation hours through the `CalendarEngine`.

### Usage

```python
from src.xer_parser import XERParser
from src.simulation_engine import SimulationEngine, triangular_sampler

parser = XERParser("data/sample-5272.xer")

# Deterministic run
engine = SimulationEngine(parser, resource_constrained=False)
result = engine.run()
engine.summary(result)

# Monte Carlo with triangular durations
mc_engine = SimulationEngine(
    parser,
    duration_sampler=triangular_sampler(0.8, 1.0, 1.5),
    seed=42,
    resource_constrained=False,
)
results = mc_engine.run_monte_carlo(num_runs=50)
mc_engine.monte_carlo_summary(results)
```

## Tests

See `tests/test_simulation_engine.py` — 38 tests covering linear chains, parallel paths, resource contention, milestones, FS lag, SS relationships, calendar integration, duration samplers, Monte Carlo reproducibility, summary output, and real XER data.
