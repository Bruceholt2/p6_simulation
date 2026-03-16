"""Tests for the activity network module."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.xer_parser import XERParser
from src.activity_network import (
    ActivityNetwork,
    Activity,
    Relationship,
    RelationshipType,
    TaskType,
    StatusCode,
)

# Minimal XER: 5 activities in a linear chain with FS relationships,
# plus one SS and one FF relationship for coverage.
# A1000 -> A1010 -> A1020 -> A1030 -> A1040 (all FS)
# A1010 --SS--> A1020 (additional SS tie)
# A1020 --FF--> A1030 (additional FF tie)
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
    "%R\t5005\t1003\t1002\tPR_SS\t0\n"
    "%R\t5006\t1004\t1003\tPR_FF\t0\n"
    "%E\n"
)


@pytest.fixture
def xer_file(tmp_path: Path) -> Path:
    """Write sample XER to a temp file."""
    f = tmp_path / "test.xer"
    f.write_text(SAMPLE_XER, encoding="utf-8")
    return f


@pytest.fixture
def network(xer_file: Path) -> ActivityNetwork:
    """Return an ActivityNetwork built from the sample fixture."""
    parser = XERParser(xer_file)
    return ActivityNetwork(parser)


class TestNetworkConstruction:
    """Test that the network is built correctly from XER data."""

    def test_activity_count(self, network: ActivityNetwork) -> None:
        assert network.num_activities == 5

    def test_relationship_count(self, network: ActivityNetwork) -> None:
        # 4 FS + 1 SS + 1 FF = 6
        assert network.num_relationships == 6

    def test_all_activities_loaded(self, network: ActivityNetwork) -> None:
        for tid in [1001, 1002, 1003, 1004, 1005]:
            assert tid in network.activities

    def test_activity_attributes(self, network: ActivityNetwork) -> None:
        a = network.get_activity(1001)
        assert a.task_code == "A1000"
        assert a.task_name == "Mobilization"
        assert a.original_duration_hours == 80.0
        assert a.remaining_duration_hours == 80.0
        assert a.calendar_id == 1
        assert a.task_type == TaskType.TASK
        assert a.status == StatusCode.NOT_STARTED

    def test_milestone_detection(self, network: ActivityNetwork) -> None:
        a = network.get_activity(1005)
        assert a.is_milestone
        assert a.task_type == TaskType.MILESTONE

    def test_non_milestone(self, network: ActivityNetwork) -> None:
        a = network.get_activity(1001)
        assert not a.is_milestone

    def test_get_activity_missing_raises(self, network: ActivityNetwork) -> None:
        with pytest.raises(KeyError, match="9999"):
            network.get_activity(9999)


class TestRelationships:
    """Test predecessor/successor relationships."""

    def test_start_activity(self, network: ActivityNetwork) -> None:
        starts = network.start_activities()
        assert len(starts) == 1
        assert starts[0].task_id == 1001

    def test_end_activity(self, network: ActivityNetwork) -> None:
        ends = network.end_activities()
        assert len(ends) == 1
        assert ends[0].task_id == 1005

    def test_successor_links(self, network: ActivityNetwork) -> None:
        succs = network.successors_of(1001)
        assert len(succs) == 1
        assert succs[0].task_id == 1002

    def test_predecessor_links(self, network: ActivityNetwork) -> None:
        preds = network.predecessors_of(1005)
        assert len(preds) == 1
        assert preds[0].task_id == 1004

    def test_multiple_predecessors(self, network: ActivityNetwork) -> None:
        # Activity 1003 has 2 predecessors from 1002 (FS + SS)
        a = network.get_activity(1003)
        assert len(a.predecessors) == 2
        pred_ids = {r.predecessor_id for r in a.predecessors}
        assert pred_ids == {1002}

    def test_relationship_types(self, network: ActivityNetwork) -> None:
        a = network.get_activity(1003)
        rel_types = {r.rel_type for r in a.predecessors}
        assert RelationshipType.FS in rel_types
        assert RelationshipType.SS in rel_types

    def test_ff_relationship(self, network: ActivityNetwork) -> None:
        a = network.get_activity(1004)
        ff_rels = [r for r in a.predecessors if r.rel_type == RelationshipType.FF]
        assert len(ff_rels) == 1
        assert ff_rels[0].predecessor_id == 1003

    def test_lag_value(self, network: ActivityNetwork) -> None:
        a = network.get_activity(1002)
        assert a.predecessors[0].lag_hours == 0.0


class TestTopologicalOrder:
    """Test topological sorting of the network."""

    def test_topological_order_length(self, network: ActivityNetwork) -> None:
        topo = network.topological_order()
        assert len(topo) == 5

    def test_topological_order_respects_dependencies(self, network: ActivityNetwork) -> None:
        topo = network.topological_order()
        positions = {a.task_id: i for i, a in enumerate(topo)}
        # Every predecessor must appear before its successor
        assert positions[1001] < positions[1002]
        assert positions[1002] < positions[1003]
        assert positions[1003] < positions[1004]
        assert positions[1004] < positions[1005]

    def test_start_is_first(self, network: ActivityNetwork) -> None:
        topo = network.topological_order()
        assert topo[0].task_id == 1001

    def test_end_is_last(self, network: ActivityNetwork) -> None:
        topo = network.topological_order()
        assert topo[-1].task_id == 1005


class TestCriticalPath:
    """Test critical path identification."""

    def test_critical_path_all_zero_float(self, network: ActivityNetwork) -> None:
        # All activities in the fixture have 0 float
        cp = network.critical_path()
        assert len(cp) == 5

    def test_is_critical_property(self, network: ActivityNetwork) -> None:
        a = network.get_activity(1001)
        assert a.is_critical


class TestSummary:
    """Test the summary output."""

    def test_summary_returns_string(self, network: ActivityNetwork) -> None:
        result = network.summary()
        assert "Activities: 5" in result
        assert "Relationships: 6" in result
        assert "Start activities: 1" in result
        assert "End activities: 1" in result

    def test_summary_shows_relationship_types(self, network: ActivityNetwork) -> None:
        result = network.summary()
        assert "FS:" in result
        assert "SS:" in result
        assert "FF:" in result


class TestWithRealData:
    """Test the network with the real sample XER file (if available)."""

    @pytest.fixture
    def real_network(self) -> ActivityNetwork | None:
        xer_path = Path("data/sample-5272.xer")
        if not xer_path.exists():
            pytest.skip("Real XER file not available")
        parser = XERParser(xer_path)
        return ActivityNetwork(parser)

    def test_real_data_loads(self, real_network: ActivityNetwork) -> None:
        assert real_network.num_activities > 0
        assert real_network.num_relationships > 0

    def test_real_data_has_start_and_end(self, real_network: ActivityNetwork) -> None:
        assert len(real_network.start_activities()) >= 1
        assert len(real_network.end_activities()) >= 1

    def test_real_data_topological_order(self, real_network: ActivityNetwork) -> None:
        topo = real_network.topological_order()
        assert len(topo) == real_network.num_activities

    def test_real_data_summary(self, real_network: ActivityNetwork) -> None:
        result = real_network.summary()
        assert "Activities:" in result
