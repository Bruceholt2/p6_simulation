# P6 XER File Format Reference

## Overview

XER files are Primavera P6's native export format. They are **plain text files** with **tab-delimited** data, typically encoded in **Latin-1 (ISO 8859-1)** — not UTF-8. Always open XER files with `encoding="latin-1"` to avoid decode errors.

## File Structure

An XER file is organized as a sequence of tables. Each table consists of three line types identified by a prefix:

| Prefix | Purpose                              |
|--------|--------------------------------------|
| `%T`   | Table name — starts a new table      |
| `%F`   | Field names — column headers for the table |
| `%R`   | Row data — one data record per line  |

A file ends with an `%E` line (end-of-file marker).

### Example

```
%T	TASK
%F	task_id	proj_id	task_code	task_name	orig_dur_hr_cnt
%R	1001	100	A1000	Mobilization	80
%R	1002	100	A1010	Site Preparation	120
%T	TASKPRED
%F	task_pred_id	task_id	pred_task_id	pred_type	lag_hr_cnt
%R	5001	1002	1001	PR_FS	0
%E
```

Fields within `%F` and `%R` lines are separated by **tab characters** (`\t`). The number of fields in each `%R` row matches the `%F` header for the current table.

## Key Tables

### PROJECT

Project-level metadata.

| Field               | Description                        |
|---------------------|------------------------------------|
| `proj_id`           | Unique project identifier (integer)|
| `proj_short_name`   | Short project name / code          |
| `last_recalc_date`  | Date of last schedule calculation   |

### CALENDAR

Calendar definitions controlling work/non-work time.

| Field         | Description                                      |
|---------------|--------------------------------------------------|
| `clndr_id`    | Unique calendar identifier (integer)             |
| `clndr_name`  | Human-readable calendar name                     |
| `clndr_data`  | Structured string encoding work hours and exceptions (see below) |

### TASK

Activities — the core schedule data.

| Field                 | Description                                    |
|-----------------------|------------------------------------------------|
| `task_id`             | Unique activity identifier (integer)           |
| `proj_id`             | Parent project ID                              |
| `task_code`           | Activity ID / code (user-visible, e.g. "A1000")|
| `task_name`           | Activity description                           |
| `task_type`           | Type: `TT_Task`, `TT_Mile`, `TT_LOE`, `TT_FinMile`, `TT_Rsrc` |
| `status_code`         | Status: `TK_NotStart`, `TK_Active`, `TK_Complete` |
| `total_float_hr_cnt`  | Total float in hours                           |
| `orig_dur_hr_cnt`     | Original duration in hours                     |
| `remain_dur_hr_cnt`   | Remaining duration in hours                    |
| `target_start_date`   | Baseline start date                            |
| `target_end_date`     | Baseline finish date                           |
| `early_start_date`    | Calculated early start                         |
| `early_end_date`      | Calculated early finish                        |
| `late_start_date`     | Calculated late start                          |
| `late_end_date`       | Calculated late finish                         |
| `clndr_id`            | Assigned calendar ID                           |
| `phys_complete_pct`   | Physical percent complete (0–100)              |

### TASKPRED

Activity relationships (logic ties).

| Field           | Description                                         |
|-----------------|-----------------------------------------------------|
| `task_pred_id`  | Unique relationship identifier (integer)            |
| `task_id`       | Successor activity ID                               |
| `pred_task_id`  | Predecessor activity ID                             |
| `pred_type`     | Relationship type: `PR_FS`, `PR_FF`, `PR_SS`, `PR_SF` |
| `lag_hr_cnt`    | Lag duration in hours (can be negative for lead)    |

**Relationship types:**
- `PR_FS` — Finish-to-Start (most common)
- `PR_FF` — Finish-to-Finish
- `PR_SS` — Start-to-Start
- `PR_SF` — Start-to-Finish (rare)

### TASKRSRC

Resource assignments to activities.

| Field              | Description                          |
|--------------------|--------------------------------------|
| `taskrsrc_id`      | Unique assignment identifier         |
| `task_id`          | Activity this resource is assigned to|
| `rsrc_id`          | Resource identifier                  |
| `target_qty_per_hr`| Budgeted units per hour              |
| `target_cost`      | Budgeted cost for this assignment    |

### RSRC

Resource definitions.

| Field             | Description                                    |
|-------------------|------------------------------------------------|
| `rsrc_id`         | Unique resource identifier (integer)           |
| `rsrc_name`       | Full resource name                             |
| `rsrc_short_name` | Short resource name / code                     |
| `rsrc_type`       | Type: `RT_Labor`, `RT_Equip`, `RT_Mat`         |

### RSRCRATE

Resource capacity and cost rates over time.

| Field             | Description                                         |
|-------------------|-----------------------------------------------------|
| `rsrc_rate_id`    | Unique rate record identifier (integer)             |
| `rsrc_id`         | Resource this rate applies to                       |
| `max_qty_per_hr`  | Maximum available units per hour (resource capacity) |
| `cost_per_qty`    | Cost per unit of resource usage                     |
| `start_date`      | Effective date for this rate                        |

## Date Format

Dates in XER files use the format:

```
yyyy-MM-dd HH:mm
```

Example: `2025-03-15 08:00`

Empty/null dates are represented as empty strings between tabs.

## Calendar Data String (`clndr_data`)

The `clndr_data` field contains a structured string that encodes the full calendar definition. Its format uses parenthesized nested entries:

```
(0||1(0|7(0|||0800|1700|1())1|||0800|1700|1())...))
```

Key structure:
- **Day definitions** — 7 entries (Sunday=0 through Saturday=6), each specifying whether it is a workday and the work hours (start/end times).
- **Exceptions** — specific dates marked as non-work (holidays) or modified work hours, listed after the day definitions.

A typical 5-day work week calendar has:
- Days 0 (Sunday) and 6 (Saturday) marked as non-work
- Days 1–5 (Monday–Friday) with work hours like `0800–1700`
- Standard hours per day: 8h (with 1h lunch implied)

## Encoding Notes

- XER files exported from P6 are typically **Latin-1** encoded, not UTF-8.
- Some exports may use **Windows-1252** encoding.
- Always try `latin-1` first; fall back to `cp1252` if characters look wrong.
- Line endings are typically `\r\n` (Windows-style).
