# Portfolio Loader Requirements Document

**Module:** `src/portfolio_loader.py`
**Last Updated:** 2026-03-16

---

## 1. Module Overview

The `portfolio_loader` module merges multiple Primavera P6 XER files from a directory into a single unified portfolio. It scans a directory for XER files, parses each one using `XERParser`, and concatenates all like-named tables across files. The resulting `PortfolioLoader` instance presents the same interface as `XERParser`, allowing downstream modules (activity network, calendar engine, simulation engine) to consume the merged data transparently.

---

## 2. Functional Requirements

| ID | Requirement |
|----|-------------|
| FR-PFL-001 | The `PortfolioLoader` class SHALL accept a directory path (string or `pathlib.Path`) and an optional glob pattern, and automatically load and merge all matching XER files upon instantiation. |
| FR-PFL-002 | The default file pattern SHALL be `*.[xXzZ][eE][rR]`, matching `.xer` and `.zer` file extensions in a case-insensitive manner. |
| FR-PFL-003 | The `_load_portfolio` method SHALL scan the directory using `sorted(self.data_dir.glob(file_pattern))` to enumerate matching files in alphabetical order. |
| FR-PFL-004 | If no XER files are found matching the pattern, the loader SHALL raise a `FileNotFoundError` with a message including the directory path and pattern. |
| FR-PFL-005 | For each XER file found, the loader SHALL create an `XERParser` instance to parse it, increment the file counter, and record the file name. |
| FR-PFL-006 | For each table in each parsed XER file, the loader SHALL add a `_source_file` column containing the originating file name for traceability. |
| FR-PFL-007 | The loader SHALL collect all DataFrames for each table name across all files and concatenate them using `pd.concat` with `ignore_index=True`. |
| FR-PFL-008 | The `get_table` method SHALL return the merged DataFrame for a given table name. If the table was not found in any XER file, it SHALL raise a `KeyError` with available table names. |
| FR-PFL-009 | The `table_names` property SHALL return a list of all merged table names. |
| FR-PFL-010 | The `project` property SHALL return the merged `PROJECT` table. |
| FR-PFL-011 | The `tasks` property SHALL return the merged `TASK` table. |
| FR-PFL-012 | The `predecessors` property SHALL return the merged `TASKPRED` table. |
| FR-PFL-013 | The `calendars` property SHALL return the merged `CALENDAR` table, deduplicated by `clndr_id` keeping the first occurrence. |
| FR-PFL-014 | The `resources` property SHALL return the merged `RSRC` table, deduplicated by `rsrc_id` keeping the first occurrence. |
| FR-PFL-015 | The `resource_assignments` property SHALL return the merged `TASKRSRC` table (no deduplication). |
| FR-PFL-016 | The `file_count` property SHALL return the number of XER files loaded. |
| FR-PFL-017 | The `file_names` property SHALL return a list of the names of all loaded XER files. |
| FR-PFL-018 | The `summary` method SHALL return and print a multi-line string showing the directory path, number of files loaded, each file name, and counts for Projects, Activities, Relationships, Calendars, Resources, Resource Assignments, Resource Rates, and all table names. |

---

## 3. Input Requirements

| Input | Format | Validation |
|-------|--------|------------|
| `data_dir` | String or `pathlib.Path` pointing to a directory | Must contain at least one file matching the glob pattern; otherwise `FileNotFoundError` is raised. |
| `file_pattern` | Glob pattern string | Defaults to `*.[xXzZ][eE][rR]`. No explicit validation on pattern syntax. |
| Individual XER files | Valid P6 XER format files | Each file is parsed by `XERParser`; parsing errors propagate from `XERParser`. |

---

## 4. Output Requirements

| Output | Type | Description |
|--------|------|-------------|
| Merged tables | `dict[str, pd.DataFrame]` | Internal dictionary mapping table names to concatenated DataFrames. |
| `get_table()` return | `pd.DataFrame` | Merged DataFrame for the requested table, with `_source_file` traceability column. |
| `calendars` property | `pd.DataFrame` | Deduplicated by `clndr_id` (first occurrence kept). |
| `resources` property | `pd.DataFrame` | Deduplicated by `rsrc_id` (first occurrence kept). |
| `summary()` return | `str` | Multi-line summary string (also printed to stdout). |

---

## 5. Data Requirements

### Added Columns

| Column | Type | Description |
|--------|------|-------------|
| `_source_file` | `str` | Added to every row in every table; contains the name of the originating XER file. |

### Deduplication Rules

| Table | Deduplication Key | Strategy |
|-------|-------------------|----------|
| `CALENDAR` | `clndr_id` | `drop_duplicates(subset=["clndr_id"], keep="first")` |
| `RSRC` | `rsrc_id` | `drop_duplicates(subset=["rsrc_id"], keep="first")` |
| All other tables | None | No deduplication; all rows from all files are retained. |

---

## 6. Interface Requirements

### Dependencies (imports)
- `pathlib.Path` -- directory and file path handling
- `pandas` -- DataFrame concatenation and deduplication
- `src.xer_parser.XERParser` -- parses individual XER files

### Dependents (modules that import this module)
- `run_simulation.py` -- creates `PortfolioLoader` as the primary data source

### API Compatibility
- `PortfolioLoader` exposes the same interface as `XERParser` (`get_table`, `table_names`, `tasks`, `predecessors`, `calendars`, `resources`, `resource_assignments` properties), making it a drop-in replacement for single-file parsing. Downstream modules (`ActivityNetwork`, `CalendarEngine`, `SimulationEngine`) accept either.

---

## 7. Performance Requirements

| ID | Requirement |
|----|-------------|
| PR-PFL-001 | All XER files are parsed and merged at construction time. Subsequent table access is a dictionary lookup. |
| PR-PFL-002 | Files are sorted alphabetically to ensure deterministic merge order across runs. |
| PR-PFL-003 | DataFrames are copied (`parser.get_table(table_name).copy()`) before adding the `_source_file` column to avoid modifying the original parser's data. |

---

## 8. Error Handling Requirements

| ID | Condition | Behavior |
|----|-----------|----------|
| EH-PFL-001 | No XER files found in directory | `FileNotFoundError` raised with directory path and pattern. |
| EH-PFL-002 | Requested table not found in merged data | `KeyError` raised with list of available tables. |
| EH-PFL-003 | Individual XER file parsing fails | Error propagates from `XERParser`; no per-file error suppression. |
| EH-PFL-004 | A table exists in some files but not others | Only files containing the table contribute rows; files without that table are silently skipped for that table name. |

---

## 9. Constraints and Assumptions

| ID | Constraint/Assumption |
|----|----------------------|
| CA-PFL-001 | All XER files in the directory represent projects that should be treated as a single portfolio schedule. |
| CA-PFL-002 | Calendar definitions (`clndr_id`) are assumed to be consistent across files; when duplicates exist, the first file's definition (alphabetically) is kept. |
| CA-PFL-003 | Resource definitions (`rsrc_id`) are assumed to be consistent across files; when duplicates exist, the first file's definition is kept. |
| CA-PFL-004 | Task IDs, relationship IDs, and other non-deduplicated identifiers are assumed to be unique across files, or the downstream modules handle any collisions. |
| CA-PFL-005 | The directory is expected to contain only relevant XER/ZER files matching the pattern; no filtering by file content is performed. |
| CA-PFL-006 | The merge order is alphabetical by file name, which affects which duplicate calendar/resource definition is retained. |
