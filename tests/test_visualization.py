"""Tests for the visualization module."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pytest

from src.xer_parser import XERParser
from src.simulation_engine import (
    SimulationEngine,
    SimulationResult,
    ActivityResult,
    triangular_sampler,
)
from src.visualization import (
    gantt_chart,
    duration_histogram,
    s_curve,
    resource_utilization,
    criticality_index,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_xer(
    tasks: str = "",
    preds: str = "",
    resources: str = "",
    assignments: str = "",
    rates: str = "",
) -> str:
    calendar = (
        "%R\t1\tStandard\t"
        "(0||CalendarData()("
        "(0||DaysOfWeek()("
        "(0||1()())"
        "(0||2()((0||0(s|08:00|f|16:00)())))"
        "(0||3()((0||0(s|08:00|f|16:00)())))"
        "(0||4()((0||0(s|08:00|f|16:00)())))"
        "(0||5()((0||0(s|08:00|f|16:00)())))"
        "(0||6()((0||0(s|08:00|f|16:00)())))"
        "(0||7()())))"
        "(0||Exceptions()())))\n"
    )
    return (
        "%T\tPROJECT\n"
        "%F\tproj_id\tproj_short_name\tlast_recalc_date\n"
        "%R\t100\tTEST\t2025-06-01 08:00\n"
        "%T\tCALENDAR\n"
        "%F\tclndr_id\tclndr_name\tclndr_data\n"
        f"{calendar}"
        "%T\tTASK\n"
        "%F\ttask_id\tproj_id\ttask_code\ttask_name\ttask_type\tstatus_code\t"
        "total_float_hr_cnt\torig_dur_hr_cnt\tremain_dur_hr_cnt\t"
        "early_start_date\tearly_end_date\tlate_start_date\tlate_end_date\t"
        "clndr_id\tphys_complete_pct\n"
        f"{tasks}"
        "%T\tTASKPRED\n"
        "%F\ttask_pred_id\ttask_id\tpred_task_id\tpred_type\tlag_hr_cnt\n"
        f"{preds}"
        "%T\tRSRC\n"
        "%F\trsrc_id\trsrc_name\trsrc_short_name\trsrc_type\n"
        f"{resources}"
        "%T\tRSRCRATE\n"
        "%F\trsrc_rate_id\trsrc_id\tmax_qty_per_hr\tcost_per_qty\tstart_date\n"
        f"{rates}"
        "%T\tTASKRSRC\n"
        "%F\ttaskrsrc_id\ttask_id\trsrc_id\ttarget_qty_per_hr\ttarget_cost\n"
        f"{assignments}"
        "%E\n"
    )


def _linear_chain_xer() -> str:
    """A -> B -> C -> D, with A and C critical (float=0)."""
    tasks = (
        "%R\t1\t100\tA1000\tMobilization\tTT_Task\tTK_NotStart\t0\t16\t16\t"
        "2025-07-07 08:00\t2025-07-08 16:00\t2025-07-07 08:00\t2025-07-08 16:00\t1\t0\n"
        "%R\t2\t100\tA1010\tExcavation\tTT_Task\tTK_NotStart\t0\t24\t24\t"
        "2025-07-09 08:00\t2025-07-11 16:00\t2025-07-09 08:00\t2025-07-11 16:00\t1\t0\n"
        "%R\t3\t100\tA1020\tFoundation\tTT_Task\tTK_NotStart\t0\t40\t40\t"
        "2025-07-14 08:00\t2025-07-18 16:00\t2025-07-14 08:00\t2025-07-18 16:00\t1\t0\n"
        "%R\t4\t100\tA1030\tHandover\tTT_Mile\tTK_NotStart\t0\t0\t0\t"
        "2025-07-21 08:00\t2025-07-21 08:00\t2025-07-21 08:00\t2025-07-21 08:00\t1\t0\n"
    )
    preds = (
        "%R\t101\t2\t1\tPR_FS\t0\n"
        "%R\t102\t3\t2\tPR_FS\t0\n"
        "%R\t103\t4\t3\tPR_FS\t0\n"
    )
    return _make_xer(tasks=tasks, preds=preds)


def _resource_xer() -> str:
    """Two parallel tasks sharing a resource."""
    tasks = (
        "%R\t1\t100\tStart\tStart\tTT_Mile\tTK_NotStart\t0\t0\t0\t"
        "2025-07-07 08:00\t2025-07-07 08:00\t2025-07-07 08:00\t2025-07-07 08:00\t1\t0\n"
        "%R\t2\t100\tB\tTask B\tTT_Task\tTK_NotStart\t0\t16\t16\t"
        "2025-07-07 08:00\t2025-07-08 16:00\t2025-07-07 08:00\t2025-07-08 16:00\t1\t0\n"
        "%R\t3\t100\tC\tTask C\tTT_Task\tTK_NotStart\t0\t16\t16\t"
        "2025-07-07 08:00\t2025-07-08 16:00\t2025-07-07 08:00\t2025-07-08 16:00\t1\t0\n"
        "%R\t4\t100\tEnd\tEnd\tTT_Mile\tTK_NotStart\t0\t0\t0\t"
        "2025-07-08 16:00\t2025-07-08 16:00\t2025-07-08 16:00\t2025-07-08 16:00\t1\t0\n"
    )
    preds = (
        "%R\t101\t2\t1\tPR_FS\t0\n"
        "%R\t102\t3\t1\tPR_FS\t0\n"
        "%R\t103\t4\t2\tPR_FS\t0\n"
        "%R\t104\t4\t3\tPR_FS\t0\n"
    )
    resources = "%R\t501\tCrane\tCRN\tRT_Labor\n"
    rates = "%R\t601\t501\t1\t0\t2025-01-01 08:00\n"
    assignments = (
        "%R\t701\t2\t501\t1.0\t0\n"
        "%R\t702\t3\t501\t1.0\t0\n"
    )
    return _make_xer(
        tasks=tasks, preds=preds,
        resources=resources, rates=rates, assignments=assignments,
    )


def _write_and_run(
    tmp_path: Path, xer: str, *, resource_constrained: bool = False,
    sampler=None, seed: int | None = None,
) -> tuple[SimulationEngine, SimulationResult]:
    f = tmp_path / "test.xer"
    f.write_text(xer, encoding="utf-8")
    parser = XERParser(f)
    engine = SimulationEngine(
        parser,
        project_start=datetime(2025, 7, 7, 8, 0),
        resource_constrained=resource_constrained,
        duration_sampler=sampler,
        seed=seed,
    )
    return engine, engine.run()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGanttChart:
    """Test Gantt chart generation."""

    @pytest.fixture
    def result(self, tmp_path: Path) -> SimulationResult:
        _, result = _write_and_run(tmp_path, _linear_chain_xer())
        return result

    def test_returns_figure(self, result: SimulationResult) -> None:
        fig = gantt_chart(result)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_has_axes(self, result: SimulationResult) -> None:
        fig = gantt_chart(result)
        assert len(fig.axes) >= 1
        plt.close(fig)

    def test_correct_bar_count(self, result: SimulationResult) -> None:
        fig = gantt_chart(result)
        ax = fig.axes[0]
        # Each activity is a barh patch
        bars = [p for p in ax.patches if hasattr(p, "get_width")]
        assert len(bars) == 4  # A, B, C, D (milestone has 0-width bar)
        plt.close(fig)

    def test_top_n_limits_bars(self, result: SimulationResult) -> None:
        fig = gantt_chart(result, top_n=2)
        ax = fig.axes[0]
        labels = [t.get_text() for t in ax.get_yticklabels()]
        assert len(labels) == 2
        plt.close(fig)

    def test_sim_hours_mode(self, result: SimulationResult) -> None:
        fig = gantt_chart(result, use_calendar_dates=False)
        ax = fig.axes[0]
        assert ax.get_xlabel() == "Simulation Hours"
        plt.close(fig)

    def test_save_to_file(self, result: SimulationResult, tmp_path: Path) -> None:
        out = tmp_path / "gantt.png"
        fig = gantt_chart(result, save_path=out)
        assert out.exists()
        assert out.stat().st_size > 0
        plt.close(fig)

    def test_custom_title(self, result: SimulationResult) -> None:
        fig = gantt_chart(result, title="My Custom Title")
        ax = fig.axes[0]
        assert ax.get_title() == "My Custom Title"
        plt.close(fig)

    def test_empty_result(self) -> None:
        empty = SimulationResult(run_id=0)
        fig = gantt_chart(empty)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


class TestDurationHistogram:
    """Test duration histogram generation."""

    @pytest.fixture
    def mc_results(self, tmp_path: Path) -> list[SimulationResult]:
        f = tmp_path / "test.xer"
        f.write_text(_linear_chain_xer(), encoding="utf-8")
        parser = XERParser(f)
        engine = SimulationEngine(
            parser,
            project_start=datetime(2025, 7, 7, 8, 0),
            duration_sampler=triangular_sampler(0.8, 1.0, 1.5),
            seed=42,
            resource_constrained=False,
        )
        return engine.run_monte_carlo(num_runs=50)

    def test_returns_figure(self, mc_results: list[SimulationResult]) -> None:
        fig = duration_histogram(mc_results)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_has_percentile_lines(self, mc_results: list[SimulationResult]) -> None:
        fig = duration_histogram(mc_results, percentiles=[50, 90])
        ax = fig.axes[0]
        # 2 percentile lines + 1 mean line = 3 vertical lines
        vlines = [l for l in ax.get_lines() if len(l.get_xdata()) == 2]
        # At minimum we should have some lines
        assert len(ax.get_lines()) >= 3
        plt.close(fig)

    def test_save_to_file(self, mc_results: list[SimulationResult], tmp_path: Path) -> None:
        out = tmp_path / "histogram.png"
        fig = duration_histogram(mc_results, save_path=out)
        assert out.exists()
        plt.close(fig)

    def test_custom_bins(self, mc_results: list[SimulationResult]) -> None:
        fig = duration_histogram(mc_results, bins=10)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


class TestSCurve:
    """Test S-curve generation."""

    @pytest.fixture
    def result(self, tmp_path: Path) -> SimulationResult:
        _, result = _write_and_run(tmp_path, _linear_chain_xer())
        return result

    def test_returns_figure(self, result: SimulationResult) -> None:
        fig = s_curve(result)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_curve_is_monotonic(self, result: SimulationResult) -> None:
        fig = s_curve(result, num_points=100)
        ax = fig.axes[0]
        line = ax.get_lines()[0]
        y_data = line.get_ydata()
        # Cumulative hours should be non-decreasing
        diffs = np.diff(y_data)
        assert np.all(diffs >= -1e-9)
        plt.close(fig)

    def test_final_value_equals_total_work(self, result: SimulationResult) -> None:
        fig = s_curve(result, num_points=100)
        ax = fig.axes[0]
        line = ax.get_lines()[0]
        y_data = line.get_ydata()
        df = result.to_dataframe()
        total = df["simulated_duration_hours"].sum()
        assert y_data[-1] == pytest.approx(total, rel=0.05)
        plt.close(fig)

    def test_save_to_file(self, result: SimulationResult, tmp_path: Path) -> None:
        out = tmp_path / "scurve.png"
        fig = s_curve(result, save_path=out)
        assert out.exists()
        plt.close(fig)

    def test_empty_result(self) -> None:
        empty = SimulationResult(run_id=0)
        fig = s_curve(empty)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


class TestResourceUtilization:
    """Test resource utilization chart."""

    @pytest.fixture
    def engine_and_result(self, tmp_path: Path) -> tuple[SimulationEngine, SimulationResult]:
        return _write_and_run(
            tmp_path, _resource_xer(), resource_constrained=True,
        )

    def test_returns_figure(self, engine_and_result: tuple) -> None:
        engine, result = engine_and_result
        fig = resource_utilization(
            result,
            resource_assignments=engine._resource_assignments,
            resource_names={501: "Crane"},
        )
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_save_to_file(self, engine_and_result: tuple, tmp_path: Path) -> None:
        engine, result = engine_and_result
        out = tmp_path / "resources.png"
        fig = resource_utilization(
            result,
            resource_assignments=engine._resource_assignments,
            resource_names={501: "Crane"},
            save_path=out,
        )
        assert out.exists()
        plt.close(fig)

    def test_no_assignments_shows_message(self) -> None:
        empty = SimulationResult(run_id=0)
        empty.activity_results[1] = ActivityResult(
            task_id=1, proj_id=100, task_code="A", task_name="Test",
            planned_duration_hours=8, simulated_duration_hours=8,
            sim_start_time=0, sim_finish_time=8,
        )
        fig = resource_utilization(
            empty,
            resource_assignments={},
            resource_names={},
        )
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


class TestCriticalityIndex:
    """Test criticality index chart."""

    @pytest.fixture
    def mc_results(self, tmp_path: Path) -> list[SimulationResult]:
        f = tmp_path / "test.xer"
        f.write_text(_linear_chain_xer(), encoding="utf-8")
        parser = XERParser(f)
        engine = SimulationEngine(
            parser,
            project_start=datetime(2025, 7, 7, 8, 0),
            duration_sampler=triangular_sampler(0.8, 1.0, 1.5),
            seed=42,
            resource_constrained=False,
        )
        return engine.run_monte_carlo(num_runs=30)

    def test_returns_figure(self, mc_results: list[SimulationResult]) -> None:
        fig = criticality_index(mc_results)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_top_n_limits(self, mc_results: list[SimulationResult]) -> None:
        fig = criticality_index(mc_results, top_n=2)
        ax = fig.axes[0]
        labels = [t.get_text() for t in ax.get_yticklabels()]
        assert len(labels) <= 2
        plt.close(fig)

    def test_save_to_file(self, mc_results: list[SimulationResult], tmp_path: Path) -> None:
        out = tmp_path / "criticality.png"
        fig = criticality_index(mc_results, save_path=out)
        assert out.exists()
        plt.close(fig)

    def test_empty_results(self) -> None:
        fig = criticality_index([])
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


class TestWithRealData:
    """Integration test with the real sample XER file."""

    @pytest.fixture
    def real_result(self) -> tuple[SimulationEngine, SimulationResult] | None:
        xer_path = Path("data/sample-5272.xer")
        if not xer_path.exists():
            pytest.skip("Real XER file not available")
        parser = XERParser(xer_path)
        engine = SimulationEngine(
            parser, resource_constrained=False, seed=42,
        )
        return engine, engine.run()

    def test_real_gantt(self, real_result: tuple, tmp_path: Path) -> None:
        engine, result = real_result
        out = tmp_path / "real_gantt.png"
        fig = gantt_chart(result, top_n=30, save_path=out)
        assert out.exists()
        plt.close(fig)

    def test_real_scurve(self, real_result: tuple, tmp_path: Path) -> None:
        engine, result = real_result
        out = tmp_path / "real_scurve.png"
        fig = s_curve(result, save_path=out)
        assert out.exists()
        plt.close(fig)
