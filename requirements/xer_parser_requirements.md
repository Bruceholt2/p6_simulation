# XER Parser Requirements Document

**Module:** `src/xer_parser.py`
**Last Updated:** 2026-03-16

---

## 1. Module Overview

The `xer_parser` module is responsible for reading Primavera P6 XER export files and parsing their tab-delimited contents into structured pandas DataFrames. It serves as the foundational data-ingestion layer for the entire simulation system. All downstream modules (portfolio loader, activity network, calendar engine, simulation engine) depend on this module to provide correctly typed schedule data.

---

## 2. Functional Requirements

| ID | Requirement |
|----|-------------|
| FR-XER-001 | The `XERParser` class SHALL accept a file path (string or `pathlib.Path`) and automatically parse the XER file upon instantiation. |
| FR-XER-002 | The `_read_file` method SHALL attempt to read the file using UTF-8 encoding first. If a `UnicodeDecodeError` or `UnicodeError` occurs, it SHALL fall back to Latin-1 encoding. |
| FR-XER-003 | The `_parse` method SHALL iterate through all lines of the file and identify table boundaries using the `%T` line prefix (table name), `%F` prefix (field definitions), `%R` prefix (data rows), and `%E` prefix (end of file). |
| FR-XER-004 | When a `%T` line is encountered, the parser SHALL save any previously accumulated table and begin tracking a new table whose name is extracted from the second tab-delimited field. |
| FR-XER-005 | When a `%F` line is encountered, the parser SHALL extract all field names by splitting on tab and stripping whitespace from each field name (skipping the first element which is the `%F` marker). |
| FR-XER-006 | When a `%R` line is encountered and a current table is being tracked, the parser SHALL extract all values by splitting on tab (skipping the first element which is the `%R` marker) and append them to the current table's row list. |
| FR-XER-007 | When a `%E` line is encountered, the parser SHALL save the last accumulated table and stop parsing. |
| FR-XER-008 | If the file does not contain a `%E` marker, the parser SHALL still save the last accumulated table after processing all lines, provided the table has not already been stored. |
| FR-XER-009 | The `_store_table` method SHALL create a pandas DataFrame from the accumulated rows and field names. If no rows exist, it SHALL create an empty DataFrame with the given column names. |
| FR-XER-010 | The `_store_table` method SHALL normalize row lengths: rows shorter than the field count SHALL be padded with empty strings; rows longer SHALL be trimmed to match the field count. |
| FR-XER-011 | The `_store_table` method SHALL strip leading and trailing whitespace from all string-typed columns. |
| FR-XER-012 | The `_store_table` method SHALL convert columns ending in `_date` (or matching the regex `.*_date\d*$`) to datetime using the format `%Y-%m-%d %H:%M`, with invalid values coerced to `NaT`. Columns in the `_ID_EXCLUDE` set SHALL be excluded from date conversion. |
| FR-XER-013 | The `_store_table` method SHALL convert columns matching any of the numeric suffixes (`_hr_cnt`, `_qty`, `_pct`, `_cost`, `_cnt`, `_per_hr`) or in the `_NUMERIC_EXACT` set (`cost_per_qty`, `base_exch_rate`, `ann_dscnt_rate_pct`) to float using `pd.to_numeric` with `errors="coerce"`. |
| FR-XER-014 | The `_store_table` method SHALL convert columns ending in `_id` to nullable integer (`Int64`) type, except for columns matching the `_ID_EXCLUDE` set (`guid`, `tmpl_guid`). |
| FR-XER-015 | The `get_table` method SHALL return the DataFrame for a given table name. If the table does not exist, it SHALL raise a `KeyError` with a message listing available tables. |
| FR-XER-016 | The `table_names` property SHALL return a list of all table names found in the parsed XER file. |
| FR-XER-017 | The `project` property SHALL return the DataFrame for the `PROJECT` table. |
| FR-XER-018 | The `tasks` property SHALL return the DataFrame for the `TASK` table. |
| FR-XER-019 | The `predecessors` property SHALL return the DataFrame for the `TASKPRED` table. |
| FR-XER-020 | The `calendars` property SHALL return the DataFrame for the `CALENDAR` table. |
| FR-XER-021 | The `resources` property SHALL return the DataFrame for the `RSRC` table. |
| FR-XER-022 | The `resource_assignments` property SHALL return the DataFrame for the `TASKRSRC` table. |
| FR-XER-023 | The `summary` method SHALL return and print a multi-line string summarizing counts of Projects, Activities, Relationships, Calendars, Resources, Resource Assignments, and Resource Rates. Tables not present SHALL be reported as "0 (table not present)". |

---

## 3. Input Requirements

| Input | Format | Validation |
|-------|--------|------------|
| `file_path` | String or `pathlib.Path` pointing to a `.xer` file | Must be a valid file path. No explicit existence check; file read will raise OS-level errors. |
| XER file content | Tab-delimited text file with `%T`, `%F`, `%R`, `%E` line prefixes | No schema validation performed. Parser is tolerant of missing fields and extra fields. |
| File encoding | UTF-8 or Latin-1 | UTF-8 tried first; Latin-1 used as fallback on decode errors. |
| Date values in XER | Format: `YYYY-MM-DD HH:MM` | Invalid dates coerced to `NaT` (not-a-time). |
| Numeric values in XER | Decimal or integer strings | Invalid numerics coerced to `NaN`. |
| ID values in XER | Integer strings | Invalid IDs coerced to `<NA>` (nullable integer). |

---

## 4. Output Requirements

| Output | Type | Description |
|--------|------|-------------|
| Parsed tables | `dict[str, pd.DataFrame]` | Internal dictionary mapping table names to DataFrames with proper types. |
| `get_table()` return | `pd.DataFrame` | Single DataFrame for the requested table. |
| `table_names` return | `list[str]` | List of all parsed table name strings. |
| `summary()` return | `str` | Multi-line summary string (also printed to stdout). |

---

## 5. Data Requirements

### Column Type Classification Rules

| Category | Identification Rule | Target Type |
|----------|-------------------|-------------|
| Date columns | Column name ends with `_date` or matches `.*_date\d*$` (excluding `_ID_EXCLUDE` members) | `datetime64[ns]` |
| Numeric columns (float) | Column name ends with `_hr_cnt`, `_qty`, `_pct`, `_cost`, `_cnt`, `_per_hr`; or column name is in `_NUMERIC_EXACT` | `float64` |
| ID columns (integer) | Column name ends with `_id` (excluding `guid`, `tmpl_guid`) | `Int64` (nullable) |
| String columns | All other columns | `object` (string) |

### Module-Level Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `_DATE_SUFFIX` | `"_date"` | Suffix identifying date columns |
| `_NUMERIC_SUFFIXES` | `("_hr_cnt", "_qty", "_pct", "_cost", "_cnt", "_per_hr")` | Suffixes identifying float columns |
| `_NUMERIC_EXACT` | `{"cost_per_qty", "base_exch_rate", "ann_dscnt_rate_pct"}` | Exact column names for float conversion |
| `_ID_SUFFIX` | `"_id"` | Suffix identifying integer ID columns |
| `_ID_EXCLUDE` | `{"guid", "tmpl_guid"}` | ID-suffix columns that should remain strings |

---

## 6. Interface Requirements

### Dependencies (imports)
- `pathlib.Path` -- file path handling
- `re` -- regex matching for date column patterns
- `pandas` -- DataFrame construction and type conversion

### Dependents (modules that import this module)
- `src.portfolio_loader` -- imports `XERParser` to parse individual XER files
- `src.activity_network` -- imports `XERParser` type for constructor parameter
- `src.calendar_engine` -- imports `XERParser` type for constructor parameter
- `src.simulation_engine` -- imports `XERParser` type for constructor parameter

### API Contract
- The `XERParser` instance exposes a consistent interface (`get_table`, `table_names`, named properties for `tasks`, `predecessors`, `calendars`, `resources`, `resource_assignments`) that is also mirrored by `PortfolioLoader`, allowing both to be used interchangeably by downstream modules.

---

## 7. Performance Requirements

| ID | Requirement |
|----|-------------|
| PR-XER-001 | Parsing is performed once at construction time. Subsequent table access is a dictionary lookup with no re-parsing. |
| PR-XER-002 | Type conversions (date, numeric, ID) are applied column-wise using vectorized pandas operations, not row-by-row iteration. |

---

## 8. Error Handling Requirements

| ID | Condition | Behavior |
|----|-----------|----------|
| EH-XER-001 | File cannot be read as UTF-8 | Falls back to Latin-1 encoding silently. |
| EH-XER-002 | Date value cannot be parsed | Coerced to `NaT` (pandas not-a-time) via `errors="coerce"`. |
| EH-XER-003 | Numeric value cannot be parsed | Coerced to `NaN` via `errors="coerce"`. |
| EH-XER-004 | ID value cannot be parsed as integer | Coerced to `<NA>` via `errors="coerce"` then cast to `Int64`. |
| EH-XER-005 | Row has fewer fields than the header | Padded with empty strings to match field count. |
| EH-XER-006 | Row has more fields than the header | Trimmed to match field count. |
| EH-XER-007 | Requested table not found in parsed data | `KeyError` raised with list of available tables. |
| EH-XER-008 | File has no `%E` marker | Last table is still saved after all lines are processed. |

---

## 9. Constraints and Assumptions

| ID | Constraint/Assumption |
|----|----------------------|
| CA-XER-001 | XER files follow the Primavera P6 export format with `%T`, `%F`, `%R`, `%E` line prefixes and tab-delimited fields. |
| CA-XER-002 | The file encoding is either UTF-8 or Latin-1; other encodings are not supported. |
| CA-XER-003 | Date columns use the format `YYYY-MM-DD HH:MM` (no seconds). |
| CA-XER-004 | The `%T` line contains the table name as the second tab-delimited value. |
| CA-XER-005 | Table names are unique within a single XER file; if duplicated, only the last occurrence is stored. |
| CA-XER-006 | The parser does not validate the semantic correctness of data (e.g., whether task IDs are unique or relationships reference valid tasks). |
| CA-XER-007 | The parser assumes the file fits in memory (entire file is read at once via `read_text`). |
