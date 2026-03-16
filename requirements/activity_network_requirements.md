# Activity Network Requirements Document

**Module:** `src/activity_network.py`
**Last Updated:** 2026-03-16

---

## 1. Module Overview

The `activity_network` module constructs a directed graph representing the project schedule. Activities are nodes and predecessor/successor relationships are edges. The module provides graph traversal, topological ordering (Kahn's algorithm), and critical path identification. It transforms raw tabular XER data into a structured network model consumed by the simulation engine.

---

## 2. Functional Requirements

### Enumerations

| ID | Requirement |
|----|-------------|
| FR-NET-001 | The `RelationshipType` enum SHALL define four P6 relationship types: `FS` ("PR_FS"), `FF` ("PR_FF"), `SS` ("PR_SS"), `SF` ("PR_SF"). |
| FR-NET-002 | The `TaskType` enum SHALL define five P6 activity types: `TASK` ("TT_Task"), `MILESTONE` ("TT_Mile"), `FINISH_MILESTONE` ("TT_FinMile"), `LOE` ("TT_LOE"), `RESOURCE_DEPENDENT` ("TT_Rsrc"). |
| FR-NET-003 | The `StatusCode` enum SHALL define three P6 status codes: `NOT_STARTED` ("TK_NotStart"), `ACTIVE` ("TK_Active"), `COMPLETE` ("TK_Complete"). |

### Data Classes

| ID | Requirement |
|----|-------------|
| FR-NET-004 | The `Relationship` dataclass SHALL store `predecessor_id` (int), `successor_id` (int), `rel_type` (RelationshipType), and `lag_hours` (float, negative for leads). |
| FR-NET-005 | The `Activity` dataclass SHALL store `task_id`, `task_code`, `task_name`, `task_type`, `status`, `original_duration_hours`, `remaining_duration_hours`, `calendar_id`, `early_start`, `early_finish`, `late_start`, `late_finish`, `total_float_hours`, and lists of `predecessors` and `successors` relationships. |
| FR-NET-006 | The `Activity.is_milestone` property SHALL return `True` if `task_type` is `MILESTONE` or `FINISH_MILESTONE`. |
| FR-NET-007 | The `Activity.is_critical` property SHALL return `True` if the absolute value of `total_float_hours` is less than 0.01. |

### Network Construction

| ID | Requirement |
|----|-------------|
| FR-NET-008 | The `ActivityNetwork` class SHALL accept an `XERParser` (or compatible interface) and automatically build the network upon instantiation. |
| FR-NET-009 | The `_load_activities` method SHALL create `Activity` objects from the `TASK` table. It SHALL use the column `target_drtn_hr_cnt` for original duration if present, otherwise fall back to `orig_dur_hr_cnt`. Similarly, `remain_drtn_hr_cnt` is preferred over `remain_dur_hr_cnt` for remaining duration. |
| FR-NET-010 | For each task row, the method SHALL parse `task_type` into the `TaskType` enum, defaulting to `TaskType.TASK` if the value is unrecognized. |
| FR-NET-011 | For each task row, the method SHALL parse `status_code` into the `StatusCode` enum, defaulting to `StatusCode.NOT_STARTED` if the value is unrecognized. |
| FR-NET-012 | Duration values (`orig_dur`, `remain_dur`) SHALL default to 0.0 if the column value is missing, `None`, or `NaN`. |
| FR-NET-013 | The `calendar_id` SHALL be extracted from `clndr_id`, converted to `int` if not null, or set to `None` if null. |
| FR-NET-014 | The `total_float_hours` SHALL be extracted from `total_float_hr_cnt`, defaulting to 0.0 if missing. |
| FR-NET-015 | Early start/finish and late start/finish dates SHALL be read from `early_start_date`, `early_end_date`, `late_start_date`, `late_end_date` columns respectively. |

### Relationship Loading

| ID | Requirement |
|----|-------------|
| FR-NET-016 | The `_load_relationships` method SHALL create `Relationship` objects from the `TASKPRED` table using `pred_task_id` as predecessor and `task_id` as successor. |
| FR-NET-017 | Relationships referencing activities not present in the network (either predecessor or successor) SHALL be silently skipped. |
| FR-NET-018 | The `pred_type` column SHALL be parsed into `RelationshipType`, defaulting to `FS` (Finish-to-Start) if unrecognized. |
| FR-NET-019 | Lag hours SHALL be extracted from `lag_hr_cnt`, defaulting to 0.0 if missing. |
| FR-NET-020 | Each relationship SHALL be appended to both the predecessor's `successors` list and the successor's `predecessors` list. |

### Queries and Traversal

| ID | Requirement |
|----|-------------|
| FR-NET-021 | `get_activity(task_id)` SHALL return the `Activity` for the given ID, or raise `KeyError` if not found. |
| FR-NET-022 | The `activities` property SHALL return the full dictionary of activities keyed by `task_id`. |
| FR-NET-023 | `num_activities` SHALL return the total count of activities. |
| FR-NET-024 | `num_relationships` SHALL return the total count of relationships (counted as sum of all successor lists). |
| FR-NET-025 | `start_activities()` SHALL return all activities with no predecessors. |
| FR-NET-026 | `end_activities()` SHALL return all activities with no successors. |
| FR-NET-027 | `predecessors_of(task_id)` SHALL return the list of predecessor `Activity` objects for the given task. |
| FR-NET-028 | `successors_of(task_id)` SHALL return the list of successor `Activity` objects for the given task. |

### Topological Ordering

| ID | Requirement |
|----|-------------|
| FR-NET-029 | `topological_order()` SHALL implement Kahn's algorithm to return activities in dependency order (every predecessor appears before its successors). |
| FR-NET-030 | If the network contains a cycle (not all activities can be ordered), `topological_order()` SHALL raise a `ValueError` reporting how many activities were ordered vs. total. |

### Critical Path

| ID | Requirement |
|----|-------------|
| FR-NET-031 | `critical_path()` SHALL return all activities with `is_critical == True` in topological order. |

### Summary

| ID | Requirement |
|----|-------------|
| FR-NET-032 | `summary()` SHALL return and print a multi-line string with: activity count, relationship count, start/end activity counts, critical activity count, relationship type distribution, and activity type distribution. |

---

## 3. Input Requirements

| Input | Format | Validation |
|-------|--------|------------|
| `parser` | `XERParser` or compatible object with `tasks` and `predecessors` properties | Must provide `tasks` and `predecessors` DataFrames with expected columns. |
| TASK table columns | `task_id`, `task_code`, `task_name`, `task_type`, `status_code`, `target_drtn_hr_cnt` or `orig_dur_hr_cnt`, `remain_drtn_hr_cnt` or `remain_dur_hr_cnt`, `clndr_id`, `early_start_date`, `early_end_date`, `late_start_date`, `late_end_date`, `total_float_hr_cnt` | Missing columns handled with defaults. |
| TASKPRED table columns | `pred_task_id`, `task_id`, `pred_type`, `lag_hr_cnt` | Missing lag defaults to 0. |

---

## 4. Output Requirements

| Output | Type | Description |
|--------|------|-------------|
| `get_activity()` | `Activity` | Single activity node with all attributes and relationship links. |
| `activities` | `dict[int, Activity]` | Full network graph as adjacency-list structure. |
| `topological_order()` | `list[Activity]` | Activities sorted in dependency order. |
| `critical_path()` | `list[Activity]` | Critical activities in dependency order. |
| `summary()` | `str` | Multi-line statistics string (also printed). |

---

## 5. Data Requirements

### Activity Dataclass Fields

| Field | Type | Default | Source Column |
|-------|------|---------|---------------|
| `task_id` | `int` | Required | `task_id` |
| `task_code` | `str` | `""` | `task_code` |
| `task_name` | `str` | `""` | `task_name` |
| `task_type` | `TaskType` | `TASK` | `task_type` |
| `status` | `StatusCode` | `NOT_STARTED` | `status_code` |
| `original_duration_hours` | `float` | `0.0` | `target_drtn_hr_cnt` / `orig_dur_hr_cnt` |
| `remaining_duration_hours` | `float` | `0.0` | `remain_drtn_hr_cnt` / `remain_dur_hr_cnt` |
| `calendar_id` | `int | None` | `None` | `clndr_id` |
| `early_start` | `pd.Timestamp | None` | `None` | `early_start_date` |
| `early_finish` | `pd.Timestamp | None` | `None` | `early_end_date` |
| `late_start` | `pd.Timestamp | None` | `None` | `late_start_date` |
| `late_finish` | `pd.Timestamp | None` | `None` | `late_end_date` |
| `total_float_hours` | `float` | `0.0` | `total_float_hr_cnt` |
| `predecessors` | `list[Relationship]` | `[]` | Built from TASKPRED |
| `successors` | `list[Relationship]` | `[]` | Built from TASKPRED |

### Relationship Dataclass Fields

| Field | Type | Source Column |
|-------|------|---------------|
| `predecessor_id` | `int` | `pred_task_id` |
| `successor_id` | `int` | `task_id` |
| `rel_type` | `RelationshipType` | `pred_type` |
| `lag_hours` | `float` | `lag_hr_cnt` |

---

## 6. Interface Requirements

### Dependencies (imports)
- `collections.defaultdict` -- counting relationship and task types in summary
- `dataclasses` -- `dataclass` and `field` for data structures
- `enum.Enum` -- enumeration types
- `pandas` -- DataFrame iteration
- `src.xer_parser.XERParser` -- type annotation for constructor parameter

### Dependents (modules that import this module)
- `src.simulation_engine` -- imports `Activity`, `ActivityNetwork`, `RelationshipType`, `StatusCode`, `TaskType`
- `run_simulation.py` -- imports `ActivityNetwork` for standalone network building

### API Contract
- The `ActivityNetwork` constructor accepts any object with a `tasks` property returning a DataFrame and a `predecessors` property returning a DataFrame (duck-typed compatibility with both `XERParser` and `PortfolioLoader`).

---

## 7. Performance Requirements

| ID | Requirement |
|----|-------------|
| PR-NET-001 | Network construction is performed once at instantiation. The graph structure is then immutable and reusable. |
| PR-NET-002 | Topological sort uses Kahn's algorithm with O(V + E) time complexity. |
| PR-NET-003 | The `queue` in `topological_order` uses `list.pop(0)` which is O(n) per pop; this is acceptable for typical schedule sizes but not optimal for very large networks. |

---

## 8. Error Handling Requirements

| ID | Condition | Behavior |
|----|-----------|----------|
| EH-NET-001 | Unrecognized `task_type` value | Defaults to `TaskType.TASK`. |
| EH-NET-002 | Unrecognized `status_code` value | Defaults to `StatusCode.NOT_STARTED`. |
| EH-NET-003 | Unrecognized `pred_type` value | Defaults to `RelationshipType.FS`. |
| EH-NET-004 | Relationship references activity not in network | Relationship silently skipped. |
| EH-NET-005 | Missing or null duration/float columns | Default to 0.0. |
| EH-NET-006 | Null `clndr_id` | Set to `None`. |
| EH-NET-007 | Cycle detected in network | `ValueError` raised with count details. |
| EH-NET-008 | Activity not found by `get_activity()` | `KeyError` raised. |

---

## 9. Constraints and Assumptions

| ID | Constraint/Assumption |
|----|----------------------|
| CA-NET-001 | The TASK table contains a `task_id` column that uniquely identifies each activity. |
| CA-NET-002 | The TASKPRED table uses `pred_task_id` and `task_id` to reference activities in the TASK table. |
| CA-NET-003 | Critical path identification relies on `total_float_hr_cnt` values from the XER data (pre-calculated by P6), not on forward/backward pass computation. |
| CA-NET-004 | The critical threshold is hardcoded at 0.01 hours (approximately 36 seconds). |
| CA-NET-005 | The network is assumed to be a directed acyclic graph (DAG); cycles cause a `ValueError`. |
| CA-NET-006 | Duration column naming varies between real P6 exports (`target_drtn_hr_cnt`) and simplified test fixtures (`orig_dur_hr_cnt`); both are supported. |
| CA-NET-007 | LOE (Level of Effort) and Resource Dependent task types are recognized but receive no special scheduling treatment in this module. |
