"""Tests for the SimPy simulation engine module."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from src.xer_parser import XERParser
from src.simulation_engine import (
    SimulationEngine,
    SimulationResult,
    ActivityResult,
    ResourcePool,
    deterministic_sampler,
    triangular_sampler,
    pert_sampler,
)


def _make_xer(
    tasks: str = "",
    preds: str = "",
    resources: str = "",
    assignments: str = "",
    rates: str = "",
    calendar: str = "",
) -> str:
    """Build a minimal XER string from provided table fragments."""
    if not calendar:
        # Default 5-day calendar (Mon-Fri, 08:00-16:00, no lunch for simplicity)
        calendar = (
            "%R\t1\tStandard\t"
            "(0||CalendarData()("
            "(0||DaysOfWeek()("
            "(0||1()())"  # Sun
            "(0||2()((0||0(s|08:00|f|16:00)())))"  # Mon
            "(0||3()((0||0(s|08:00|f|16:00)())))"  # Tue
            "(0||4()((0||0(s|08:00|f|16:00)())))"  # Wed
            "(0||5()((0||0(s|08:00|f|16:00)())))"  # Thu
            "(0||6()((0||0(s|08:00|f|16:00)())))"  # Fri
            "(0||7()())))"  # Sat
            "(0||Exceptions()())))\n"
        )

    xer = (
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
    return xer


def _write_xer(tmp_path: Path, xer_content: str) -> XERParser:
    """Write XER content to a temp file and return a parser."""
    f = tmp_path / "test.xer"
    f.write_text(xer_content, encoding="utf-8")
    return XERParser(f)


# --- Fixtures for common schedule patterns ---

def _linear_chain_xer() -> str:
    """3 activities in a linear FS chain: A(16h) -> B(24h) -> C(8h)."""
    tasks = (
        "%R\t1\t100\tA\tActivity A\tTT_Task\tTK_NotStart\t0\t16\t16\t"
        "2025-07-07 08:00\t2025-07-08 16:00\t2025-07-07 08:00\t2025-07-08 16:00\t1\t0\n"
        "%R\t2\t100\tB\tActivity B\tTT_Task\tTK_NotStart\t0\t24\t24\t"
        "2025-07-09 08:00\t2025-07-11 16:00\t2025-07-09 08:00\t2025-07-11 16:00\t1\t0\n"
        "%R\t3\t100\tC\tActivity C\tTT_Task\tTK_NotStart\t0\t8\t8\t"
        "2025-07-14 08:00\t2025-07-14 16:00\t2025-07-14 08:00\t2025-07-14 16:00\t1\t0\n"
    )
    preds = (
        "%R\t101\t2\t1\tPR_FS\t0\n"
        "%R\t102\t3\t2\tPR_FS\t0\n"
    )
    return _make_xer(tasks=tasks, preds=preds)


def _parallel_xer() -> str:
    """Start -> (B, C in parallel) -> End. B=16h, C=24h, so C drives."""
    tasks = (
        "%R\t1\t100\tStart\tStart\tTT_Mile\tTK_NotStart\t0\t0\t0\t"
        "2025-07-07 08:00\t2025-07-07 08:00\t2025-07-07 08:00\t2025-07-07 08:00\t1\t0\n"
        "%R\t2\t100\tB\tParallel B\tTT_Task\tTK_NotStart\t8\t16\t16\t"
        "2025-07-07 08:00\t2025-07-08 16:00\t2025-07-07 08:00\t2025-07-08 16:00\t1\t0\n"
        "%R\t3\t100\tC\tParallel C\tTT_Task\tTK_NotStart\t0\t24\t24\t"
        "2025-07-07 08:00\t2025-07-09 16:00\t2025-07-07 08:00\t2025-07-09 16:00\t1\t0\n"
        "%R\t4\t100\tEnd\tEnd\tTT_Mile\tTK_NotStart\t0\t0\t0\t"
        "2025-07-09 16:00\t2025-07-09 16:00\t2025-07-09 16:00\t2025-07-09 16:00\t1\t0\n"
    )
    preds = (
        "%R\t101\t2\t1\tPR_FS\t0\n"
        "%R\t102\t3\t1\tPR_FS\t0\n"
        "%R\t103\t4\t2\tPR_FS\t0\n"
        "%R\t104\t4\t3\tPR_FS\t0\n"
    )
    return _make_xer(tasks=tasks, preds=preds)


def _resource_contention_xer() -> str:
    """Two parallel tasks competing for the same resource (capacity=1).
    Start -> (B, C) -> End. B=8h, C=8h, both need resource R1."""
    tasks = (
        "%R\t1\t100\tStart\tStart\tTT_Mile\tTK_NotStart\t0\t0\t0\t"
        "2025-07-07 08:00\t2025-07-07 08:00\t2025-07-07 08:00\t2025-07-07 08:00\t1\t0\n"
        "%R\t2\t100\tB\tTask B\tTT_Task\tTK_NotStart\t0\t8\t8\t"
        "2025-07-07 08:00\t2025-07-07 16:00\t2025-07-07 08:00\t2025-07-07 16:00\t1\t0\n"
        "%R\t3\t100\tC\tTask C\tTT_Task\tTK_NotStart\t0\t8\t8\t"
        "2025-07-07 08:00\t2025-07-07 16:00\t2025-07-07 08:00\t2025-07-07 16:00\t1\t0\n"
        "%R\t4\t100\tEnd\tEnd\tTT_Mile\tTK_NotStart\t0\t0\t0\t"
        "2025-07-07 16:00\t2025-07-07 16:00\t2025-07-07 16:00\t2025-07-07 16:00\t1\t0\n"
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


# ============================================================
# Tests
# ============================================================

class TestDeterministicLinearChain:
    """Test a simple A -> B -> C chain with deterministic durations."""

    @pytest.fixture
    def result(self, tmp_path: Path) -> SimulationResult:
        parser = _write_xer(tmp_path, _linear_chain_xer())
        engine = SimulationEngine(
            parser,
            project_start=datetime(2025, 7, 7, 8, 0),
            resource_constrained=False,
        )
        return engine.run()

    def test_all_activities_simulated(self, result: SimulationResult) -> None:
        assert len(result.activity_results) == 3

    def test_project_duration(self, result: SimulationResult) -> None:
        # A=16h + B=24h + C=8h = 48h total
        assert result.project_duration_hours == pytest.approx(48.0)

    def test_activity_a_starts_at_zero(self, result: SimulationResult) -> None:
        a = result.activity_results[1]
        assert a.sim_start_time == pytest.approx(0.0)
        assert a.sim_finish_time == pytest.approx(16.0)

    def test_activity_b_starts_after_a(self, result: SimulationResult) -> None:
        b = result.activity_results[2]
        assert b.sim_start_time == pytest.approx(16.0)
        assert b.sim_finish_time == pytest.approx(40.0)

    def test_activity_c_starts_after_b(self, result: SimulationResult) -> None:
        c = result.activity_results[3]
        assert c.sim_start_time == pytest.approx(40.0)
        assert c.sim_finish_time == pytest.approx(48.0)

    def test_no_wait_hours(self, result: SimulationResult) -> None:
        for r in result.activity_results.values():
            assert r.wait_hours == pytest.approx(0.0)

    def test_result_to_dataframe(self, result: SimulationResult) -> None:
        df = result.to_dataframe()
        assert len(df) == 3
        assert "task_code" in df.columns
        assert "sim_start_time" in df.columns


class TestParallelPaths:
    """Test parallel paths — project duration driven by longest path."""

    @pytest.fixture
    def result(self, tmp_path: Path) -> SimulationResult:
        parser = _write_xer(tmp_path, _parallel_xer())
        engine = SimulationEngine(
            parser,
            project_start=datetime(2025, 7, 7, 8, 0),
            resource_constrained=False,
        )
        return engine.run()

    def test_project_duration_driven_by_longest(self, result: SimulationResult) -> None:
        # B=16h, C=24h in parallel. Duration = max(16, 24) = 24h
        assert result.project_duration_hours == pytest.approx(24.0)

    def test_parallel_activities_start_together(self, result: SimulationResult) -> None:
        b = result.activity_results[2]
        c = result.activity_results[3]
        assert b.sim_start_time == pytest.approx(0.0)
        assert c.sim_start_time == pytest.approx(0.0)

    def test_end_milestone_at_24(self, result: SimulationResult) -> None:
        end = result.activity_results[4]
        assert end.sim_start_time == pytest.approx(24.0)
        assert end.simulated_duration_hours == pytest.approx(0.0)


class TestResourceContention:
    """Test that resource constraints cause serialization of parallel tasks."""

    @pytest.fixture
    def result(self, tmp_path: Path) -> SimulationResult:
        parser = _write_xer(tmp_path, _resource_contention_xer())
        engine = SimulationEngine(
            parser,
            project_start=datetime(2025, 7, 7, 8, 0),
            resource_constrained=True,
        )
        return engine.run()

    def test_resource_constraint_extends_duration(self, result: SimulationResult) -> None:
        # Without resources: B and C run in parallel = 8h
        # With resource contention (capacity=1): one waits, so 8+8=16h
        assert result.project_duration_hours == pytest.approx(16.0)

    def test_one_task_delayed(self, result: SimulationResult) -> None:
        b = result.activity_results[2]
        c = result.activity_results[3]
        # One starts at 0, the other at 8 (order depends on topo sort)
        starts = sorted([b.sim_start_time, c.sim_start_time])
        assert starts[0] == pytest.approx(0.0)
        assert starts[1] == pytest.approx(8.0)

    def test_delayed_task_has_wait_hours(self, result: SimulationResult) -> None:
        b = result.activity_results[2]
        c = result.activity_results[3]
        total_wait = b.wait_hours + c.wait_hours
        assert total_wait == pytest.approx(8.0)

    @pytest.fixture
    def unconstrained_result(self, tmp_path: Path) -> SimulationResult:
        parser = _write_xer(tmp_path, _resource_contention_xer())
        engine = SimulationEngine(
            parser,
            project_start=datetime(2025, 7, 7, 8, 0),
            resource_constrained=False,
        )
        return engine.run()

    def test_no_constraint_runs_parallel(self, unconstrained_result: SimulationResult) -> None:
        assert unconstrained_result.project_duration_hours == pytest.approx(8.0)


class TestMilestones:
    """Test that milestones have zero simulated duration."""

    @pytest.fixture
    def result(self, tmp_path: Path) -> SimulationResult:
        parser = _write_xer(tmp_path, _parallel_xer())
        engine = SimulationEngine(
            parser,
            project_start=datetime(2025, 7, 7, 8, 0),
            resource_constrained=False,
        )
        return engine.run()

    def test_start_milestone_zero_duration(self, result: SimulationResult) -> None:
        start = result.activity_results[1]
        assert start.simulated_duration_hours == pytest.approx(0.0)
        assert start.sim_start_time == start.sim_finish_time

    def test_end_milestone_zero_duration(self, result: SimulationResult) -> None:
        end = result.activity_results[4]
        assert end.simulated_duration_hours == pytest.approx(0.0)


class TestLag:
    """Test that lag on FS relationships is respected."""

    @pytest.fixture
    def result(self, tmp_path: Path) -> SimulationResult:
        tasks = (
            "%R\t1\t100\tA\tAct A\tTT_Task\tTK_NotStart\t0\t8\t8\t"
            "2025-07-07 08:00\t2025-07-07 16:00\t2025-07-07 08:00\t2025-07-07 16:00\t1\t0\n"
            "%R\t2\t100\tB\tAct B\tTT_Task\tTK_NotStart\t0\t8\t8\t"
            "2025-07-08 08:00\t2025-07-08 16:00\t2025-07-08 08:00\t2025-07-08 16:00\t1\t0\n"
        )
        preds = "%R\t101\t2\t1\tPR_FS\t16\n"  # 16 hours lag
        xer = _make_xer(tasks=tasks, preds=preds)
        parser = _write_xer(tmp_path, xer)
        engine = SimulationEngine(
            parser,
            project_start=datetime(2025, 7, 7, 8, 0),
            resource_constrained=False,
        )
        return engine.run()

    def test_lag_delays_successor(self, result: SimulationResult) -> None:
        b = result.activity_results[2]
        # A finishes at 8h, lag=16h, so B starts at 8+16=24h
        assert b.sim_start_time == pytest.approx(24.0)

    def test_total_duration_with_lag(self, result: SimulationResult) -> None:
        # A=8h + lag=16h + B=8h = 32h
        assert result.project_duration_hours == pytest.approx(32.0)


class TestSSRelationship:
    """Test Start-to-Start relationships."""

    @pytest.fixture
    def result(self, tmp_path: Path) -> SimulationResult:
        tasks = (
            "%R\t1\t100\tA\tAct A\tTT_Task\tTK_NotStart\t0\t16\t16\t"
            "2025-07-07 08:00\t2025-07-08 16:00\t2025-07-07 08:00\t2025-07-08 16:00\t1\t0\n"
            "%R\t2\t100\tB\tAct B\tTT_Task\tTK_NotStart\t0\t8\t8\t"
            "2025-07-07 08:00\t2025-07-07 16:00\t2025-07-07 08:00\t2025-07-07 16:00\t1\t0\n"
        )
        # SS with 4h lag: B starts 4h after A starts
        preds = "%R\t101\t2\t1\tPR_SS\t4\n"
        xer = _make_xer(tasks=tasks, preds=preds)
        parser = _write_xer(tmp_path, xer)
        engine = SimulationEngine(
            parser,
            project_start=datetime(2025, 7, 7, 8, 0),
            resource_constrained=False,
        )
        return engine.run()

    def test_ss_successor_starts_after_lag(self, result: SimulationResult) -> None:
        b = result.activity_results[2]
        # A starts at 0, SS lag=4, so B starts at 0+4=4
        assert b.sim_start_time == pytest.approx(4.0)

    def test_ss_project_duration(self, result: SimulationResult) -> None:
        # A: 0-16, B: 4-12. Max finish = 16
        assert result.project_duration_hours == pytest.approx(16.0)


class TestCalendarIntegration:
    """Test that calendar datetimes are computed from simulation hours."""

    @pytest.fixture
    def result(self, tmp_path: Path) -> SimulationResult:
        parser = _write_xer(tmp_path, _linear_chain_xer())
        engine = SimulationEngine(
            parser,
            project_start=datetime(2025, 7, 7, 8, 0),  # Monday 8am
            resource_constrained=False,
        )
        return engine.run()

    def test_first_activity_calendar_start(self, result: SimulationResult) -> None:
        a = result.activity_results[1]
        assert a.sim_start_date == datetime(2025, 7, 7, 8, 0)

    def test_project_start_set(self, result: SimulationResult) -> None:
        assert result.project_start == datetime(2025, 7, 7, 8, 0)

    def test_project_finish_set(self, result: SimulationResult) -> None:
        assert result.project_finish is not None


class TestDurationSamplers:
    """Test the built-in duration sampling functions."""

    def test_deterministic_returns_same(self) -> None:
        rng = np.random.default_rng(42)
        assert deterministic_sampler(100.0, rng) == 100.0
        assert deterministic_sampler(0.0, rng) == 0.0

    def test_triangular_range(self) -> None:
        sampler = triangular_sampler(0.8, 1.0, 1.5)
        rng = np.random.default_rng(42)
        results = [sampler(100.0, rng) for _ in range(1000)]
        assert all(80.0 <= r <= 150.0 for r in results)

    def test_triangular_zero_duration(self) -> None:
        sampler = triangular_sampler()
        rng = np.random.default_rng(42)
        assert sampler(0.0, rng) == 0.0

    def test_pert_range(self) -> None:
        sampler = pert_sampler(0.8, 1.0, 1.5)
        rng = np.random.default_rng(42)
        results = [sampler(100.0, rng) for _ in range(1000)]
        assert all(80.0 <= r <= 150.0 for r in results)

    def test_pert_zero_duration(self) -> None:
        sampler = pert_sampler()
        rng = np.random.default_rng(42)
        assert sampler(0.0, rng) == 0.0

    def test_triangular_mean_near_planned(self) -> None:
        sampler = triangular_sampler(0.8, 1.0, 1.5)
        rng = np.random.default_rng(42)
        results = [sampler(100.0, rng) for _ in range(5000)]
        mean = np.mean(results)
        # Triangular mean = (a + b + c) / 3 = (80 + 100 + 150) / 3 = 110
        assert 105 < mean < 115


class TestMonteCarloBasic:
    """Test Monte Carlo execution with stochastic durations."""

    @pytest.fixture
    def results(self, tmp_path: Path) -> list[SimulationResult]:
        parser = _write_xer(tmp_path, _linear_chain_xer())
        engine = SimulationEngine(
            parser,
            project_start=datetime(2025, 7, 7, 8, 0),
            duration_sampler=triangular_sampler(0.8, 1.0, 1.5),
            seed=42,
            resource_constrained=False,
        )
        return engine.run_monte_carlo(num_runs=50)

    def test_correct_number_of_runs(self, results: list[SimulationResult]) -> None:
        assert len(results) == 50

    def test_run_ids_sequential(self, results: list[SimulationResult]) -> None:
        ids = [r.run_id for r in results]
        assert ids == list(range(50))

    def test_durations_vary(self, results: list[SimulationResult]) -> None:
        durations = [r.project_duration_hours for r in results]
        assert max(durations) > min(durations)

    def test_all_runs_have_activities(self, results: list[SimulationResult]) -> None:
        for r in results:
            assert len(r.activity_results) == 3

    def test_reproducible_with_seed(self, tmp_path: Path) -> None:
        parser = _write_xer(tmp_path, _linear_chain_xer())
        engine1 = SimulationEngine(
            parser, project_start=datetime(2025, 7, 7, 8, 0),
            duration_sampler=triangular_sampler(), seed=123,
            resource_constrained=False,
        )
        engine2 = SimulationEngine(
            parser, project_start=datetime(2025, 7, 7, 8, 0),
            duration_sampler=triangular_sampler(), seed=123,
            resource_constrained=False,
        )
        r1 = engine1.run(run_id=0)
        r2 = engine2.run(run_id=0)
        assert r1.project_duration_hours == pytest.approx(r2.project_duration_hours)


class TestSummaryOutput:
    """Test the summary and monte_carlo_summary methods."""

    @pytest.fixture
    def engine(self, tmp_path: Path) -> SimulationEngine:
        parser = _write_xer(tmp_path, _linear_chain_xer())
        return SimulationEngine(
            parser,
            project_start=datetime(2025, 7, 7, 8, 0),
            resource_constrained=False,
        )

    def test_single_run_summary(self, engine: SimulationEngine) -> None:
        result = engine.run()
        text = engine.summary(result)
        assert "Duration (hours): 48.0" in text
        assert "Activities:       3" in text

    def test_monte_carlo_summary(self, engine: SimulationEngine) -> None:
        results = engine.run_monte_carlo(num_runs=10)
        text = engine.monte_carlo_summary(results)
        assert "Monte Carlo Summary (10 runs)" in text
        assert "Mean duration:" in text
        assert "P90 duration:" in text


class TestWithRealData:
    """Integration test with the real sample XER file."""

    @pytest.fixture
    def real_engine(self) -> SimulationEngine | None:
        xer_path = Path("data/sample-5272.xer")
        if not xer_path.exists():
            pytest.skip("Real XER file not available")
        parser = XERParser(xer_path)
        return SimulationEngine(
            parser, resource_constrained=False, seed=42,
        )

    def test_real_deterministic_run(self, real_engine: SimulationEngine) -> None:
        result = real_engine.run()
        assert len(result.activity_results) == real_engine.network.num_activities
        assert result.project_duration_hours > 0

    def test_real_summary(self, real_engine: SimulationEngine) -> None:
        result = real_engine.run()
        text = real_engine.summary(result)
        assert "Duration (hours):" in text
