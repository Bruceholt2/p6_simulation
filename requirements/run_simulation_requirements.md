# Run Simulation Requirements Document

**Module:** `run_simulation.py`
**Last Updated:** 2026-03-16

---

## 1. Module Overview

The `run_simulation` module is the top-level entry point for the P6 schedule simulation system. It orchestrates the full pipeline: loading a portfolio of XER files, building the activity network, loading calendars, running deterministic and Monte Carlo simulations, running a resource-constrained simulation, generating visualizations, and saving all outputs to the `results/` directory. It is designed to be executed from the command line with an optional data directory argument.

---

## 2. Functional Requirements

### Command-Line Interface

| ID | Requirement |
|----|-------------|
| FR-RUN-001 | The module SHALL be executable as a script (`python run_simulation.py [data_directory]`). |
| FR-RUN-002 | If a command-line argument is provided, it SHALL be used as the data directory path. If no argument is provided, it SHALL default to `"data"`. |
| FR-RUN-003 | The entry point SHALL call `main(data_directory)`. |

### Output Directory

| ID | Requirement |
|----|-------------|
| FR-RUN-004 | The `main` function SHALL create a `results/` directory (relative to the working directory) if it does not exist, using `mkdir(exist_ok=True)`. |

### Step 1: Portfolio Loading

| ID | Requirement |
|----|-------------|
| FR-RUN-005 | The function SHALL create a `PortfolioLoader` with the specified data directory and print its summary. |
| FR-RUN-006 | Progress SHALL be indicated by printing a header "STEP 1: Loading XER portfolio" with separator lines. |

### Step 2: Activity Network

| ID | Requirement |
|----|-------------|
| FR-RUN-007 | The function SHALL create an `ActivityNetwork` from the portfolio and print its summary. |
| FR-RUN-008 | Progress SHALL be indicated by printing "STEP 2: Building activity network". |

### Step 3: Calendar Loading

| ID | Requirement |
|----|-------------|
| FR-RUN-009 | The function SHALL create a `CalendarEngine` from the portfolio and print its summary. |
| FR-RUN-010 | Progress SHALL be indicated by printing "STEP 3: Loading calendars". |

### Step 4: Deterministic Simulation

| ID | Requirement |
|----|-------------|
| FR-RUN-011 | The function SHALL create a `SimulationEngine` with `resource_constrained=False` and run a single deterministic simulation with calendar conversion enabled. |
| FR-RUN-012 | The function SHALL save the deterministic results as CSV to `results/deterministic_results.csv`. |
| FR-RUN-013 | The function SHALL generate and save a Gantt chart (top 40 activities) to `results/gantt_deterministic.png`. |
| FR-RUN-014 | The function SHALL generate and save an S-curve to `results/scurve_deterministic.png`. |
| FR-RUN-015 | Progress SHALL be indicated by printing "STEP 4: Deterministic simulation (single run)". |

### Step 5: Monte Carlo Simulation

| ID | Requirement |
|----|-------------|
| FR-RUN-016 | The function SHALL create a `SimulationEngine` with a triangular sampler (factors 0.8, 1.0, 1.5), seed 42, and `resource_constrained=False`. |
| FR-RUN-017 | The function SHALL execute 50 Monte Carlo runs using `run_monte_carlo`. |
| FR-RUN-018 | The function SHALL print the Monte Carlo summary statistics. |
| FR-RUN-019 | The function SHALL generate and save a duration histogram to `results/histogram.png`. |
| FR-RUN-020 | The function SHALL generate and save a criticality index chart (top 30 activities) to `results/criticality.png`. |
| FR-RUN-021 | Progress SHALL be indicated by printing "STEP 5: Monte Carlo simulation ({num_runs} runs)". |

### Step 6: Resource-Constrained Simulation

| ID | Requirement |
|----|-------------|
| FR-RUN-022 | The function SHALL create a `SimulationEngine` with `resource_constrained=True` and run a single simulation with calendar conversion. |
| FR-RUN-023 | The function SHALL save the resource-constrained results as CSV to `results/resource_constrained_results.csv`. |
| FR-RUN-024 | The function SHALL generate and save a resource-constrained Gantt chart (top 40 activities) to `results/gantt_resource_constrained.png`. |
| FR-RUN-025 | Progress SHALL be indicated by printing "STEP 6: Resource-constrained simulation (single run)". |

### Completion

| ID | Requirement |
|----|-------------|
| FR-RUN-026 | Upon completion, the function SHALL print "COMPLETE -- All outputs saved to results/" and list all PNG and CSV files in the results directory. |

### CSV Export (`save_results_csv`)

| ID | Requirement |
|----|-------------|
| FR-RUN-027 | `save_results_csv` SHALL convert a `SimulationResult` to a DataFrame, reorder columns in a specified order (`task_id`, `proj_id`, `task_code`, `task_name`, `planned_duration_hours`, `simulated_duration_hours`, `sim_start_date`, `sim_finish_date`, `sim_start_time`, `sim_finish_time`, `wait_hours`, `is_critical`), and save to CSV without index. |
| FR-RUN-028 | Column reordering SHALL only include columns that actually exist in the DataFrame (graceful handling of missing columns). |

---

## 3. Input Requirements

| Input | Format | Validation |
|-------|--------|------------|
| `data_dir` (CLI argument) | Directory path string | Passed directly to `PortfolioLoader`; validation happens there. |
| Default data directory | `"data"` | Relative to working directory. |
| XER files in data directory | P6 XER format files | Loaded by `PortfolioLoader` which delegates to `XERParser`. |

---

## 4. Output Requirements

### Files Generated

| File Path | Type | Description |
|-----------|------|-------------|
| `results/deterministic_results.csv` | CSV | Activity-level deterministic simulation results. |
| `results/gantt_deterministic.png` | PNG | Gantt chart of deterministic run (top 40 activities). |
| `results/scurve_deterministic.png` | PNG | S-curve of deterministic run. |
| `results/histogram.png` | PNG | Monte Carlo duration distribution histogram. |
| `results/criticality.png` | PNG | Activity criticality index chart (top 30). |
| `results/resource_constrained_results.csv` | CSV | Activity-level resource-constrained simulation results. |
| `results/gantt_resource_constrained.png` | PNG | Gantt chart of resource-constrained run (top 40 activities). |

### Console Output
- Step headers with `=` separator lines (60 characters wide)
- Summary outputs from each module (portfolio, network, calendar, simulation)
- File save confirmations
- Final file listing

---

## 5. Data Requirements

### CSV Column Order
1. `task_id`
2. `proj_id`
3. `task_code`
4. `task_name`
5. `planned_duration_hours`
6. `simulated_duration_hours`
7. `sim_start_date`
8. `sim_finish_date`
9. `sim_start_time`
10. `sim_finish_time`
11. `wait_hours`
12. `is_critical`

---

## 6. Interface Requirements

### Dependencies (imports)
- `sys` -- command-line argument parsing (`sys.argv`)
- `datetime` -- datetime type (imported but not directly used in `main`)
- `pathlib.Path` -- results directory creation and file path handling
- `src.portfolio_loader.PortfolioLoader` -- XER file loading and merging
- `src.activity_network.ActivityNetwork` -- network construction
- `src.calendar_engine.CalendarEngine` -- calendar loading
- `src.simulation_engine.SimulationEngine` -- simulation execution
- `src.simulation_engine.triangular_sampler` -- Monte Carlo duration model
- `src.visualization.gantt_chart` -- Gantt chart generation
- `src.visualization.duration_histogram` -- histogram generation
- `src.visualization.s_curve` -- S-curve generation
- `src.visualization.criticality_index` -- criticality chart generation

### Not Imported/Used
- `src.visualization.resource_utilization` -- defined in visualization module but not imported or used by run_simulation.
- `SimulationResult` type is referenced in the `save_results_csv` function signature as a string annotation but not imported.

---

## 7. Performance Requirements

| ID | Requirement |
|----|-------------|
| PR-RUN-001 | Monte Carlo runs use `resource_constrained=False` for faster execution. |
| PR-RUN-002 | Monte Carlo runs default to no calendar conversion (`run_monte_carlo` defaults to `convert_calendar=False`) for performance. |
| PR-RUN-003 | The number of Monte Carlo runs is set to 50 (a moderate value balancing statistical significance and execution time). |

---

## 8. Error Handling Requirements

| ID | Condition | Behavior |
|----|-----------|----------|
| EH-RUN-001 | No XER files in data directory | `FileNotFoundError` propagates from `PortfolioLoader`. |
| EH-RUN-002 | Invalid XER file content | Errors propagate from `XERParser`. |
| EH-RUN-003 | Cycle in activity network | `ValueError` propagates from `ActivityNetwork.topological_order()`. |
| EH-RUN-004 | Results directory creation failure | OS-level error propagates. |
| EH-RUN-005 | Missing columns in CSV export | Columns not present in DataFrame are silently excluded from the output. |

---

## 9. Constraints and Assumptions

| ID | Constraint/Assumption |
|----|----------------------|
| CA-RUN-001 | The script assumes it is run from the project root directory (paths are relative: `data/`, `results/`). |
| CA-RUN-002 | The `results/` directory is created relative to the current working directory. |
| CA-RUN-003 | Monte Carlo parameters are hardcoded: 50 runs, triangular(0.8, 1.0, 1.5), seed 42. |
| CA-RUN-004 | Deterministic and resource-constrained simulations use the default (deterministic) duration sampler. |
| CA-RUN-005 | The Gantt chart `top_n` is hardcoded to 40 activities. |
| CA-RUN-006 | The criticality index `top_n` is hardcoded to 30 activities. |
| CA-RUN-007 | The `save_results_csv` function uses a forward-reference string annotation for `SimulationResult` but does not import the type. |
| CA-RUN-008 | The script does not return an exit code; success/failure is indicated by exception propagation. |
| CA-RUN-009 | The `ActivityNetwork` and `CalendarEngine` are created standalone in steps 2-3 for summary display, but the `SimulationEngine` creates its own internal instances of these. |
| CA-RUN-010 | Console output uses `print()` throughout for progress indication; no logging framework is used. |
