"""Tests for the portfolio loader module."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.portfolio_loader import PortfolioLoader
from src.xer_parser import XERParser


def _make_xer(proj_id: int, proj_name: str, task_id: int) -> str:
    """Build a minimal XER string with one project and one task."""
    return (
        "%T\tPROJECT\n"
        f"%F\tproj_id\tproj_short_name\tlast_recalc_date\n"
        f"%R\t{proj_id}\t{proj_name}\t2025-06-01 08:00\n"
        "%T\tCALENDAR\n"
        "%F\tclndr_id\tclndr_name\tclndr_data\n"
        f"%R\t{proj_id}\tCal-{proj_name}\t\n"
        "%T\tTASK\n"
        "%F\ttask_id\tproj_id\ttask_code\ttask_name\ttask_type\tstatus_code\t"
        "total_float_hr_cnt\torig_dur_hr_cnt\tremain_dur_hr_cnt\tclndr_id\n"
        f"%R\t{task_id}\t{proj_id}\tA1000\tTask-{proj_name}\tTT_Task\t"
        f"TK_NotStart\t0\t80\t80\t{proj_id}\n"
        "%T\tTASKPRED\n"
        "%F\ttask_pred_id\ttask_id\tpred_task_id\tpred_type\tlag_hr_cnt\n"
        "%T\tRSRC\n"
        "%F\trsrc_id\trsrc_name\trsrc_short_name\trsrc_type\n"
        f"%R\t{proj_id + 500}\tRes-{proj_name}\tR-{proj_name}\tRT_Labor\n"
        "%T\tTASKRSRC\n"
        "%F\ttaskrsrc_id\ttask_id\trsrc_id\ttarget_qty_per_hr\ttarget_cost\n"
        "%E\n"
    )


@pytest.fixture
def portfolio_dir(tmp_path: Path) -> Path:
    """Create a temp directory with two XER files."""
    (tmp_path / "project_a.xer").write_text(
        _make_xer(100, "PROJ_A", 1001), encoding="utf-8"
    )
    (tmp_path / "project_b.xer").write_text(
        _make_xer(200, "PROJ_B", 2001), encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def portfolio(portfolio_dir: Path) -> PortfolioLoader:
    """Return a PortfolioLoader from the temp directory."""
    return PortfolioLoader(portfolio_dir)


class TestPortfolioLoading:
    """Test that multiple XER files are loaded and merged."""

    def test_file_count(self, portfolio: PortfolioLoader) -> None:
        assert portfolio.file_count == 2

    def test_file_names(self, portfolio: PortfolioLoader) -> None:
        assert "project_a.xer" in portfolio.file_names
        assert "project_b.xer" in portfolio.file_names

    def test_projects_merged(self, portfolio: PortfolioLoader) -> None:
        assert len(portfolio.project) == 2

    def test_tasks_merged(self, portfolio: PortfolioLoader) -> None:
        assert len(portfolio.tasks) == 2
        task_ids = set(portfolio.tasks["task_id"])
        assert 1001 in task_ids
        assert 2001 in task_ids

    def test_calendars_deduplicated(self, portfolio: PortfolioLoader) -> None:
        # Each file has a unique clndr_id, so both should be present
        assert len(portfolio.calendars) == 2

    def test_resources_deduplicated(self, portfolio: PortfolioLoader) -> None:
        # Each file has a unique rsrc_id, so both should be present
        assert len(portfolio.resources) == 2

    def test_source_file_column(self, portfolio: PortfolioLoader) -> None:
        tasks = portfolio.tasks
        assert "_source_file" in tasks.columns
        sources = set(tasks["_source_file"])
        assert "project_a.xer" in sources
        assert "project_b.xer" in sources

    def test_all_tables_present(self, portfolio: PortfolioLoader) -> None:
        for table in ["PROJECT", "CALENDAR", "TASK", "TASKPRED", "RSRC", "TASKRSRC"]:
            assert table in portfolio.table_names

    def test_get_table_missing_raises(self, portfolio: PortfolioLoader) -> None:
        with pytest.raises(KeyError, match="NONEXISTENT"):
            portfolio.get_table("NONEXISTENT")

    def test_summary_returns_string(self, portfolio: PortfolioLoader) -> None:
        result = portfolio.summary()
        assert "XER files loaded: 2" in result
        assert "Activities: 2" in result


class TestEmptyDirectory:
    """Test error handling for empty directories."""

    def test_no_xer_files_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="No XER files"):
            PortfolioLoader(tmp_path)


class TestWithRealData:
    """Integration test with the real data directory."""

    @pytest.fixture
    def real_portfolio(self) -> PortfolioLoader | None:
        data_dir = Path("data")
        if not data_dir.exists():
            pytest.skip("Data directory not available")
        return PortfolioLoader(data_dir)

    def test_real_portfolio_loads(self, real_portfolio: PortfolioLoader) -> None:
        assert real_portfolio.file_count >= 1
        assert len(real_portfolio.tasks) > 0

    def test_real_portfolio_summary(self, real_portfolio: PortfolioLoader) -> None:
        result = real_portfolio.summary()
        assert "XER files loaded:" in result
