"""XER file parser for Primavera P6 schedule data.

Reads P6 XER export files and extracts schedule tables into pandas DataFrames
with proper data types for dates, numerics, and identifiers.
"""

from __future__ import annotations

from pathlib import Path

import re

import pandas as pd


# Suffixes that indicate a date column (must end with _date)
_DATE_SUFFIX = "_date"

# Patterns that indicate a numeric column (float)
_NUMERIC_SUFFIXES = ("_hr_cnt", "_qty", "_pct", "_cost", "_cnt", "_per_hr")

# Exact-name numeric columns that don't match the suffix patterns
_NUMERIC_EXACT = {
    "cost_per_qty",
    "base_exch_rate",
    "ann_dscnt_rate_pct",
}

# Suffixes that indicate an integer ID column
_ID_SUFFIX = "_id"

# Columns ending in _id that are NOT integer IDs (they are string identifiers)
_ID_EXCLUDE = {"guid", "tmpl_guid"}


class XERParser:
    """Parses a Primavera P6 XER file into pandas DataFrames.

    Args:
        file_path: Path to the XER file to parse.
    """

    def __init__(self, file_path: str | Path) -> None:
        self.file_path = Path(file_path)
        self._tables: dict[str, pd.DataFrame] = {}
        self._parse()

    def _read_file(self) -> str:
        """Read the XER file, trying UTF-8 first then Latin-1."""
        try:
            return self.file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, UnicodeError):
            return self.file_path.read_text(encoding="latin-1")

    def _parse(self) -> None:
        """Parse the XER file contents into DataFrames."""
        content = self._read_file()
        lines = content.splitlines()

        current_table: str | None = None
        current_fields: list[str] = []
        current_rows: list[list[str]] = []

        for line in lines:
            if line.startswith("%T"):
                # Save previous table if any
                if current_table is not None and current_fields:
                    self._store_table(current_table, current_fields, current_rows)
                # Start new table
                parts = line.split("\t")
                current_table = parts[1].strip() if len(parts) > 1 else None
                current_fields = []
                current_rows = []

            elif line.startswith("%F"):
                current_fields = [f.strip() for f in line.split("\t")[1:]]

            elif line.startswith("%R") and current_table is not None:
                values = line.split("\t")[1:]
                current_rows.append(values)

            elif line.startswith("%E"):
                # End of file — save last table
                if current_table is not None and current_fields:
                    self._store_table(current_table, current_fields, current_rows)
                break

        # Handle files without %E marker
        if current_table is not None and current_fields:
            if current_table not in self._tables:
                self._store_table(current_table, current_fields, current_rows)

    def _store_table(
        self,
        table_name: str,
        fields: list[str],
        rows: list[list[str]],
    ) -> None:
        """Create a DataFrame from parsed rows and apply type conversions."""
        if not rows:
            self._tables[table_name] = pd.DataFrame(columns=fields)
            return

        # Pad or trim rows to match field count
        n_fields = len(fields)
        normalized = []
        for row in rows:
            if len(row) < n_fields:
                row = row + [""] * (n_fields - len(row))
            elif len(row) > n_fields:
                row = row[:n_fields]
            normalized.append(row)

        df = pd.DataFrame(normalized, columns=fields)

        # Strip whitespace from string values
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].str.strip()

        # Convert date columns (any column ending in _date or matching _date\d+)
        for col in df.columns:
            if (
                (col.endswith(_DATE_SUFFIX) or re.match(r".*_date\d*$", col))
                and col not in _ID_EXCLUDE
            ):
                df[col] = pd.to_datetime(df[col], format="%Y-%m-%d %H:%M", errors="coerce")

        # Convert numeric columns (by suffix pattern or exact match)
        for col in df.columns:
            if (
                any(col.endswith(s) for s in _NUMERIC_SUFFIXES)
                or col in _NUMERIC_EXACT
            ):
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Convert ID columns to nullable integer (any column ending in _id)
        for col in df.columns:
            if col.endswith(_ID_SUFFIX) and col not in _ID_EXCLUDE:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

        self._tables[table_name] = df

    def get_table(self, table_name: str) -> pd.DataFrame:
        """Return the DataFrame for a given table name.

        Args:
            table_name: The XER table name (e.g., 'TASK', 'TASKPRED').

        Returns:
            The parsed DataFrame for that table.

        Raises:
            KeyError: If the table was not found in the XER file.
        """
        if table_name not in self._tables:
            raise KeyError(
                f"Table '{table_name}' not found. "
                f"Available tables: {list(self._tables.keys())}"
            )
        return self._tables[table_name]

    @property
    def table_names(self) -> list[str]:
        """List of all table names found in the XER file."""
        return list(self._tables.keys())

    @property
    def project(self) -> pd.DataFrame:
        """PROJECT table — project-level metadata."""
        return self.get_table("PROJECT")

    @property
    def tasks(self) -> pd.DataFrame:
        """TASK table — schedule activities."""
        return self.get_table("TASK")

    @property
    def predecessors(self) -> pd.DataFrame:
        """TASKPRED table — activity relationships."""
        return self.get_table("TASKPRED")

    @property
    def calendars(self) -> pd.DataFrame:
        """CALENDAR table — calendar definitions."""
        return self.get_table("CALENDAR")

    @property
    def resources(self) -> pd.DataFrame:
        """RSRC table — resource definitions."""
        return self.get_table("RSRC")

    @property
    def resource_assignments(self) -> pd.DataFrame:
        """TASKRSRC table — resource assignments to activities."""
        return self.get_table("TASKRSRC")

    def summary(self) -> str:
        """Return a summary of parsed schedule data.

        Returns:
            A multi-line string summarizing the number of projects, activities,
            relationships, calendars, and resources parsed.
        """
        lines = [f"XER File: {self.file_path.name}", ""]

        counts = {
            "Projects": "PROJECT",
            "Activities": "TASK",
            "Relationships": "TASKPRED",
            "Calendars": "CALENDAR",
            "Resources": "RSRC",
            "Resource Assignments": "TASKRSRC",
            "Resource Rates": "RSRCRATE",
        }

        for label, table_name in counts.items():
            if table_name in self._tables:
                lines.append(f"  {label}: {len(self._tables[table_name])}")
            else:
                lines.append(f"  {label}: 0 (table not present)")

        summary_text = "\n".join(lines)
        print(summary_text)
        return summary_text
