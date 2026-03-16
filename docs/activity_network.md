# activity_network.py

**Location:** `src/activity_network.py`

## Purpose

Constructs a directed dependency graph from parsed XER schedule data. Activities are nodes, predecessor/successor relationships are edges. Provides topological ordering and critical path identification.

## Enums

| Enum | Values | Description |
|------|--------|-------------|
| `RelationshipType` | `FS`, `FF`, `SS`, `SF` | P6 relationship types (Finish-to-Start, etc.) |
| `TaskType` | `TASK`, `MILESTONE`, `FINISH_MILESTONE`, `LOE`, `RESOURCE_DEPENDENT` | P6 activity types |
| `StatusCode` | `NOT_STARTED`, `ACTIVE`, `COMPLETE` | P6 activity statuses |

## Dataclasses

### Relationship

| Field | Type | Description |
|-------|------|-------------|
| `predecessor_id` | `int` | Predecessor task_id |
| `successor_id` | `int` | Successor task_id |
| `rel_type` | `RelationshipType` | FS, FF, SS, or SF |
| `lag_hours` | `float` | Lag in hours (negative = lead) |

### Activity

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `int` | Unique identifier |
| `task_code` | `str` | User-visible activity code |
| `task_name` | `str` | Activity description |
| `task_type` | `TaskType` | Task, milestone, etc. |
| `status` | `StatusCode` | Not started, active, complete |
| `original_duration_hours` | `float` | Planned duration |
| `remaining_duration_hours` | `float` | Remaining duration |
| `calendar_id` | `int \| None` | Assigned calendar |
| `early_start/finish` | `Timestamp \| None` | CPM early dates |
| `late_start/finish` | `Timestamp \| None` | CPM late dates |
| `total_float_hours` | `float` | Total float |
| `predecessors` | `list[Relationship]` | Incoming relationships |
| `successors` | `list[Relationship]` | Outgoing relationships |

**Properties:** `is_milestone` (bool), `is_critical` (bool — total float near zero)

## Class: ActivityNetwork

### Constructor

```python
ActivityNetwork(parser: XERParser)
```

Builds the network automatically from the parser's TASK and TASKPRED tables.

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_activity(task_id)` | `Activity` | Look up an activity by ID. Raises `KeyError` if missing. |
| `start_activities()` | `list[Activity]` | Activities with no predecessors. |
| `end_activities()` | `list[Activity]` | Activities with no successors. |
| `predecessors_of(task_id)` | `list[Activity]` | All predecessor activities. |
| `successors_of(task_id)` | `list[Activity]` | All successor activities. |
| `topological_order()` | `list[Activity]` | Kahn's algorithm. Raises `ValueError` on cycles. |
| `critical_path()` | `list[Activity]` | Zero-float activities in topological order. |
| `summary()` | `str` | Prints network statistics. |

### Properties

| Property | Returns | Description |
|----------|---------|-------------|
| `activities` | `dict[int, Activity]` | All activities keyed by task_id. |
| `num_activities` | `int` | Total activity count. |
| `num_relationships` | `int` | Total relationship count. |

### Usage

```python
from src.xer_parser import XERParser
from src.activity_network import ActivityNetwork

parser = XERParser("data/sample-5272.xer")
network = ActivityNetwork(parser)
network.summary()

for activity in network.critical_path():
    print(f"{activity.task_code}: {activity.task_name}")
```

## Tests

See `tests/test_activity_network.py` — 27 tests covering construction, relationships, topological ordering, critical path, summary, and real XER data.
