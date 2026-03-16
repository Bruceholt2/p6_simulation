"""Activity network builder for P6 schedule simulation.

Constructs a directed graph from parsed XER schedule data, representing
activities as nodes and predecessor/successor relationships as edges.
Supports forward/backward pass calculations and critical path identification.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator

import pandas as pd

from src.xer_parser import XERParser


class RelationshipType(Enum):
    """P6 activity relationship types."""

    FS = "PR_FS"  # Finish-to-Start
    FF = "PR_FF"  # Finish-to-Finish
    SS = "PR_SS"  # Start-to-Start
    SF = "PR_SF"  # Start-to-Finish


class TaskType(Enum):
    """P6 activity types."""

    TASK = "TT_Task"
    MILESTONE = "TT_Mile"
    FINISH_MILESTONE = "TT_FinMile"
    LOE = "TT_LOE"
    RESOURCE_DEPENDENT = "TT_Rsrc"


class StatusCode(Enum):
    """P6 activity status codes."""

    NOT_STARTED = "TK_NotStart"
    ACTIVE = "TK_Active"
    COMPLETE = "TK_Complete"


@dataclass
class Relationship:
    """A dependency relationship between two activities.

    Attributes:
        predecessor_id: The predecessor activity's task_id.
        successor_id: The successor activity's task_id.
        rel_type: The relationship type (FS, FF, SS, SF).
        lag_hours: Lag duration in hours (negative = lead).
    """

    predecessor_id: int
    successor_id: int
    rel_type: RelationshipType
    lag_hours: float


@dataclass
class Activity:
    """An activity (node) in the schedule network.

    Attributes:
        task_id: Unique activity identifier.
        task_code: User-visible activity code.
        task_name: Activity description.
        task_type: Activity type (task, milestone, etc.).
        status: Current status.
        original_duration_hours: Planned duration in hours.
        remaining_duration_hours: Remaining duration in hours.
        calendar_id: Assigned calendar ID.
        early_start: Calculated early start datetime.
        early_finish: Calculated early finish datetime.
        late_start: Calculated late start datetime.
        late_finish: Calculated late finish datetime.
        total_float_hours: Total float in hours.
        predecessors: Incoming relationships.
        successors: Outgoing relationships.
    """

    task_id: int
    task_code: str
    task_name: str
    task_type: TaskType
    status: StatusCode
    original_duration_hours: float
    remaining_duration_hours: float
    calendar_id: int | None
    early_start: pd.Timestamp | None = None
    early_finish: pd.Timestamp | None = None
    late_start: pd.Timestamp | None = None
    late_finish: pd.Timestamp | None = None
    total_float_hours: float = 0.0
    predecessors: list[Relationship] = field(default_factory=list)
    successors: list[Relationship] = field(default_factory=list)

    @property
    def is_milestone(self) -> bool:
        """Return True if this activity is a milestone."""
        return self.task_type in (TaskType.MILESTONE, TaskType.FINISH_MILESTONE)

    @property
    def is_critical(self) -> bool:
        """Return True if this activity is on the critical path (zero total float)."""
        return abs(self.total_float_hours) < 0.01


class ActivityNetwork:
    """Directed graph of schedule activities and their relationships.

    Builds a network from XERParser output, providing traversal,
    topological ordering, and critical path identification.

    Args:
        parser: An XERParser instance with loaded schedule data.
    """

    def __init__(self, parser: XERParser) -> None:
        self._parser = parser
        self._activities: dict[int, Activity] = {}
        self._build_network()

    def _build_network(self) -> None:
        """Construct the activity network from parsed XER data."""
        self._load_activities()
        self._load_relationships()

    def _load_activities(self) -> None:
        """Create Activity objects from the TASK table."""
        tasks = self._parser.tasks

        # Determine duration column — real XER files use target_drtn_hr_cnt,
        # simplified test fixtures may use orig_dur_hr_cnt
        dur_col = (
            "target_drtn_hr_cnt"
            if "target_drtn_hr_cnt" in tasks.columns
            else "orig_dur_hr_cnt"
        )
        remain_col = (
            "remain_drtn_hr_cnt"
            if "remain_drtn_hr_cnt" in tasks.columns
            else "remain_dur_hr_cnt"
        )

        for _, row in tasks.iterrows():
            task_id = int(row["task_id"])

            task_type_str = row.get("task_type", "TT_Task")
            try:
                task_type = TaskType(task_type_str)
            except ValueError:
                task_type = TaskType.TASK

            status_str = row.get("status_code", "TK_NotStart")
            try:
                status = StatusCode(status_str)
            except ValueError:
                status = StatusCode.NOT_STARTED

            orig_dur = float(row.get(dur_col, 0) or 0)
            remain_dur = float(row.get(remain_col, 0) or 0)
            cal_id = row.get("clndr_id")
            cal_id = int(cal_id) if pd.notna(cal_id) else None
            total_float = float(row.get("total_float_hr_cnt", 0) or 0)

            activity = Activity(
                task_id=task_id,
                task_code=str(row.get("task_code", "")),
                task_name=str(row.get("task_name", "")),
                task_type=task_type,
                status=status,
                original_duration_hours=orig_dur,
                remaining_duration_hours=remain_dur,
                calendar_id=cal_id,
                early_start=row.get("early_start_date"),
                early_finish=row.get("early_end_date"),
                late_start=row.get("late_start_date"),
                late_finish=row.get("late_end_date"),
                total_float_hours=total_float,
            )
            self._activities[task_id] = activity

    def _load_relationships(self) -> None:
        """Create Relationship objects and link activities."""
        preds = self._parser.predecessors

        for _, row in preds.iterrows():
            pred_id = int(row["pred_task_id"])
            succ_id = int(row["task_id"])

            # Skip relationships referencing activities not in our network
            if pred_id not in self._activities or succ_id not in self._activities:
                continue

            try:
                rel_type = RelationshipType(row["pred_type"])
            except ValueError:
                rel_type = RelationshipType.FS

            lag = float(row.get("lag_hr_cnt", 0) or 0)

            rel = Relationship(
                predecessor_id=pred_id,
                successor_id=succ_id,
                rel_type=rel_type,
                lag_hours=lag,
            )

            self._activities[pred_id].successors.append(rel)
            self._activities[succ_id].predecessors.append(rel)

    def get_activity(self, task_id: int) -> Activity:
        """Return the Activity for a given task_id.

        Raises:
            KeyError: If the task_id is not in the network.
        """
        if task_id not in self._activities:
            raise KeyError(f"Activity {task_id} not found in network")
        return self._activities[task_id]

    @property
    def activities(self) -> dict[int, Activity]:
        """All activities in the network, keyed by task_id."""
        return self._activities

    @property
    def num_activities(self) -> int:
        """Total number of activities in the network."""
        return len(self._activities)

    @property
    def num_relationships(self) -> int:
        """Total number of relationships in the network."""
        return sum(len(a.successors) for a in self._activities.values())

    def start_activities(self) -> list[Activity]:
        """Return activities with no predecessors."""
        return [a for a in self._activities.values() if not a.predecessors]

    def end_activities(self) -> list[Activity]:
        """Return activities with no successors."""
        return [a for a in self._activities.values() if not a.successors]

    def predecessors_of(self, task_id: int) -> list[Activity]:
        """Return all predecessor activities of the given task_id."""
        activity = self.get_activity(task_id)
        return [self._activities[r.predecessor_id] for r in activity.predecessors]

    def successors_of(self, task_id: int) -> list[Activity]:
        """Return all successor activities of the given task_id."""
        activity = self.get_activity(task_id)
        return [self._activities[r.successor_id] for r in activity.successors]

    def topological_order(self) -> list[Activity]:
        """Return activities in topological order (Kahn's algorithm).

        Returns:
            A list of Activity objects sorted so that every predecessor
            appears before its successors.

        Raises:
            ValueError: If the network contains a cycle.
        """
        in_degree: dict[int, int] = {tid: 0 for tid in self._activities}
        for activity in self._activities.values():
            for rel in activity.successors:
                in_degree[rel.successor_id] += 1

        queue = [tid for tid, deg in in_degree.items() if deg == 0]
        result: list[Activity] = []

        while queue:
            tid = queue.pop(0)
            activity = self._activities[tid]
            result.append(activity)

            for rel in activity.successors:
                in_degree[rel.successor_id] -= 1
                if in_degree[rel.successor_id] == 0:
                    queue.append(rel.successor_id)

        if len(result) != len(self._activities):
            raise ValueError(
                f"Network contains a cycle — only {len(result)} of "
                f"{len(self._activities)} activities could be ordered"
            )

        return result

    def critical_path(self) -> list[Activity]:
        """Return activities on the critical path (total float == 0).

        Activities are returned in topological order.
        """
        topo = self.topological_order()
        return [a for a in topo if a.is_critical]

    def summary(self) -> str:
        """Return a summary of the activity network.

        Returns:
            A multi-line string with network statistics.
        """
        rel_type_counts: dict[str, int] = defaultdict(int)
        for activity in self._activities.values():
            for rel in activity.successors:
                rel_type_counts[rel.rel_type.name] += 1

        task_type_counts: dict[str, int] = defaultdict(int)
        for activity in self._activities.values():
            task_type_counts[activity.task_type.name] += 1

        lines = [
            "Activity Network Summary",
            "",
            f"  Activities: {self.num_activities}",
            f"  Relationships: {self.num_relationships}",
            f"  Start activities: {len(self.start_activities())}",
            f"  End activities: {len(self.end_activities())}",
            f"  Critical activities: {len(self.critical_path())}",
            "",
            "  Relationship types:",
        ]
        for rtype, count in sorted(rel_type_counts.items()):
            lines.append(f"    {rtype}: {count}")

        lines.append("")
        lines.append("  Activity types:")
        for ttype, count in sorted(task_type_counts.items()):
            lines.append(f"    {ttype}: {count}")

        summary_text = "\n".join(lines)
        print(summary_text)
        return summary_text
