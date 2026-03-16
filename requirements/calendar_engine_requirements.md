# Calendar Engine Requirements Document

**Module:** `src/calendar_engine.py`
**Last Updated:** 2026-03-16

---

## 1. Module Overview

The `calendar_engine` module parses Primavera P6 calendar definitions from `clndr_data` strings and provides calendar-aware time calculations. It converts between work hours and calendar datetime values, respecting weekly work schedules, work periods within each day, and exception dates (holidays, modified work days). This module is essential for translating simulation hours into real-world calendar dates.

---

## 2. Functional Requirements

### Data Structures

| ID | Requirement |
|----|-------------|
| FR-CAL-001 | The `WorkPeriod` dataclass SHALL represent a contiguous work period within a day with `start` and `finish` as `time` objects, and a computed `hours` property giving the duration in decimal hours. |
| FR-CAL-002 | The `DaySchedule` dataclass SHALL represent a day's work schedule as an ordered list of `WorkPeriod` objects. An empty list means a non-work day. |
| FR-CAL-003 | `DaySchedule.is_workday` SHALL return `True` if the day has at least one work period. |
| FR-CAL-004 | `DaySchedule.total_hours` SHALL return the sum of all work period durations in hours. |
| FR-CAL-005 | `DaySchedule.earliest_start` SHALL return the start time of the first work period, or `None` for non-work days. |
| FR-CAL-006 | `DaySchedule.latest_finish` SHALL return the finish time of the last work period, or `None` for non-work days. |
| FR-CAL-007 | The `CalendarDefinition` dataclass SHALL store `calendar_id` (int), `name` (str), `week_schedule` (list of 7 `DaySchedule` objects indexed 0=Monday through 6=Sunday), and `exceptions` (dict mapping `datetime` to `DaySchedule`). |

### Parsing Functions

| ID | Requirement |
|----|-------------|
| FR-CAL-008 | `_parse_time(s)` SHALL parse a time string in `HH:MM` or `HHMM` format into a `time` object. |
| FR-CAL-009 | `_parse_work_periods(text)` SHALL extract all work periods from a calendar data fragment by matching the regex pattern `\(s\|(\d{2}:\d{2})\|f\|(\d{2}:\d{2})\)`. Only periods where `start < finish` SHALL be included. Results SHALL be sorted by start time. |
| FR-CAL-010 | `_serial_to_date(serial)` SHALL convert a P6/Excel serial day number to a `datetime` using the epoch `1899-12-30`. |
| FR-CAL-011 | `_find_balanced_block(text, start)` SHALL extract the content between a balanced pair of parentheses starting at the given index. If no matching closing parenthesis is found, it SHALL return the text from `start+1` to end of string. |
| FR-CAL-012 | `_extract_section(data, section_name)` SHALL find a named section (e.g., `DaysOfWeek`, `Exceptions`) in the `clndr_data` string and return the children block content. |
| FR-CAL-013 | `_parse_clndr_data(clndr_data)` SHALL parse the full `clndr_data` string and return a tuple of `(week_schedule, exceptions)`. If `clndr_data` is empty or `NaN`, it SHALL return a default empty week schedule and empty exceptions dictionary. |
| FR-CAL-014 | The `DaysOfWeek` section parser SHALL map P6 day numbers (1=Sunday through 7=Saturday) to Python weekday indices (0=Monday through 6=Sunday) using the mapping `{1:6, 2:0, 3:1, 4:2, 5:3, 6:4, 7:5}`. |
| FR-CAL-015 | The `Exceptions` section parser SHALL extract exception entries by matching `\(0\|\|\d+\(d\|(\d+)\)` patterns, convert the serial day number to a date, parse work periods, and store as `DaySchedule` objects in the exceptions dictionary. An exception with no work periods represents a holiday. |
| FR-CAL-016 | `_default_calendar()` SHALL create a standard 5-day, 8-hour calendar with work periods 08:00-12:00 and 13:00-17:00 Monday through Friday, non-work Saturday and Sunday, calendar ID of -1, and name "Default 5-Day 8-Hour". |

### CalendarEngine Class

| ID | Requirement |
|----|-------------|
| FR-CAL-017 | The `CalendarEngine` class SHALL accept an `XERParser` (or compatible) and load all calendar definitions from the `CALENDAR` table upon instantiation. |
| FR-CAL-018 | The `_load_calendars` method SHALL parse each calendar row's `clndr_data` string. If parsing fails (any exception), it SHALL fall back to the default calendar's week schedule for that calendar. |
| FR-CAL-019 | `get_calendar(calendar_id)` SHALL return the `CalendarDefinition` for the given ID, or the default calendar if the ID is not found. |
| FR-CAL-020 | `_get_day_schedule(calendar_id, dt)` SHALL check the calendar's exceptions dictionary first (normalizing `dt` to midnight for lookup), then fall back to the standard weekly schedule based on `dt.weekday()`. |
| FR-CAL-021 | `is_work_time(calendar_id, dt)` SHALL return `True` if the given datetime falls within any work period (`period.start <= t < period.finish`) of the effective day schedule. |
| FR-CAL-022 | `get_work_hours_per_day(calendar_id, day_of_week)` SHALL return the total standard work hours for the specified weekday from the calendar's weekly schedule (not considering exceptions). |
| FR-CAL-023 | `next_work_start(calendar_id, dt)` SHALL find the next work period start at or after the given datetime. If currently within a work period, return `dt` unchanged. Otherwise check remaining periods today, then advance day-by-day up to 365 days. |
| FR-CAL-024 | `calculate_finish(calendar_id, start_datetime, work_hours)` SHALL compute the calendar datetime when an activity finishes, given its start time and duration in work hours. If `work_hours <= 0`, it SHALL return `start_datetime` immediately. |
| FR-CAL-025 | The `calculate_finish` method SHALL implement a bulk week-skipping optimization: when remaining hours exceed twice the weekly hours, it SHALL align to Monday, then skip full weeks at a time, using `bisect` to detect exception dates in the skip range. |
| FR-CAL-026 | When bulk-skipping encounters an exception within the skip range, the method SHALL only skip weeks up to the Monday before the exception, then process that week day-by-day before resuming bulk skipping. |
| FR-CAL-027 | After bulk-skipping, the method SHALL process remaining hours day-by-day, period-by-period, with a safety limit of 10,000 day iterations. |
| FR-CAL-028 | When computing the finish time within a period, the method SHALL handle the edge case where rounding produces 60 minutes by incrementing the hour and setting minutes to 0. |
| FR-CAL-029 | `calculate_work_hours_between(calendar_id, start_datetime, end_datetime)` SHALL compute total work hours between two datetimes by iterating day-by-day and clamping each work period to the query range. If `end_datetime <= start_datetime`, it SHALL return 0.0. |
| FR-CAL-030 | `summary()` SHALL return and print a multi-line string listing each calendar's ID, name, work days, hours per week, and number of exceptions. |

### Helper Methods

| ID | Requirement |
|----|-------------|
| FR-CAL-031 | `_day_available(cal, dt)` SHALL return the total work hours for a date, checking exceptions first then the weekly schedule. |
| FR-CAL-032 | `_consume_day_hours(cal, dt, remaining)` SHALL subtract a full day's available hours from the remaining hours and return the new remaining value. |
| FR-CAL-033 | `_advance_to_next_workday(calendar_id, current)` SHALL advance to the start of the next calendar day and find the next work start. |
| FR-CAL-034 | `_finish_in_day(cal, dt, work_hours)` SHALL find the exact finish time within a day for the given number of work hours, iterating through periods and computing the precise minute within the correct period. |

---

## 3. Input Requirements

| Input | Format | Validation |
|-------|--------|------------|
| `parser` | `XERParser` or compatible with `calendars` property | Must provide CALENDAR DataFrame with `clndr_id`, `clndr_name`, `clndr_data` columns. |
| `clndr_data` | P6 calendar data string with nested parenthesized sections | Complex nested format; parsed with regex and balanced-parenthesis extraction. |
| `calendar_id` (runtime) | `int` | No validation; returns default calendar if not found. |
| `dt` (runtime) | `datetime` | Standard Python datetime object. |
| `work_hours` (runtime) | `float` | Non-negative float. Zero or negative returns start time immediately. |

---

## 4. Output Requirements

| Output | Type | Description |
|--------|------|-------------|
| `get_calendar()` | `CalendarDefinition` | Calendar definition or default. |
| `is_work_time()` | `bool` | Whether datetime is during work hours. |
| `get_work_hours_per_day()` | `float` | Standard hours for a weekday. |
| `next_work_start()` | `datetime` | Next work period start datetime. |
| `calculate_finish()` | `datetime` | Calendar datetime when activity finishes. |
| `calculate_work_hours_between()` | `float` | Work hours between two datetimes. |
| `summary()` | `str` | Multi-line calendar summary (also printed). |

---

## 5. Data Requirements

### WorkPeriod
| Field | Type | Description |
|-------|------|-------------|
| `start` | `time` | Period start time (e.g., 08:00) |
| `finish` | `time` | Period finish time (e.g., 12:00) |

### DaySchedule
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `periods` | `list[WorkPeriod]` | `[]` | Ordered work periods; empty = non-work day |

### CalendarDefinition
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `calendar_id` | `int` | Required | Unique identifier |
| `name` | `str` | Required | Calendar name |
| `week_schedule` | `list[DaySchedule]` (length 7) | 7 empty schedules | Index 0=Monday through 6=Sunday |
| `exceptions` | `dict[datetime, DaySchedule]` | `{}` | Date-specific overrides |

### P6 Day Number Mapping

| P6 Day Number | Day Name | Python Weekday |
|---------------|----------|----------------|
| 1 | Sunday | 6 |
| 2 | Monday | 0 |
| 3 | Tuesday | 1 |
| 4 | Wednesday | 2 |
| 5 | Thursday | 3 |
| 6 | Friday | 4 |
| 7 | Saturday | 5 |

### Module Constants
| Constant | Value | Description |
|----------|-------|-------------|
| `_P6_EPOCH` | `datetime(1899, 12, 30)` | P6/Excel serial date epoch |

---

## 6. Interface Requirements

### Dependencies (imports)
- `re` -- regex pattern matching for calendar data parsing
- `dataclasses` -- data structure definitions
- `datetime` -- `datetime`, `time`, `timedelta` for time calculations
- `bisect` (imported inside `calculate_finish`) -- binary search on sorted exception dates
- `pandas` -- `pd.isna()` for null checking
- `src.xer_parser.XERParser` -- type annotation for constructor

### Dependents (modules that import this module)
- `src.simulation_engine` -- imports `CalendarEngine` for calendar-aware date conversion
- `run_simulation.py` -- imports `CalendarEngine` for standalone calendar loading

---

## 7. Performance Requirements

| ID | Requirement |
|----|-------------|
| PR-CAL-001 | Calendar definitions are parsed once at construction time and cached in a dictionary for O(1) lookup by ID. |
| PR-CAL-002 | `calculate_finish` implements a bulk week-skipping optimization that avoids day-by-day iteration for large durations, reducing complexity from O(days) to O(weeks + exceptions). |
| PR-CAL-003 | Exception dates are sorted once per `calculate_finish` call and searched using `bisect.bisect_left` for O(log n) lookup. |
| PR-CAL-004 | The `_P6_EPOCH` constant is precomputed at module level to avoid repeated object creation. |
| PR-CAL-005 | Weekly hours are precomputed once per `calculate_finish` call from the standard schedule. |
| PR-CAL-006 | The `next_work_start` method has a safety limit of 365 day iterations to prevent infinite loops with malformed calendars. |
| PR-CAL-007 | The `calculate_finish` day-by-day fallback has a safety limit of 10,000 iterations. |

---

## 8. Error Handling Requirements

| ID | Condition | Behavior |
|----|-----------|----------|
| EH-CAL-001 | `clndr_data` parsing fails (any exception) | Falls back to default calendar week schedule for that calendar. |
| EH-CAL-002 | `clndr_data` is empty or `NaN` | Returns default empty week schedule and empty exceptions. |
| EH-CAL-003 | Calendar ID not found in loaded calendars | Returns the default 5-day, 8-hour calendar. |
| EH-CAL-004 | Work period has `start >= finish` | Period is excluded from the parsed results. |
| EH-CAL-005 | Unrecognized P6 day number in `DaysOfWeek` section | Day is silently skipped (not in `p6_to_python` mapping). |
| EH-CAL-006 | `next_work_start` cannot find a work day within 365 days | Returns the original datetime as fallback. |
| EH-CAL-007 | `calculate_finish` exceeds 10,000 day iterations | Returns the current datetime (safety limit reached). |
| EH-CAL-008 | `end_datetime <= start_datetime` in `calculate_work_hours_between` | Returns 0.0. |
| EH-CAL-009 | Rounding produces 60 minutes | Hour is incremented and minutes set to 0. |

---

## 9. Constraints and Assumptions

| ID | Constraint/Assumption |
|----|----------------------|
| CA-CAL-001 | P6 `clndr_data` strings follow the nested parenthesized format with `DaysOfWeek` and `Exceptions` sections. |
| CA-CAL-002 | P6 serial dates use the same epoch as Excel/OLE Automation (`1899-12-30`). |
| CA-CAL-003 | Work periods do not span midnight (start time is always earlier than finish time within the same day). |
| CA-CAL-004 | The default calendar assumes a standard 5-day, 8-hour work week (Mon-Fri, 08:00-12:00 and 13:00-17:00). |
| CA-CAL-005 | Exception dates are stored normalized to midnight (`datetime(year, month, day)`) for consistent dictionary lookup. |
| CA-CAL-006 | The `calculate_finish` method assumes `work_hours` is non-negative. |
| CA-CAL-007 | Time precision is limited to minutes (no seconds). |
| CA-CAL-008 | A floating-point tolerance of `1e-9` is used for hour comparisons to handle rounding errors. |
| CA-CAL-009 | The bulk week-skip optimization assumes the calendar has a consistent weekly pattern; exceptions within the skip range are handled by falling back to day-by-day processing. |
