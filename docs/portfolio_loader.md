# portfolio_loader.py

**Location:** `src/portfolio_loader.py`

## Purpose

Reads all XER files from a directory, parses each one using `XERParser`, and merges like-named tables into a single portfolio of DataFrames. The merged portfolio exposes the same interface as `XERParser` (properties like `tasks`, `predecessors`, `calendars`, etc.), so it can be passed directly to `ActivityNetwork`, `CalendarEngine`, and `SimulationEngine`.

## Class: PortfolioLoader

### Constructor

```python
PortfolioLoader(
    data_dir: str | Path,
    file_pattern: str = "*.[xXzZ][eE][rR]",  # Matches .xer and .zer (case-insensitive)
)
```

- Scans `data_dir` for files matching the glob pattern.
- Raises `FileNotFoundError` if no matching files are found.
- Parses each file with `XERParser` and concatenates all like-named tables.
- Tags every row with a `_source_file` column for traceability.

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_table(table_name)` | `pd.DataFrame` | Returns the merged DataFrame for a named table. Raises `KeyError` if not found in any file. |
| `summary()` | `str` | Prints and returns a summary: file count, file names, and merged table counts. |

### Properties

| Property | Returns | Description |
|----------|---------|-------------|
| `table_names` | `list[str]` | All merged table names. |
| `project` | `pd.DataFrame` | Merged PROJECT table. |
| `tasks` | `pd.DataFrame` | Merged TASK table. |
| `predecessors` | `pd.DataFrame` | Merged TASKPRED table. |
| `calendars` | `pd.DataFrame` | Merged CALENDAR table, deduplicated by `clndr_id` (keeps first). |
| `resources` | `pd.DataFrame` | Merged RSRC table, deduplicated by `rsrc_id` (keeps first). |
| `resource_assignments` | `pd.DataFrame` | Merged TASKRSRC table. |
| `file_count` | `int` | Number of XER files loaded. |
| `file_names` | `list[str]` | Names of all loaded XER files. |

### Deduplication

- `calendars` is deduplicated by `clndr_id` because multiple XER files may reference the same calendar definitions. The first occurrence is kept.
- `resources` is deduplicated by `rsrc_id` for the same reason.
- Other tables (TASK, TASKPRED, PROJECT, TASKRSRC) are fully concatenated since each file contributes distinct rows.

### Source File Tracking

Every row in every merged table includes a `_source_file` column containing the original XER filename. This allows downstream analysis to trace any activity, relationship, or resource back to its source file.

### Usage

```python
from src.portfolio_loader import PortfolioLoader
from src.activity_network import ActivityNetwork
from src.simulation_engine import SimulationEngine

# Load all XER files from the data directory
portfolio = PortfolioLoader("data")
portfolio.summary()

# Use exactly like an XERParser
network = ActivityNetwork(portfolio)
engine = SimulationEngine(portfolio, resource_constrained=False)
result = engine.run()
```

### Compatibility

`PortfolioLoader` exposes the same API surface as `XERParser`:
- `get_table(name)`, `table_names`, `project`, `tasks`, `predecessors`, `calendars`, `resources`, `resource_assignments`, `summary()`

This means any code that accepts an `XERParser` will also work with a `PortfolioLoader` (duck typing).
