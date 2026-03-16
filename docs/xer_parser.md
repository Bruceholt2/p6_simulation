# xer_parser.py

**Location:** `src/xer_parser.py`

## Purpose

Reads Primavera P6 XER export files and extracts schedule tables into pandas DataFrames with automatic type conversion for dates, numeric fields, and integer IDs.

## Class: XERParser

### Constructor

```python
XERParser(file_path: str | Path)
```

- Accepts a path to an XER file.
- Automatically parses on construction.
- Tries UTF-8 encoding first, falls back to Latin-1.

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_table(table_name)` | `pd.DataFrame` | Returns the DataFrame for a named table. Raises `KeyError` if not found. |
| `summary()` | `str` | Prints and returns a summary of parsed data (counts of projects, activities, relationships, calendars, resources). |

### Properties

| Property | Returns | Description |
|----------|---------|-------------|
| `table_names` | `list[str]` | All table names found in the XER file. |
| `project` | `pd.DataFrame` | PROJECT table. |
| `tasks` | `pd.DataFrame` | TASK table. |
| `predecessors` | `pd.DataFrame` | TASKPRED table. |
| `calendars` | `pd.DataFrame` | CALENDAR table. |
| `resources` | `pd.DataFrame` | RSRC table. |
| `resource_assignments` | `pd.DataFrame` | TASKRSRC table. |

### Type Conversion Rules

The parser automatically converts columns based on naming patterns:

- **Date columns** (`*_date`, `*_date2`, etc.) → `datetime64`
- **Numeric columns** (`*_hr_cnt`, `*_qty`, `*_pct`, `*_cost`, `*_per_hr`) → `float64`
- **ID columns** (`*_id`, excluding `guid`/`tmpl_guid`) → nullable `Int64`

### Usage

```python
from src.xer_parser import XERParser

parser = XERParser("data/sample-5272.xer")
parser.summary()

tasks = parser.tasks
print(tasks[["task_id", "task_code", "task_name"]].head())
```

## Tests

See `tests/test_xer_parser.py` — 22 tests covering table extraction, data type conversions, convenience properties, relationship data, and summary output.
