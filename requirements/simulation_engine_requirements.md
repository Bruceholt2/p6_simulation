# Simulation Engine Requirements Document

**Module:** `src/simulation_engine.py`
**Last Updated:** 2026-03-16

---

## 1. Module Overview

The `simulation_engine` module is the core of the P6 schedule simulation system. It implements a SimPy-based discrete event simulation that processes activities in dependency order, respecting resource constraints and calendar-aware durations. The engine supports both deterministic and stochastic (Monte Carlo) duration modeling, with two execution paths: a fast direct-traversal path for non-resource-constrained runs, and a full SimPy simulation path for resource-constrained runs.

---

## 2. Functional Requirements

### Data Structures

| ID | Requirement |
|----|-------------|
| FR-SIM-001 | The `ResourcePool` dataclass SHALL store `rsrc_id` (int), `name` (str), `capacity` (float), and an optional `resource` (SimPy Resource object, set during simulation). |
| FR-SIM-002 | The `ActivityResult` dataclass SHALL store per-activity simulation results: `task_id`, `proj_id`, `task_code`, `task_name`, `planned_duration_hours`, `simulated_duration_hours`, `sim_start_time` (int hours), `sim_finish_time` (int hours), `sim_start_date` (datetime or None), `sim_finish_date` (datetime or None), `wait_hours` (float, default 0.0), and `is_critical` (bool, default False). |
| FR-SIM-003 | The `SimulationResult` dataclass SHALL store `run_id` (int), `activity_results` (dict of task_id to ActivityResult), `project_duration_hours` (float), `project_start` (datetime or None), and `project_finish` (datetime or None). |
| FR-SIM-004 | `SimulationResult.to_dataframe()` SHALL convert all activity results to a pandas DataFrame with columns: `task_id`, `proj_id`, `task_code`, `task_name`, `planned_duration_hours`, `simulated_duration_hours`, `sim_start_date`, `sim_finish_date`, `sim_start_time`, `sim_finish_time`, `wait_hours`, `is_critical`. |

### Duration Samplers

| ID | Requirement |
|----|-------------|
| FR-SIM-005 | The `DurationSampler` type alias SHALL be defined as `Callable[[float, np.random.Generator], float]`, taking planned hours and an RNG and returning simulated hours. |
| FR-SIM-006 | `deterministic_sampler` SHALL return the planned duration unchanged, ignoring the RNG. |
| FR-SIM-007 | `triangular_sampler(optimistic_factor, most_likely_factor, pessimistic_factor)` SHALL return a `DurationSampler` that samples from a triangular distribution with parameters `low = planned * optimistic_factor`, `mode = planned * most_likely_factor`, `high = planned * pessimistic_factor`. If planned hours is zero or negative, it SHALL return 0.0. Default factors: 0.8, 1.0, 1.5. |
| FR-SIM-008 | `pert_sampler(optimistic_factor, most_likely_factor, pessimistic_factor, lambd)` SHALL return a `DurationSampler` that samples from a PERT (Beta) distribution. The mean is computed as `(a + lambd * m + b) / (lambd + 2)`. Alpha and beta parameters are derived from the PERT formula. If the range `(b - a)` is less than `1e-9`, it SHALL return the mode. Invalid alpha or beta values (<=0) SHALL be clamped to 1.0. Default lambda: 4.0. |

### Earliest Start Computation

| ID | Requirement |
|----|-------------|
| FR-SIM-009 | `_compute_earliest_start` SHALL compute the earliest start for a successor based on one relationship, implementing all four relationship types: FS (pred_finish + lag), SS (pred_start + lag), FF (pred_finish + lag - successor_duration), SF (pred_start + lag - successor_duration). Unknown types default to FS behavior. |

### SimulationEngine Class

| ID | Requirement |
|----|-------------|
| FR-SIM-010 | The `SimulationEngine` class SHALL accept an `XERParser` (or compatible), optional `project_start` datetime, optional `duration_sampler`, optional `seed`, and `resource_constrained` flag (default True). |
| FR-SIM-011 | If `project_start` is not provided, the engine SHALL infer it from the earliest `early_start_date` in the TASK table. If no valid dates exist, it SHALL default to `2025-01-01 08:00`. |
| FR-SIM-012 | The engine SHALL build a `task_id` to `proj_id` lookup from the TASK table's `proj_id` column (if present). |
| FR-SIM-013 | If `resource_constrained` is True, the engine SHALL build resource pools from the RSRC and RSRCRATE tables, and build task-to-resource assignment mappings from the TASKRSRC table. |
| FR-SIM-014 | Resource pool capacity SHALL be derived from the `max_qty_per_hr` column in RSRCRATE. If multiple rates exist for a resource, the maximum capacity is used. Default capacity is 1.0. Capacity is converted to integer (minimum 1) for SimPy Resource. |
| FR-SIM-015 | The engine SHALL cache the topological order of activities at construction time for reuse across Monte Carlo runs. |

### Fast Path (Non-Resource-Constrained)

| ID | Requirement |
|----|-------------|
| FR-SIM-016 | `_run_fast(run_id)` SHALL implement a direct traversal of the topological order without SimPy overhead for non-resource-constrained runs. |
| FR-SIM-017 | For each activity in topological order, `_run_fast` SHALL compute the earliest start as the maximum of all predecessor constraints using `_compute_earliest_start`. |
| FR-SIM-018 | Duration SHALL be sampled using the configured `_duration_sampler` with `remaining_duration_hours` as input. Milestones SHALL always have zero duration. |
| FR-SIM-019 | The RNG for each run SHALL be seeded with `self._seed + run_id` if a seed is set, otherwise `None` (random). |
| FR-SIM-020 | `sim_start_time` and `sim_finish_time` SHALL be stored as integer values (truncated from float). |
| FR-SIM-021 | Project duration SHALL be the maximum `sim_finish_time` across all activities. |

### SimPy Path (Resource-Constrained)

| ID | Requirement |
|----|-------------|
| FR-SIM-022 | `_run_simpy(run_id)` SHALL create a SimPy Environment and SimPy Resource objects for each resource pool. |
| FR-SIM-023 | Each activity SHALL be modeled as a SimPy process that: (a) waits for predecessor events based on relationship type (start events for SS/SF, completion events for FS/FF), (b) applies lag delays, (c) acquires all assigned resources, (d) runs for the sampled duration, (e) releases resources, and (f) records results. |
| FR-SIM-024 | Wait hours SHALL be calculated as the difference between resource acquisition completion time and the time resource requests began. |
| FR-SIM-025 | Start events and completion events SHALL be created for each activity to coordinate predecessor/successor dependencies. |

### Run Methods

| ID | Requirement |
|----|-------------|
| FR-SIM-026 | `run(run_id, convert_calendar)` SHALL execute a single simulation run using the fast path or SimPy path based on `_resource_constrained`. If `convert_calendar` is True, it SHALL convert simulation hours to calendar datetimes post-simulation. |
| FR-SIM-027 | `_convert_calendar_dates` SHALL convert all activity `sim_start_time` and `sim_finish_time` values to calendar datetimes using the CalendarEngine, looking up each activity's assigned calendar. |
| FR-SIM-028 | After calendar conversion, `project_finish` SHALL be set to the `sim_finish_date` of the activity with the latest `sim_finish_time`. |
| FR-SIM-029 | `run_monte_carlo(num_runs, convert_calendar)` SHALL execute `num_runs` sequential simulation runs and return a list of `SimulationResult` objects. Default `convert_calendar` is False for performance. |

### Summary Methods

| ID | Requirement |
|----|-------------|
| FR-SIM-030 | `summary(result)` SHALL return and print a multi-line string with: run ID, project start/finish, duration in hours, activity count, critical activity count. If resource-constrained, it SHALL also show number of delayed activities, total wait hours, and max wait hours. |
| FR-SIM-031 | `monte_carlo_summary(results)` SHALL return and print a multi-line string with: run count, mean/std/min/P10/P50/P80/P90/max duration statistics computed from project_duration_hours across all runs. |

---

## 3. Input Requirements

| Input | Format | Validation |
|-------|--------|------------|
| `parser` | `XERParser` or compatible | Must provide `tasks`, `predecessors`, `calendars`, `resources`, `resource_assignments` DataFrames. |
| `project_start` | `datetime` or `None` | Optional. Inferred from data if not provided. |
| `duration_sampler` | `DurationSampler` callable or `None` | Optional. Defaults to `deterministic_sampler`. |
| `seed` | `int` or `None` | Optional. If None, runs are non-reproducible. |
| `resource_constrained` | `bool` | Default True. Controls execution path. |
| `num_runs` | `int` | For Monte Carlo. Default 100. |
| `convert_calendar` | `bool` | Controls calendar date conversion. |

---

## 4. Output Requirements

| Output | Type | Description |
|--------|------|-------------|
| `run()` return | `SimulationResult` | Single run results with activity-level timing data. |
| `run_monte_carlo()` return | `list[SimulationResult]` | List of results, one per run. |
| `SimulationResult.to_dataframe()` | `pd.DataFrame` | Tabular activity results. |
| `summary()` return | `str` | Run summary (also printed). |
| `monte_carlo_summary()` return | `str` | Statistical summary (also printed). |

---

## 5. Data Requirements

### ResourcePool Fields
| Field | Type | Description |
|-------|------|-------------|
| `rsrc_id` | `int` | Unique resource identifier |
| `name` | `str` | Resource name |
| `capacity` | `float` | Max units per hour |
| `resource` | `simpy.Resource | None` | SimPy resource (set during sim) |

### ActivityResult Fields
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task_id` | `int` | Required | Activity identifier |
| `proj_id` | `int` | Required | Project identifier |
| `task_code` | `str` | Required | User-visible code |
| `task_name` | `str` | Required | Activity description |
| `planned_duration_hours` | `float` | Required | Remaining duration (input) |
| `simulated_duration_hours` | `float` | Required | Sampled duration (output) |
| `sim_start_time` | `int` | Required | Start in sim hours |
| `sim_finish_time` | `int` | Required | Finish in sim hours |
| `sim_start_date` | `datetime | None` | `None` | Calendar start (post-conversion) |
| `sim_finish_date` | `datetime | None` | `None` | Calendar finish (post-conversion) |
| `wait_hours` | `float` | `0.0` | Resource wait time |
| `is_critical` | `bool` | `False` | On critical path |

---

## 6. Interface Requirements

### Dependencies (imports)
- `os` -- imported but not used directly in visible code
- `concurrent.futures.ProcessPoolExecutor` -- imported but not used in current implementation (reserved for parallel Monte Carlo)
- `numpy` -- random number generation (`np.random.default_rng`, `np.random.Generator`), array operations, percentile calculations
- `pandas` -- DataFrame construction
- `simpy` -- discrete event simulation (Environment, Resource, Event, Process)
- `src.activity_network` -- `Activity`, `ActivityNetwork`, `RelationshipType`, `StatusCode`, `TaskType`
- `src.calendar_engine` -- `CalendarEngine`
- `src.xer_parser` -- `XERParser`

### Dependents (modules that import this module)
- `run_simulation.py` -- imports `SimulationEngine`, `triangular_sampler`
- `src.visualization` -- imports `ActivityResult`, `SimulationResult`

### Exposed API
- `network` property -- provides access to the underlying `ActivityNetwork`
- `calendar` property -- provides access to the underlying `CalendarEngine`
- `project_start` property -- the project start datetime

---

## 7. Performance Requirements

| ID | Requirement |
|----|-------------|
| PR-SIM-001 | Non-resource-constrained runs use a fast-path direct traversal (`_run_fast`) that avoids SimPy process creation overhead. |
| PR-SIM-002 | Topological order is cached at construction time and reused across all Monte Carlo runs. |
| PR-SIM-003 | Calendar date conversion is deferred (only performed when `convert_calendar=True`). For Monte Carlo, the default is `False` to avoid expensive calendar computations on every run. |
| PR-SIM-004 | `ProcessPoolExecutor` is imported for potential parallel Monte Carlo execution, though the current implementation runs sequentially. |
| PR-SIM-005 | The `_proj_ids` dictionary is built once at construction for O(1) lookup per activity. |
| PR-SIM-006 | Resource pool capacity lookup from RSRCRATE is pre-computed once at construction. |

---

## 8. Error Handling Requirements

| ID | Condition | Behavior |
|----|-----------|----------|
| EH-SIM-001 | RSRCRATE table not found | Empty DataFrame used; resources get default capacity of 1.0. |
| EH-SIM-002 | `max_qty_per_hr` missing or null | Default capacity of 1 used. |
| EH-SIM-003 | No valid `early_start_date` values | Project start defaults to `2025-01-01 08:00`. |
| EH-SIM-004 | `proj_id` column not in TASK table | `_proj_ids` dictionary remains empty; activities get proj_id 0. |
| EH-SIM-005 | Activity has no calendar assigned (`calendar_id` is None) | Calendar ID -1 (default calendar) is used for conversion. |
| EH-SIM-006 | Zero or negative planned duration for PERT sampler | Returns 0.0 (triangular) or mode value (PERT with zero range). |
| EH-SIM-007 | PERT alpha or beta parameter <= 0 | Clamped to 1.0. |
| EH-SIM-008 | Resource not found in resource pools during assignment building | Assignment silently skipped. |

---

## 9. Constraints and Assumptions

| ID | Constraint/Assumption |
|----|----------------------|
| CA-SIM-001 | Simulation operates in work-hours space; calendar conversion happens post-simulation. |
| CA-SIM-002 | Activities are simulated using `remaining_duration_hours`, not original duration, to support in-progress schedules. |
| CA-SIM-003 | Milestones always have zero simulated duration regardless of sampler output. |
| CA-SIM-004 | `sim_start_time` and `sim_finish_time` are truncated to integers (hours). |
| CA-SIM-005 | SimPy Resource capacity must be a positive integer (minimum 1). |
| CA-SIM-006 | Monte Carlo runs are sequential (not parallel) in the current implementation despite importing `ProcessPoolExecutor`. |
| CA-SIM-007 | Each Monte Carlo run uses a deterministic seed of `base_seed + run_id` for reproducibility. |
| CA-SIM-008 | The fast path sets `wait_hours` to 0.0 for all activities since there are no resource constraints. |
| CA-SIM-009 | In the SimPy path, resources are acquired sequentially (not simultaneously), which may introduce artificial delays if an activity requires multiple resources. |
| CA-SIM-010 | The PERT sampler uses the standard PERT formula with lambda=4 by default, deriving Beta distribution parameters from the three-point estimate. |
| CA-SIM-011 | The `is_critical` flag is taken from the original XER data's total float, not recomputed during simulation. |
