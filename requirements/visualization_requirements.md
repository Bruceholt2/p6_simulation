# Visualization Requirements Document

**Module:** `src/visualization.py`
**Last Updated:** 2026-03-16

---

## 1. Module Overview

The `visualization` module generates charts and plots from simulation results using matplotlib. It provides five chart types: Gantt charts (schedule visualization), duration histograms (Monte Carlo distribution), S-curves (cumulative work hours), resource utilization charts (stacked area), and criticality index charts (bar chart of how often each activity is critical). All functions produce matplotlib Figure objects, optionally save them to files, and close the figure to free memory.

---

## 2. Functional Requirements

### Global Configuration

| ID | Requirement |
|----|-------------|
| FR-VIS-001 | The module SHALL set the matplotlib backend to `"Agg"` (non-interactive) at import time via `matplotlib.use("Agg")` to support headless/file-output rendering. |

### Gantt Chart (`gantt_chart`)

| ID | Requirement |
|----|-------------|
| FR-VIS-002 | `gantt_chart` SHALL accept a `SimulationResult`, optional `top_n` (default 50), `show_critical` (default True), `use_calendar_dates` (default True), `title`, `figsize`, and `save_path`. |
| FR-VIS-003 | If the result DataFrame is empty, the function SHALL return a figure with "No activities to display" centered text. |
| FR-VIS-004 | Activities SHALL be sorted by `sim_start_time` ascending. |
| FR-VIS-005 | If `top_n` is specified and fewer activities than total exist, the function SHALL select the `top_n` activities with the largest `simulated_duration_hours` and re-sort by start time. |
| FR-VIS-006 | Activity labels SHALL be formatted as `"{task_code} -- {task_name}"` and truncated to 40 characters (37 + "...") if longer. |
| FR-VIS-007 | If `use_calendar_dates` is True and `sim_start_date` is not None, the x-axis SHALL use matplotlib date numbers for proper date formatting. |
| FR-VIS-008 | If `use_calendar_dates` is False, the x-axis SHALL display simulation hours. |
| FR-VIS-009 | Critical activities SHALL be colored red (`#e74c3c`) when `show_critical` is True; non-critical activities SHALL be blue (`#3498db`). |
| FR-VIS-010 | If `wait_hours > 0` and calendar dates are not used, wait time SHALL be rendered as an orange (`#f39c12`) bar preceding the activity bar with alpha 0.5. |
| FR-VIS-011 | The y-axis SHALL be inverted (earliest activities at top). |
| FR-VIS-012 | When using calendar dates, the x-axis SHALL use `DateFormatter("%Y-%m-%d")` and `AutoDateLocator`, with 45-degree rotation for date labels. |
| FR-VIS-013 | A legend SHALL be displayed in the lower right with Critical and Non-Critical entries. |
| FR-VIS-014 | Bars SHALL have height 0.6, alpha 0.85, and white edgecolor with linewidth 0.5. |

### Duration Histogram (`duration_histogram`)

| ID | Requirement |
|----|-------------|
| FR-VIS-015 | `duration_histogram` SHALL accept a list of `SimulationResult` objects, optional `bins` (default 30), `percentiles` (default [10, 50, 80, 90]), `title`, `figsize`, and `save_path`. |
| FR-VIS-016 | The histogram SHALL plot project duration hours from all runs. |
| FR-VIS-017 | Percentile lines SHALL be drawn as dashed vertical lines with colors cycling through `["#2ecc71", "#f39c12", "#e67e22", "#e74c3c"]`, labeled as `"P{pct}: {value:.0f}h"`. |
| FR-VIS-018 | A mean line SHALL be drawn as a solid black vertical line labeled `"Mean: {value:.0f}h"`. |
| FR-VIS-019 | The x-axis SHALL be labeled "Project Duration (Work Hours)" and y-axis "Frequency". |

### S-Curve (`s_curve`)

| ID | Requirement |
|----|-------------|
| FR-VIS-020 | `s_curve` SHALL accept a `SimulationResult`, optional `num_points` (default 200), `title`, `figsize`, and `save_path`. |
| FR-VIS-021 | If the result DataFrame is empty, it SHALL return an empty figure with just the title. |
| FR-VIS-022 | The function SHALL evaluate cumulative work hours at `num_points` evenly spaced time points from 0 to `max(sim_finish_time)`. If max time is 0, it SHALL use 1.0. |
| FR-VIS-023 | For each activity at each time point: if time is before start, zero contribution; if time is at or past finish, full duration contributed; if between start and finish, proportional elapsed time contributed. |
| FR-VIS-024 | Activities with zero or negative duration SHALL be skipped. |
| FR-VIS-025 | A horizontal dashed red line SHALL mark the total planned work hours. |
| FR-VIS-026 | The x-axis SHALL be "Simulation Hours" and y-axis "Cumulative Work Hours". |

### Resource Utilization (`resource_utilization`)

| ID | Requirement |
|----|-------------|
| FR-VIS-027 | `resource_utilization` SHALL accept a `SimulationResult`, `resource_assignments` (dict of task_id to list of rsrc_ids), `resource_names` (dict of rsrc_id to name), optional `num_points` (default 200), `title`, `figsize`, and `save_path`. |
| FR-VIS-028 | If the result DataFrame is empty, it SHALL return a figure with just the title. |
| FR-VIS-029 | If no resources are assigned to any activity in the results, it SHALL display "No resource assignments" centered text. |
| FR-VIS-030 | The function SHALL calculate utilization per resource over `num_points` time points. For each activity and each assigned resource, it SHALL increment utilization by 1 for all time points where `start <= t < finish`. |
| FR-VIS-031 | The chart SHALL be rendered as a stacked area plot (`stackplot`) with resource labels and alpha 0.7. |
| FR-VIS-032 | The y-axis SHALL be labeled "Concurrent Resource Units". |
| FR-VIS-033 | Resource legend SHALL be in upper right with max 2 columns. |

### Criticality Index (`criticality_index`)

| ID | Requirement |
|----|-------------|
| FR-VIS-034 | `criticality_index` SHALL accept a list of `SimulationResult` objects, optional `top_n` (default 30), `title`, `figsize`, and `save_path`. |
| FR-VIS-035 | If results list is empty, it SHALL return a figure with just the title. |
| FR-VIS-036 | The criticality index for each activity SHALL be computed as `(count of runs where is_critical is True) / (total runs) * 100`. |
| FR-VIS-037 | If no activities are ever critical, it SHALL display "No critical activities found" centered text. |
| FR-VIS-038 | Activities SHALL be sorted by criticality index descending, and limited to `top_n`. |
| FR-VIS-039 | Activity labels SHALL be truncated to 40 characters (37 + "...") if longer. |
| FR-VIS-040 | Bar colors SHALL be: red (`#e74c3c`) for index >= 80%, orange (`#f39c12`) for >= 50%, blue (`#3498db`) for < 50%. |
| FR-VIS-041 | The x-axis range SHALL be 0 to 105% with label "Criticality Index (%)". |
| FR-VIS-042 | The y-axis SHALL be inverted (most critical at top). |
| FR-VIS-043 | A three-entry legend SHALL be displayed in lower right: ">= 80%", ">= 50%", "< 50%". |

### Common Behaviors

| ID | Requirement |
|----|-------------|
| FR-VIS-044 | All chart functions SHALL call `fig.tight_layout()` before saving or returning. |
| FR-VIS-045 | All chart functions SHALL call `plt.close(fig)` after saving to free matplotlib memory. |
| FR-VIS-046 | If `save_path` is provided, all chart functions SHALL save the figure at 150 DPI with `bbox_inches="tight"`. |
| FR-VIS-047 | All chart functions SHALL return the matplotlib `Figure` object. |

---

## 3. Input Requirements

| Input | Type | Description |
|-------|------|-------------|
| `result` | `SimulationResult` | Single run result with activity-level data. |
| `results` | `list[SimulationResult]` | Multiple run results for Monte Carlo charts. |
| `resource_assignments` | `dict[int, list[int]]` | Task ID to resource ID mapping. |
| `resource_names` | `dict[int, str]` | Resource ID to display name mapping. |
| `top_n` | `int | None` | Limit on displayed activities/entries. |
| `bins` | `int` | Histogram bin count. |
| `percentiles` | `list[float] | None` | Percentile values to mark. |
| `num_points` | `int` | Time discretization resolution. |
| `title` | `str` | Chart title text. |
| `figsize` | `tuple[float, float]` | Figure dimensions in inches. |
| `save_path` | `str | Path | None` | Output file path. |

---

## 4. Output Requirements

| Output | Type | Description |
|--------|------|-------------|
| Return value | `plt.Figure` | Matplotlib figure (closed but returned). |
| Saved file | PNG image | At specified path, 150 DPI, tight bounding box. |

---

## 5. Data Requirements

The module consumes `SimulationResult` objects, which must provide:
- `to_dataframe()` returning a DataFrame with columns: `task_id`, `task_code`, `task_name`, `sim_start_time`, `sim_finish_time`, `simulated_duration_hours`, `planned_duration_hours`, `sim_start_date`, `sim_finish_date`, `wait_hours`, `is_critical`
- `project_duration_hours` float attribute
- `project_start` datetime attribute

---

## 6. Interface Requirements

### Dependencies (imports)
- `matplotlib` -- chart rendering (pyplot, dates, patches)
- `numpy` -- array operations, percentile calculations, linspace
- `pandas` -- DataFrame operations
- `pathlib.Path` -- file path handling
- `src.simulation_engine` -- `ActivityResult`, `SimulationResult` types

### Dependents (modules that import this module)
- `run_simulation.py` -- imports `gantt_chart`, `duration_histogram`, `s_curve`, `criticality_index`

### Not Used Internally
- The `resource_utilization` function is defined but not called by `run_simulation.py`.

---

## 7. Performance Requirements

| ID | Requirement |
|----|-------------|
| PR-VIS-001 | The Agg backend is used to avoid GUI rendering overhead. |
| PR-VIS-002 | Figures are closed after creation to free memory (`plt.close(fig)`). |
| PR-VIS-003 | S-curve and resource utilization use NumPy arrays for time-point calculations rather than Python loops where possible. |
| PR-VIS-004 | Activity count is limited by `top_n` to prevent unreadable charts and excessive rendering time. |

---

## 8. Error Handling Requirements

| ID | Condition | Behavior |
|----|-----------|----------|
| EH-VIS-001 | Empty result DataFrame (Gantt chart) | Displays "No activities to display" message on chart. |
| EH-VIS-002 | Empty result DataFrame (S-curve) | Returns empty figure with title only. |
| EH-VIS-003 | Empty result DataFrame (resource utilization) | Returns figure with title only. |
| EH-VIS-004 | No resource assignments (resource utilization) | Displays "No resource assignments" message. |
| EH-VIS-005 | Empty results list (criticality index) | Returns figure with title only. |
| EH-VIS-006 | No critical activities found (criticality index) | Displays "No critical activities found" message. |
| EH-VIS-007 | `max_time` is 0 in S-curve/resource utilization | Uses 1.0 as fallback to avoid division by zero. |
| EH-VIS-008 | Activity with zero duration in S-curve | Skipped (continue to next activity). |

---

## 9. Constraints and Assumptions

| ID | Constraint/Assumption |
|----|----------------------|
| CA-VIS-001 | The matplotlib Agg backend must be set before any pyplot imports; this is done at module level. |
| CA-VIS-002 | Chart labels are truncated at 40 characters to maintain readability. |
| CA-VIS-003 | The S-curve assumes linear progress within each activity (proportional completion between start and finish). |
| CA-VIS-004 | Resource utilization assumes each active activity uses exactly 1 unit of each assigned resource at any given time. |
| CA-VIS-005 | Calendar date display in Gantt charts requires that `sim_start_date` and `sim_finish_date` have been computed (calendar conversion must have been performed). |
| CA-VIS-006 | Default figure sizes are tuned for desktop viewing and A4-compatible printing. |
| CA-VIS-007 | The color palette is hardcoded (red for critical, blue for non-critical, orange for wait, green/orange/red for percentile lines). |
| CA-VIS-008 | Criticality index color thresholds are hardcoded at 80% (red) and 50% (orange). |
| CA-VIS-009 | Wait time visualization in Gantt charts is only displayed when calendar dates are not used (`use_calendar_dates=False`). |
| CA-VIS-010 | All figures are saved at 150 DPI, which balances file size and quality. |
