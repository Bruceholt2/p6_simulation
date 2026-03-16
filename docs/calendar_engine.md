# calendar_engine.py

**Location:** `src/calendar_engine.py`

## Purpose

Parses P6 calendar definitions (`clndr_data` strings) and provides methods to convert between work hours and calendar time, respecting weekly work schedules, lunch breaks, and exception dates (holidays, modified work days).

## Dataclasses

### WorkPeriod

A single work window within a day (e.g., 08:00-12:00).

| Field | Type | Description |
|-------|------|-------------|
| `start` | `time` | Period start time |
| `finish` | `time` | Period end time |

**Property:** `hours` (float) — duration of the period.

### DaySchedule

Work schedule for a single day.

| Field | Type | Description |
|-------|------|-------------|
| `periods` | `list[WorkPeriod]` | Ordered work periods. Empty = non-work day. |

**Properties:** `is_workday` (bool), `total_hours` (float), `earliest_start` (time), `latest_finish` (time).

### CalendarDefinition

| Field | Type | Description |
|-------|------|-------------|
| `calendar_id` | `int` | Unique identifier |
| `name` | `str` | Calendar name |
| `week_schedule` | `list[DaySchedule]` | 7 entries (0=Monday .. 6=Sunday) |
| `exceptions` | `dict[datetime, DaySchedule]` | Date-specific overrides |

## Class: CalendarEngine

### Constructor

```python
CalendarEngine(parser: XERParser)
```

Parses all calendars from the CALENDAR table. Falls back to a default 5-day, 8-hour calendar (Mon-Fri, 08:00-12:00, 13:00-17:00) if parsing fails.

### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_calendar` | `(calendar_id) → CalendarDefinition` | Returns calendar definition or the default. |
| `is_work_time` | `(calendar_id, datetime) → bool` | Is this datetime during a work period? |
| `get_work_hours_per_day` | `(calendar_id, day_of_week) → float` | Standard hours for a weekday (0=Mon, 6=Sun). |
| `next_work_start` | `(calendar_id, datetime) → datetime` | When does the next work period begin? |
| `calculate_finish` | `(calendar_id, start, work_hours) → datetime` | When does an activity finish? |
| `calculate_work_hours_between` | `(calendar_id, start, end) → float` | Work hours between two datetimes. |
| `summary` | `() → str` | Prints all loaded calendars with work patterns. |

### Calendar Data Parsing

The `clndr_data` field uses a nested parenthesized format:

- **DaysOfWeek** section: 7 day entries (P6 day 1=Sunday, 2=Monday, ..., 7=Saturday) with work periods defined as `(s|HH:MM|f|HH:MM)`.
- **Exceptions** section: Date overrides using P6/Excel serial day numbers (epoch 1899-12-30). Empty child = holiday; child with work periods = modified day.

### Usage

```python
from datetime import datetime
from src.xer_parser import XERParser
from src.calendar_engine import CalendarEngine

parser = XERParser("data/sample-5272.xer")
calendar = CalendarEngine(parser)
calendar.summary()

# When does a 40-hour task starting Friday 2pm finish?
start = datetime(2025, 7, 11, 14, 0)
finish = calendar.calculate_finish(597, start, 40.0)
print(f"Finish: {finish}")  # Next Friday 2pm (skips weekend)
```

## Tests

See `tests/test_calendar_engine.py` — 45 tests covering work periods, day schedules, serial date conversion, calendar parsing, work time checks, next work start, calculate finish (weekends, holidays, lunch breaks, milestones), work hours between, and real XER data.
