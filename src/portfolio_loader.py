"""Portfolio loader for merging multiple P6 XER files.

Reads all XER files from a directory, parses each one, and merges
like-named tables into a single portfolio of DataFrames. The merged
portfolio can then be passed to the simulation engine as if it were
a single XER file.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.xer_parser import XERParser


class PortfolioLoader:
    """Loads and merges multiple XER files into a unified portfolio.

    Scans a directory for XER files, parses each one using XERParser,
    and concatenates all like-named tables (e.g., all TASK tables become
    one portfolio TASK table). The result acts as a single XERParser
    with the merged data.

    Args:
        data_dir: Path to the directory containing XER files.
        file_pattern: Glob pattern to match XER files.
            Defaults to matching .xer and .zer extensions.
    """

    def __init__(
        self,
        data_dir: str | Path,
        file_pattern: str = "*.[xXzZ][eE][rR]",
    ) -> None:
        self.data_dir = Path(data_dir)
        self._tables: dict[str, pd.DataFrame] = {}
        self._file_count = 0
        self._file_names: list[str] = []
        self._load_portfolio(file_pattern)

    def _load_portfolio(self, file_pattern: str) -> None:
        """Parse all XER files and merge like-named tables."""
        xer_files = sorted(self.data_dir.glob(file_pattern))

        if not xer_files:
            raise FileNotFoundError(
                f"No XER files found in {self.data_dir} "
                f"matching pattern '{file_pattern}'"
            )

        # Collect DataFrames per table name across all files
        table_frames: dict[str, list[pd.DataFrame]] = {}

        for xer_path in xer_files:
            parser = XERParser(xer_path)
            self._file_count += 1
            self._file_names.append(xer_path.name)

            for table_name in parser.table_names:
                df = parser.get_table(table_name).copy()
                # Tag each row with its source file for traceability
                df["_source_file"] = xer_path.name
                table_frames.setdefault(table_name, []).append(df)

        # Concatenate all frames per table
        for table_name, frames in table_frames.items():
            merged = pd.concat(frames, ignore_index=True)
            self._tables[table_name] = merged

    def get_table(self, table_name: str) -> pd.DataFrame:
        """Return the merged DataFrame for a given table name.

        Args:
            table_name: The XER table name (e.g., 'TASK', 'TASKPRED').

        Returns:
            The merged DataFrame across all XER files.

        Raises:
            KeyError: If the table was not found in any XER file.
        """
        if table_name not in self._tables:
            raise KeyError(
                f"Table '{table_name}' not found. "
                f"Available tables: {list(self._tables.keys())}"
            )
        return self._tables[table_name]

    @property
    def table_names(self) -> list[str]:
        """List of all merged table names."""
        return list(self._tables.keys())

    @property
    def project(self) -> pd.DataFrame:
        """Merged PROJECT table."""
        return self.get_table("PROJECT")

    @property
    def tasks(self) -> pd.DataFrame:
        """Merged TASK table."""
        return self.get_table("TASK")

    @property
    def predecessors(self) -> pd.DataFrame:
        """Merged TASKPRED table."""
        return self.get_table("TASKPRED")

    @property
    def calendars(self) -> pd.DataFrame:
        """Merged CALENDAR table — deduplicated by clndr_id."""
        df = self.get_table("CALENDAR")
        return df.drop_duplicates(subset=["clndr_id"], keep="first")

    @property
    def resources(self) -> pd.DataFrame:
        """Merged RSRC table — deduplicated by rsrc_id."""
        df = self.get_table("RSRC")
        return df.drop_duplicates(subset=["rsrc_id"], keep="first")

    @property
    def resource_assignments(self) -> pd.DataFrame:
        """Merged TASKRSRC table."""
        return self.get_table("TASKRSRC")

    @property
    def file_count(self) -> int:
        """Number of XER files loaded."""
        return self._file_count

    @property
    def file_names(self) -> list[str]:
        """Names of all loaded XER files."""
        return self._file_names

    def summary(self) -> str:
        """Return a summary of the merged portfolio.

        Returns:
            A multi-line string with portfolio statistics.
        """
        lines = [
            f"Portfolio: {self.data_dir}",
            f"  XER files loaded: {self._file_count}",
        ]
        for name in self._file_names:
            lines.append(f"    - {name}")
        lines.append("")

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

        lines.append("")
        lines.append(f"  All tables: {', '.join(self.table_names)}")

        summary_text = "\n".join(lines)
        print(summary_text)
        return summary_text
