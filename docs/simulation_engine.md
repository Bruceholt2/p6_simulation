# simulation_engine.py

**Location:** `src/simulation_engine.py`

## Purpose

Discrete event simulation engine that processes P6 schedule activities in dependency order, respecting resource constraints, relationship types (FS/FF/SS/SF with lag), and calendar-aware scheduling. Supports deterministic and stochastic (Monte Carlo) duration modeling.

### Performance Optimizations

- **Fast-path direct traversal** (`_run_fast`) for non-resource-constrained runs -- no SimPy overhead.
- **Cached topological order** reused across all Monte Carlo runs.
- **Deferred calendar conversion** -- sim hours are not converted to calendar datetimes during Monte Carlo runs by default; only converted on demand.
- **Remaining duration sampling** -- uses `remaining_duration_hours` (not `original_duration_hours`) so in-progress schedules are modeled correctly.

## Dataclasses

### ResourcePool

| Field | Type | Description |
|-------|------|-------------|
| `rsrc_id` | `int` | Resource identifier |
| `name` | `str` | Resource name |
| `capacity` | `float` | Maximum concurrent units |
| `resource` | `simpy.Resource \| None` | SimPy Resource object (set during simulation) |

### ActivityResult

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `int` | Activity identifier |
| `proj_id` | `int` | Project identifier (from TASK table's proj_id column) |
| `task_code` | `str` | User-visible code |
| `task_name` | `str` | Description |
| `planned_duration_hours` | `float` | Remaining planned duration (used as input to sampler) |
| `simulated_duration_hours` | `float` | Duration used in this run |
| `sim_start_time` | `int` | Start time in integer hours from simulation epoch |
| `sim_finish_time` | `int` | Finish time in integer hours from simulation epoch |
| `sim_start_date` | `datetime \| None` | Calendar datetime when activity started (populated when `convert_calendar=True`) |
| `sim_finish_date` | `datetime \| None` | Calendar datetime when activity finished (populated when `convert_calendar=True`) |
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

**Method:** `to_dataframe() -> pd.DataFrame` -- converts all results to a DataFrame with columns: `task_id`, `proj_id`, `task_code`, `task_name`, `planned_duration_hours`, `simulated_duration_hours`, `sim_start_date`, `sim_finish_date`, `sim_start_time`, `sim_finish_time`, `wait_hours`, `is_critical`.

## Duration Samplers

Pluggable functions with signature `(planned_hours, rng) -> simulated_hours`:

| Function | Description |
|----------|-------------|
| `deterministic_sampler` | Returns planned duration unchanged. |
| `triangular_sampler(opt, mode, pess)` | Triangular distribution. Default: 0.8/1.0/1.5. |
| `pert_sampler(opt, mode, pess, lambda)` | PERT Beta distribution. Default: 0.8/1.0/1.5/4.0. |

## Class: SimulationEngine

### Constructor

```python
SimulationEngine(
    parser: XERParser,                         # Also accepts PortfolioLoader
    project_start: datetime | None = None,     # Auto-inferred if None
    duration_sampler: DurationSampler = None,   # Defaults to deterministic
    seed: int | None = None,                    # For reproducible Monte Carlo
    resource_constrained: bool = True,          # Enforce resource limits
)
```

On construction the engine:
1. Builds an `ActivityNetwork` from the parser.
2. Builds a `CalendarEngine` from the parser.
3. Constructs a `task_id -> proj_id` lookup from the TASK table.
4. Builds resource pools and assignments (if `resource_constrained=True`).
5. Caches the topological order for reuse across runs.

### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `run` | `(run_id=0, *, convert_calendar=True) -> SimulationResult` | Execute a single simulation run. When `convert_calendar=False`, skips the expensive calendar datetime conversion. |
| `run_monte_carlo` | `(num_runs=100, *, convert_calendar=False) -> list[SimulationResult]` | Execute multiple runs. Defaults `convert_calendar=False` for performance. |
| `summary` | `(result) -> str` | Print single-run summary. |
| `monte_carlo_summary` | `(results) -> str` | Print percentile statistics (P10/P50/P80/P90). |

### Properties

| Property | Returns | Description |
|----------|---------|-------------|
| `network` | `ActivityNetwork` | The dependency network. |
| `calendar` | `CalendarEngine` | The calendar engine. |
| `project_start` | `datetime` | Simulation start date. |

### How the Simulation Works

The engine provides two execution paths selected automatically:

#### Fast Path (`_run_fast`) -- non-resource-constrained

1. Activities are traversed in **cached topological order**.
2. For each activity, the earliest start is computed as `max()` over all predecessor constraints (FS, FF, SS, SF with lag).
3. Duration is sampled from `remaining_duration_hours` using the configured sampler.
4. Start/finish times are stored as integer hours. No SimPy overhead.

#### SimPy Path (`_run_simpy`) -- resource-constrained

1. Activities are sorted in **cached topological order**.
2. Each activity runs as a **SimPy process** that:
   - Waits for predecessor constraints (start events for SS/SF, completion events for FS/FF).
   - Applies lag delays based on relationship type.
   - Acquires required **SimPy Resources** (if resource-constrained).
   - Executes for the sampled duration via `env.timeout()`.
   - Releases resources and signals completion.
3. Duration is sampled from `remaining_duration_hours`.

#### Calendar Conversion (deferred)

Calendar datetimes (`sim_start_date`, `sim_finish_date`) are computed by `_convert_calendar_dates()` only when `convert_calendar=True`. This maps simulation hours through the `CalendarEngine` for each activity's assigned calendar.

### Usage

```python
from src.xer_parser import XERParser
from src.simulation_engine import SimulationEngine, triangular_sampler

parser = XERParser("data/sample-5272.xer")

# Deterministic run (with calendar dates)
engine = SimulationEngine(parser, resource_constrained=False)
result = engine.run()  # convert_calendar=True by default
engine.summary(result)

# Monte Carlo with triangular durations (no calendar conversion for speed)
mc_engine = SimulationEngine(
    parser,
    duration_sampler=triangular_sampler(0.8, 1.0, 1.5),
    seed=42,
    resource_constrained=False,
)
results = mc_engine.run_monte_carlo(num_runs=50)  # convert_calendar=False by default
mc_engine.monte_carlo_summary(results)
```

## Tests

See `tests/test_simulation_engine.py` -- tests covering linear chains, parallel paths, resource contention, milestones, FS lag, SS relationships, calendar integration, duration samplers, Monte Carlo reproducibility, summary output, and real XER data.
