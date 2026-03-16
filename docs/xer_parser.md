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

- **Date columns** (`*_date`, `*_date2`, etc.) -- `datetime64` (format `%Y-%m-%d %H:%M`)
- **Numeric columns** (`*_hr_cnt`, `*_qty`, `*_pct`, `*_cost`, `*_cnt`, `*_per_hr`) -- `float64`
- **Exact-name numeric columns** (`cost_per_qty`, `base_exch_rate`, `ann_dscnt_rate_pct`) -- `float64`
- **ID columns** (`*_id`, excluding `guid`/`tmpl_guid`) -- nullable `Int64`

### Internal Details

- `_parse()` iterates line-by-line, recognizing `%T` (table name), `%F` (field names), `%R` (row data), and `%E` (end-of-file) markers.
- `_store_table()` pads or trims rows to match the field count, strips whitespace, and applies type conversions.
- Handles files missing the `%E` end marker gracefully.

### Usage

```python
from src.xer_parser import XERParser

parser = XERParser("data/sample-5272.xer")
parser.summary()

tasks = parser.tasks
print(tasks[["task_id", "task_code", "task_name"]].head())
```

## Tests

See `tests/test_xer_parser.py` -- tests covering table extraction, data type conversions, convenience properties, relationship data, and summary output.
