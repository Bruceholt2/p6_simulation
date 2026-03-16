"""Tests for the XER parser module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.xer_parser import XERParser

# A minimal XER file with 1 project, 1 calendar, 5 activities, and 4 FS relationships
SAMPLE_XER = (
    "%T\tPROJECT\n"
    "%F\tproj_id\tproj_short_name\tlast_recalc_date\n"
    "%R\t100\tTESTPROJ\t2025-06-01 08:00\n"
    "%T\tCALENDAR\n"
    "%F\tclndr_id\tclndr_name\tclndr_data\n"
    "%R\t1\tStandard 5-day\t(0||1(0|7(0|||0800|1700|1())))\n"
    "%T\tTASK\n"
    "%F\ttask_id\tproj_id\ttask_code\ttask_name\ttask_type\tstatus_code\t"
    "total_float_hr_cnt\torig_dur_hr_cnt\tremain_dur_hr_cnt\t"
    "target_start_date\ttarget_end_date\tearly_start_date\tearly_end_date\t"
    "late_start_date\tlate_end_date\tclndr_id\tphys_complete_pct\n"
    "%R\t1001\t100\tA1000\tMobilization\tTT_Task\tTK_NotStart\t0\t80\t80\t"
    "2025-07-01 08:00\t2025-07-11 17:00\t2025-07-01 08:00\t2025-07-11 17:00\t"
    "2025-07-01 08:00\t2025-07-11 17:00\t1\t0\n"
    "%R\t1002\t100\tA1010\tSite Preparation\tTT_Task\tTK_NotStart\t0\t120\t120\t"
    "2025-07-14 08:00\t2025-07-28 17:00\t2025-07-14 08:00\t2025-07-28 17:00\t"
    "2025-07-14 08:00\t2025-07-28 17:00\t1\t0\n"
    "%R\t1003\t100\tA1020\tFoundation\tTT_Task\tTK_NotStart\t0\t200\t200\t"
    "2025-07-29 08:00\t2025-08-22 17:00\t2025-07-29 08:00\t2025-08-22 17:00\t"
    "2025-07-29 08:00\t2025-08-22 17:00\t1\t0\n"
    "%R\t1004\t100\tA1030\tStructural Steel\tTT_Task\tTK_NotStart\t0\t160\t160\t"
    "2025-08-25 08:00\t2025-09-12 17:00\t2025-08-25 08:00\t2025-09-12 17:00\t"
    "2025-08-25 08:00\t2025-09-12 17:00\t1\t0\n"
    "%R\t1005\t100\tA1040\tCommissioning\tTT_Mile\tTK_NotStart\t0\t0\t0\t"
    "2025-09-15 08:00\t2025-09-15 08:00\t2025-09-15 08:00\t2025-09-15 08:00\t"
    "2025-09-15 08:00\t2025-09-15 08:00\t1\t0\n"
    "%T\tTASKPRED\n"
    "%F\ttask_pred_id\ttask_id\tpred_task_id\tpred_type\tlag_hr_cnt\n"
    "%R\t5001\t1002\t1001\tPR_FS\t0\n"
    "%R\t5002\t1003\t1002\tPR_FS\t0\n"
    "%R\t5003\t1004\t1003\tPR_FS\t0\n"
    "%R\t5004\t1005\t1004\tPR_FS\t0\n"
    "%T\tRSRC\n"
    "%F\trsrc_id\trsrc_name\trsrc_short_name\trsrc_type\n"
    "%R\t201\tCrane Operator\tCRN-OP\tRT_Labor\n"
    "%T\tTASKRSRC\n"
    "%F\ttaskrsrc_id\ttask_id\trsrc_id\ttarget_qty_per_hr\ttarget_cost\n"
    "%R\t3001\t1004\t201\t1.0\t25000\n"
    "%E\n"
)


@pytest.fixture
def xer_file(tmp_path: Path) -> Path:
    """Write the sample XER content to a temp file and return its path."""
    file = tmp_path / "test_schedule.xer"
    file.write_text(SAMPLE_XER, encoding="utf-8")
    return file


@pytest.fixture
def parser(xer_file: Path) -> XERParser:
    """Return an XERParser loaded with the sample fixture."""
    return XERParser(xer_file)


class TestTableParsing:
    """Test that all tables are correctly extracted."""

    def test_all_tables_present(self, parser: XERParser) -> None:
        expected = {"PROJECT", "CALENDAR", "TASK", "TASKPRED", "RSRC", "TASKRSRC"}
        assert set(parser.table_names) == expected

    def test_project_table(self, parser: XERParser) -> None:
        df = parser.project
        assert len(df) == 1
        assert df.iloc[0]["proj_short_name"] == "TESTPROJ"

    def test_task_count(self, parser: XERParser) -> None:
        assert len(parser.tasks) == 5

    def test_predecessor_count(self, parser: XERParser) -> None:
        assert len(parser.predecessors) == 4

    def test_calendar_count(self, parser: XERParser) -> None:
        assert len(parser.calendars) == 1

    def test_resource_count(self, parser: XERParser) -> None:
        assert len(parser.resources) == 1

    def test_resource_assignment_count(self, parser: XERParser) -> None:
        assert len(parser.resource_assignments) == 1

    def test_get_table_missing_raises(self, parser: XERParser) -> None:
        with pytest.raises(KeyError, match="NONEXISTENT"):
            parser.get_table("NONEXISTENT")


class TestDataTypes:
    """Test that columns are converted to proper types."""

    def test_task_id_is_integer(self, parser: XERParser) -> None:
        assert parser.tasks["task_id"].dtype == pd.Int64Dtype()
        assert parser.tasks["task_id"].iloc[0] == 1001

    def test_duration_is_numeric(self, parser: XERParser) -> None:
        durations = parser.tasks["orig_dur_hr_cnt"]
        assert pd.api.types.is_numeric_dtype(durations)
        assert durations.iloc[0] == 80.0

    def test_float_is_numeric(self, parser: XERParser) -> None:
        floats = parser.tasks["total_float_hr_cnt"]
        assert pd.api.types.is_numeric_dtype(floats)

    def test_lag_is_numeric(self, parser: XERParser) -> None:
        lags = parser.predecessors["lag_hr_cnt"]
        assert pd.api.types.is_numeric_dtype(lags)
        assert lags.iloc[0] == 0.0

    def test_date_columns_are_datetime(self, parser: XERParser) -> None:
        date_cols = [
            "target_start_date",
            "target_end_date",
            "early_start_date",
            "early_end_date",
            "late_start_date",
            "late_end_date",
        ]
        for col in date_cols:
            assert pd.api.types.is_datetime64_any_dtype(parser.tasks[col]), (
                f"{col} should be datetime"
            )

    def test_project_date_is_datetime(self, parser: XERParser) -> None:
        assert pd.api.types.is_datetime64_any_dtype(parser.project["last_recalc_date"])

    def test_target_cost_is_numeric(self, parser: XERParser) -> None:
        costs = parser.resource_assignments["target_cost"]
        assert pd.api.types.is_numeric_dtype(costs)
        assert costs.iloc[0] == 25000.0


class TestConvenienceProperties:
    """Test that convenience properties return correct tables."""

    def test_tasks_property(self, parser: XERParser) -> None:
        assert parser.tasks.equals(parser.get_table("TASK"))

    def test_predecessors_property(self, parser: XERParser) -> None:
        assert parser.predecessors.equals(parser.get_table("TASKPRED"))

    def test_calendars_property(self, parser: XERParser) -> None:
        assert parser.calendars.equals(parser.get_table("CALENDAR"))

    def test_resources_property(self, parser: XERParser) -> None:
        assert parser.resources.equals(parser.get_table("RSRC"))


class TestRelationshipData:
    """Test the parsed relationship network."""

    def test_all_relationships_are_fs(self, parser: XERParser) -> None:
        preds = parser.predecessors
        assert (preds["pred_type"] == "PR_FS").all()

    def test_relationship_chain(self, parser: XERParser) -> None:
        """Verify the linear chain: 1001 -> 1002 -> 1003 -> 1004 -> 1005."""
        preds = parser.predecessors
        edges = list(zip(preds["pred_task_id"], preds["task_id"]))
        assert (1001, 1002) in edges
        assert (1002, 1003) in edges
        assert (1003, 1004) in edges
        assert (1004, 1005) in edges


class TestSummary:
    """Test the summary output."""

    def test_summary_returns_string(self, parser: XERParser, capsys: pytest.CaptureFixture[str]) -> None:
        result = parser.summary()
        assert "Activities: 5" in result
        assert "Relationships: 4" in result
        assert "Calendars: 1" in result
