"""SimPy-based discrete event simulation engine for P6 schedules.

Simulates project execution by processing activities in dependency order,
respecting resource constraints and calendar-aware durations. Supports
deterministic and stochastic (Monte Carlo) duration modeling.

Performance optimizations:
- Fast-path direct traversal for non-resource-constrained runs (no SimPy overhead)
- Cached topological order reused across Monte Carlo runs
- Deferred calendar conversion (only on single-run results, not during MC)
- Parallel Monte Carlo execution via concurrent.futures
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

import numpy as np
import pandas as pd
import simpy

from src.activity_network import (
    Activity,
    ActivityNetwork,
    RelationshipType,
    StatusCode,
    TaskType,
)
from src.calendar_engine import CalendarEngine
from src.xer_parser import XERParser


@dataclass
class ResourcePool:
    """A shared resource with limited capacity.

    Attributes:
        rsrc_id: Unique resource identifier.
        name: Resource name.
        capacity: Maximum units available per hour.
        resource: SimPy Resource object (set during simulation).
    """

    rsrc_id: int
    name: str
    capacity: float
    resource: simpy.Resource | None = field(default=None, repr=False)


@dataclass
class ActivityResult:
    """Result of simulating a single activity.

    Attributes:
        task_id: Activity identifier.
        proj_id: Project identifier.
        task_code: User-visible activity code.
        task_name: Activity description.
        planned_duration_hours: Original planned duration.
        simulated_duration_hours: Duration used in this simulation run.
        sim_start_time: Simulation start time (int hours from sim epoch).
        sim_finish_time: Simulation finish time (int hours from sim epoch).
        sim_start_date: Calendar datetime when activity started.
        sim_finish_date: Calendar datetime when activity finished.
        wait_hours: Hours spent waiting for resources.
        is_critical: Whether the activity was on the critical path.
    """

    task_id: int
    proj_id: int
    task_code: str
    task_name: str
    planned_duration_hours: float
    simulated_duration_hours: float
    sim_start_time: int
    sim_finish_time: int
    sim_start_date: datetime | None = None
    sim_finish_date: datetime | None = None
    wait_hours: float = 0.0
    is_critical: bool = False


@dataclass
class SimulationResult:
    """Results from a single simulation run.

    Attributes:
        run_id: Identifier for this run (0-based for Monte Carlo).
        activity_results: Results for each activity, keyed by task_id.
        project_duration_hours: Total simulated project duration in work hours.
        project_start: Calendar start datetime.
        project_finish: Calendar finish datetime.
    """

    run_id: int
    activity_results: dict[int, ActivityResult] = field(default_factory=dict)
    project_duration_hours: float = 0.0
    project_start: datetime | None = None
    project_finish: datetime | None = None

    def filter_by_project(self, proj_id: int) -> "SimulationResult":
        """Return a new SimulationResult containing only activities for a project.

        Args:
            proj_id: The project ID to filter by.

        Returns:
            A new SimulationResult with only the matching activities.
        """
        filtered = {
            tid: ar
            for tid, ar in self.activity_results.items()
            if ar.proj_id == proj_id
        }
        result = SimulationResult(
            run_id=self.run_id,
            activity_results=filtered,
            project_start=self.project_start,
        )
        if filtered:
            result.project_duration_hours = max(
                r.sim_finish_time for r in filtered.values()
            )
            last = max(filtered.values(), key=lambda r: r.sim_finish_time)
            result.project_finish = last.sim_finish_date
        return result

    def to_dataframe(self) -> pd.DataFrame:
        """Convert activity results to a DataFrame.

        Returns:
            DataFrame with one row per activity and columns for all
            ActivityResult fields.
        """
        records = []
        for r in self.activity_results.values():
            records.append({
                "task_id": r.task_id,
                "proj_id": r.proj_id,
                "task_code": r.task_code,
                "task_name": r.task_name,
                "planned_duration_hours": r.planned_duration_hours,
                "simulated_duration_hours": r.simulated_duration_hours,
                "sim_start_date": r.sim_start_date,
                "sim_finish_date": r.sim_finish_date,
                "sim_start_time": r.sim_start_time,
                "sim_finish_time": r.sim_finish_time,
                "wait_hours": r.wait_hours,
                "is_critical": r.is_critical,
            })
        return pd.DataFrame(records)


# Type alias for duration sampling functions.
# Given planned duration, return simulated duration.
DurationSampler = Callable[[float, np.random.Generator], float]


def deterministic_sampler(planned_hours: float, rng: np.random.Generator) -> float:
    """Return the planned duration unchanged (no uncertainty)."""
    return planned_hours


def triangular_sampler(
    optimistic_factor: float = 0.8,
    most_likely_factor: float = 1.0,
    pessimistic_factor: float = 1.5,
) -> DurationSampler:
    """Create a triangular distribution sampler for activity durations.

    Args:
        optimistic_factor: Multiplier for best-case duration.
        most_likely_factor: Multiplier for most-likely duration.
        pessimistic_factor: Multiplier for worst-case duration.

    Returns:
        A DurationSampler function.
    """

    def sampler(planned_hours: float, rng: np.random.Generator) -> float:
        if planned_hours <= 0:
            return 0.0
        low = planned_hours * optimistic_factor
        mode = planned_hours * most_likely_factor
        high = planned_hours * pessimistic_factor
        return float(rng.triangular(low, mode, high))

    return sampler


def pert_sampler(
    optimistic_factor: float = 0.8,
    most_likely_factor: float = 1.0,
    pessimistic_factor: float = 1.5,
    lambd: float = 4.0,
) -> DurationSampler:
    """Create a PERT (Beta) distribution sampler for activity durations.

    Uses the PERT formula to derive Beta distribution parameters:
        mean = (optimistic + lambd * most_likely + pessimistic) / (lambd + 2)

    Args:
        optimistic_factor: Multiplier for best-case duration.
        most_likely_factor: Multiplier for most-likely duration.
        pessimistic_factor: Multiplier for worst-case duration.
        lambd: Shape parameter (4 is standard PERT).

    Returns:
        A DurationSampler function.
    """

    def sampler(planned_hours: float, rng: np.random.Generator) -> float:
        if planned_hours <= 0:
            return 0.0
        a = planned_hours * optimistic_factor
        m = planned_hours * most_likely_factor
        b = planned_hours * pessimistic_factor
        if b - a < 1e-9:
            return m
        mu = (a + lambd * m + b) / (lambd + 2)
        # Derive alpha and beta for the Beta distribution
        alpha = ((mu - a) * (2 * m - a - b)) / ((m - mu) * (b - a))
        if alpha <= 0:
            alpha = 1.0
        beta_param = alpha * (b - mu) / (mu - a) if mu > a else 1.0
        if beta_param <= 0:
            beta_param = 1.0
        sample = rng.beta(alpha, beta_param)
        return float(a + sample * (b - a))

    return sampler


def _compute_earliest_start(
    rel: object,
    activity_starts: dict[int, float],
    activity_finishes: dict[int, float],
    successor_duration: float,
) -> float:
    """Compute the earliest start for a successor based on one relationship."""
    pred_finish = activity_finishes.get(rel.predecessor_id, 0)
    pred_start = activity_starts.get(rel.predecessor_id, 0)

    if rel.rel_type == RelationshipType.FS:
        return pred_finish + rel.lag_hours
    elif rel.rel_type == RelationshipType.SS:
        return pred_start + rel.lag_hours
    elif rel.rel_type == RelationshipType.FF:
        return pred_finish + rel.lag_hours - successor_duration
    elif rel.rel_type == RelationshipType.SF:
        return pred_start + rel.lag_hours - successor_duration
    return pred_finish + rel.lag_hours


class SimulationEngine:
    """Discrete event simulation engine for P6 schedules.

    Processes activities in topological order through a SimPy simulation,
    respecting predecessor relationships, resource constraints, and
    calendar-aware scheduling.

    Args:
        parser: XERParser with loaded schedule data.
        project_start: Calendar start date for the simulation.
            If None, uses the earliest early_start from the schedule.
        duration_sampler: Function to sample activity durations.
            Defaults to deterministic (planned = simulated).
        seed: Random seed for reproducible Monte Carlo runs.
        resource_constrained: Whether to enforce resource capacity limits.
    """

    def __init__(
        self,
        parser: XERParser,
        project_start: datetime | None = None,
        duration_sampler: DurationSampler | None = None,
        seed: int | None = None,
        resource_constrained: bool = True,
    ) -> None:
        self._parser = parser
        self._network = ActivityNetwork(parser)
        self._calendar = CalendarEngine(parser)
        self._duration_sampler = duration_sampler or deterministic_sampler
        self._seed = seed
        self._resource_constrained = resource_constrained

        # Determine project start
        if project_start is not None:
            self._project_start = project_start
        else:
            self._project_start = self._infer_project_start()

        # Build task_id -> proj_id lookup
        tasks = self._parser.tasks
        self._proj_ids: dict[int, int] = {}
        if "proj_id" in tasks.columns:
            for _, row in tasks.iterrows():
                self._proj_ids[int(row["task_id"])] = int(row["proj_id"])

        # Build resource pools and task calendar mappings
        self._resource_pools: dict[int, ResourcePool] = {}
        self._resource_assignments: dict[int, list[int]] = {}  # task_id -> [rsrc_id]
        self._task_calendar_ids: dict[int, list[int]] = {}  # task_id -> [clndr_id]
        self._build_resource_data()

        # Cache topological order — the network doesn't change between runs
        self._topo_order: list[Activity] = self._network.topological_order()

    def _infer_project_start(self) -> datetime:
        """Determine project start from the earliest early_start date."""
        tasks = self._parser.tasks
        if "early_start_date" in tasks.columns:
            valid = tasks["early_start_date"].dropna()
            if len(valid) > 0:
                return valid.min().to_pydatetime()
        return datetime(2025, 1, 1, 8, 0)

    def _build_resource_data(self) -> None:
        """Build resource pools, task assignments, and task calendar mappings.

        Resource capacity priority:
        1. max_qty_per_hr from RSRCRATE with the latest start_date
        2. def_qty_per_hr from RSRC table
        3. Infinity (unlimited capacity)

        Task calendar: intersection of all resource calendars assigned
        to the task via TASKRSRC. Falls back to the activity's own
        calendar_id if no resource assignments exist.
        """
        resources = self._parser.resources
        try:
            rates = self._parser.get_table("RSRCRATE")
        except KeyError:
            rates = pd.DataFrame()

        # Build capacity lookup from rates — use the latest start_date per resource
        rate_capacity: dict[int, float] = {}
        if len(rates) > 0 and "max_qty_per_hr" in rates.columns:
            # Sort by start_date descending so first occurrence per rsrc_id is latest
            rate_df = rates.dropna(subset=["rsrc_id"]).copy()
            if "start_date" in rate_df.columns:
                rate_df = rate_df.sort_values("start_date", ascending=False)
            for _, row in rate_df.iterrows():
                rsrc_id = int(row["rsrc_id"])
                if rsrc_id not in rate_capacity:
                    cap = row.get("max_qty_per_hr")
                    if pd.notna(cap) and float(cap) > 0:
                        rate_capacity[rsrc_id] = float(cap)

        # Build def_qty_per_hr lookup from RSRC table
        def_capacity: dict[int, float] = {}
        if "def_qty_per_hr" in resources.columns:
            for _, row in resources.iterrows():
                rsrc_id = int(row["rsrc_id"])
                val = row.get("def_qty_per_hr")
                if pd.notna(val) and float(val) > 0:
                    def_capacity[rsrc_id] = float(val)

        for _, row in resources.iterrows():
            rsrc_id = int(row["rsrc_id"])
            name = str(row.get("rsrc_name", f"Resource-{rsrc_id}"))

            # Priority: RSRCRATE latest -> RSRC def_qty_per_hr -> infinity
            if rsrc_id in rate_capacity:
                capacity = rate_capacity[rsrc_id]
            elif rsrc_id in def_capacity:
                capacity = def_capacity[rsrc_id]
            else:
                capacity = float("inf")

            # SimPy Resource uses integer capacity; inf means no constraint
            if capacity == float("inf"):
                int_capacity = 999999
            else:
                int_capacity = max(1, int(capacity))

            self._resource_pools[rsrc_id] = ResourcePool(
                rsrc_id=rsrc_id,
                name=name,
                capacity=int_capacity,
            )

        # Build resource clndr_id lookup
        rsrc_calendar: dict[int, int] = {}
        if "clndr_id" in resources.columns:
            for _, row in resources.iterrows():
                rid = int(row["rsrc_id"])
                cid = row.get("clndr_id")
                if pd.notna(cid):
                    rsrc_calendar[rid] = int(cid)

        # Build task -> resource assignments and task -> resource calendar IDs
        assignments = self._parser.resource_assignments
        for _, row in assignments.iterrows():
            task_id = int(row["task_id"])
            rsrc_id = int(row["rsrc_id"])
            if rsrc_id in self._resource_pools:
                self._resource_assignments.setdefault(task_id, []).append(rsrc_id)
            # Collect resource calendar for this task
            if rsrc_id in rsrc_calendar:
                self._task_calendar_ids.setdefault(task_id, []).append(
                    rsrc_calendar[rsrc_id]
                )

    @property
    def network(self) -> ActivityNetwork:
        """The activity network used by this engine."""
        return self._network

    @property
    def calendar(self) -> CalendarEngine:
        """The calendar engine used by this engine."""
        return self._calendar

    @property
    def project_start(self) -> datetime:
        """The project start date for the simulation."""
        return self._project_start

    def _sim_hours_to_calendar(
        self, sim_hours: float, calendar_id: int | None
    ) -> datetime:
        """Convert simulation hours to a calendar datetime.

        Uses the calendar engine to skip non-work time.
        """
        cal_id = calendar_id if calendar_id is not None else -1
        return self._calendar.calculate_finish(
            cal_id, self._project_start, sim_hours
        )

    def _get_task_calendar(self, task_id: int) -> int | None:
        """Get the effective calendar for a task.

        Uses the intersection of all resource calendars assigned to the task.
        Falls back to the activity's own calendar_id if no resource
        calendars are available.
        """
        rsrc_cal_ids = self._task_calendar_ids.get(task_id)
        if rsrc_cal_ids:
            # Get or create the intersected calendar and register it
            intersected = self._calendar.get_intersected_calendar(rsrc_cal_ids)
            return intersected.calendar_id
        # Fall back to activity calendar
        activity = self._network.activities.get(task_id)
        if activity is not None:
            return activity.calendar_id
        return None

    def _sim_hours_to_calendar_for_task(
        self, sim_hours: float, task_id: int
    ) -> datetime:
        """Convert simulation hours to calendar datetime using the task's
        effective calendar (intersection of resource calendars)."""
        rsrc_cal_ids = self._task_calendar_ids.get(task_id)
        if rsrc_cal_ids:
            cal_def = self._calendar.get_intersected_calendar(rsrc_cal_ids)
            # Use calculate_finish directly with the intersected calendar
            return self._calendar.calculate_finish(
                cal_def.calendar_id, self._project_start, sim_hours
            )
        # Fall back to activity calendar
        activity = self._network.activities.get(task_id)
        cal_id = activity.calendar_id if activity else None
        return self._sim_hours_to_calendar(sim_hours, cal_id)

    def _convert_calendar_dates(self, result: SimulationResult) -> None:
        """Convert simulation hours to calendar datetimes for all activities.

        Uses the intersection of all resource calendars assigned to each task.
        Falls back to the activity's own calendar if no resources are assigned.
        Called once after a run completes, rather than during simulation.
        """
        for ar in result.activity_results.values():
            ar.sim_start_date = self._sim_hours_to_calendar_for_task(
                ar.sim_start_time, ar.task_id
            )
            ar.sim_finish_date = self._sim_hours_to_calendar_for_task(
                ar.sim_finish_time, ar.task_id
            )

        # Update project finish from the last activity
        if result.activity_results:
            last = max(result.activity_results.values(), key=lambda r: r.sim_finish_time)
            result.project_finish = last.sim_finish_date

    def _run_fast(self, run_id: int = 0) -> SimulationResult:
        """Fast-path simulation without SimPy for non-resource-constrained runs.

        Directly traverses the topological order and computes start/finish
        times using simple max() over predecessor constraints. Much faster
        than creating SimPy processes for every activity.
        """
        rng = np.random.default_rng(
            self._seed + run_id if self._seed is not None else None
        )

        result = SimulationResult(run_id=run_id, project_start=self._project_start)

        activity_starts: dict[int, float] = {}
        activity_finishes: dict[int, float] = {}

        for activity in self._topo_order:
            # Compute earliest start from all predecessors
            earliest = 0.0
            for rel in activity.predecessors:
                dur = activity.remaining_duration_hours
                constraint = _compute_earliest_start(
                    rel, activity_starts, activity_finishes, dur
                )
                if constraint > earliest:
                    earliest = constraint

            start_time = earliest

            # Sample duration based on remaining duration (for in-progress schedules)
            simulated_duration = self._duration_sampler(
                activity.remaining_duration_hours, rng
            )
            if activity.is_milestone:
                simulated_duration = 0.0

            finish_time = start_time + simulated_duration

            activity_starts[activity.task_id] = start_time
            activity_finishes[activity.task_id] = finish_time

            result.activity_results[activity.task_id] = ActivityResult(
                task_id=activity.task_id,
                proj_id=self._proj_ids.get(activity.task_id, 0),
                task_code=activity.task_code,
                task_name=activity.task_name,
                planned_duration_hours=activity.remaining_duration_hours,
                simulated_duration_hours=simulated_duration,
                sim_start_time=int(start_time),
                sim_finish_time=int(finish_time),
                wait_hours=0.0,
                is_critical=activity.is_critical,
            )

        # Calculate project duration
        if result.activity_results:
            result.project_duration_hours = max(
                r.sim_finish_time for r in result.activity_results.values()
            )

        return result

    def _run_simpy(self, run_id: int = 0) -> SimulationResult:
        """Full SimPy simulation with resource constraints.

        Used when resource_constrained=True. Creates SimPy processes
        for each activity with resource acquisition/release.
        """
        rng = np.random.default_rng(
            self._seed + run_id if self._seed is not None else None
        )

        env = simpy.Environment()
        result = SimulationResult(run_id=run_id, project_start=self._project_start)

        # Create SimPy resources
        simpy_resources: dict[int, simpy.Resource] = {}
        for rsrc_id, pool in self._resource_pools.items():
            simpy_resources[rsrc_id] = simpy.Resource(env, capacity=pool.capacity)
            pool.resource = simpy_resources[rsrc_id]

        # Track activity start and completion events
        start_events: dict[int, simpy.Event] = {}
        completion_events: dict[int, simpy.Event] = {}
        activity_starts: dict[int, float] = {}
        activity_finishes: dict[int, float] = {}

        for activity in self._topo_order:
            start_events[activity.task_id] = env.event()
            completion_events[activity.task_id] = env.event()

        def activity_process(
            env: simpy.Environment, activity: Activity
        ) -> simpy.events.Process:
            """SimPy process for a single activity."""
            for rel in activity.predecessors:
                if rel.rel_type in (RelationshipType.SS, RelationshipType.SF):
                    pred_event = start_events.get(rel.predecessor_id)
                else:
                    pred_event = completion_events.get(rel.predecessor_id)

                if pred_event is not None:
                    yield pred_event
                    earliest = _compute_earliest_start(
                        rel, activity_starts, activity_finishes,
                        activity.remaining_duration_hours,
                    )
                    if earliest > env.now:
                        yield env.timeout(earliest - env.now)

            # Sample duration based on remaining duration (for in-progress schedules)
            simulated_duration = self._duration_sampler(
                activity.remaining_duration_hours, rng
            )
            if activity.is_milestone:
                simulated_duration = 0.0

            # Acquire resources
            requests = []
            wait_start = env.now
            rsrc_ids = self._resource_assignments.get(activity.task_id, [])
            for rsrc_id in rsrc_ids:
                if rsrc_id in simpy_resources:
                    req = simpy_resources[rsrc_id].request()
                    requests.append((rsrc_id, req))
                    yield req

            wait_hours = env.now - wait_start
            start_time = env.now
            activity_starts[activity.task_id] = start_time
            start_events[activity.task_id].succeed()

            if simulated_duration > 0:
                yield env.timeout(simulated_duration)

            finish_time = env.now
            activity_finishes[activity.task_id] = finish_time

            for rsrc_id, req in requests:
                simpy_resources[rsrc_id].release(req)

            result.activity_results[activity.task_id] = ActivityResult(
                task_id=activity.task_id,
                proj_id=self._proj_ids.get(activity.task_id, 0),
                task_code=activity.task_code,
                task_name=activity.task_name,
                planned_duration_hours=activity.remaining_duration_hours,
                simulated_duration_hours=simulated_duration,
                sim_start_time=int(start_time),
                sim_finish_time=int(finish_time),
                wait_hours=wait_hours,
                is_critical=activity.is_critical,
            )
            completion_events[activity.task_id].succeed()

        for activity in self._topo_order:
            env.process(activity_process(env, activity))

        env.run()

        if result.activity_results:
            result.project_duration_hours = max(
                r.sim_finish_time for r in result.activity_results.values()
            )

        return result

    def run(
        self, run_id: int = 0, *, convert_calendar: bool = True
    ) -> SimulationResult:
        """Execute a single simulation run.

        Args:
            run_id: Identifier for this run (useful for Monte Carlo).
            convert_calendar: Whether to convert sim hours to calendar
                datetimes. Set to False for faster Monte Carlo runs when
                only project duration is needed.

        Returns:
            A SimulationResult with timing data for all activities.
        """
        if self._resource_constrained:
            result = self._run_simpy(run_id)
        else:
            result = self._run_fast(run_id)

        if convert_calendar:
            self._convert_calendar_dates(result)

        return result

    def run_monte_carlo(
        self, num_runs: int = 100, *, convert_calendar: bool = False
    ) -> list[SimulationResult]:
        """Execute multiple simulation runs for Monte Carlo analysis.

        Args:
            num_runs: Number of simulation runs to execute.
            convert_calendar: Whether to convert sim hours to calendar
                datetimes for every run. Defaults to False for performance.
                Calendar dates are only needed for visualization of
                individual runs, not for duration statistics.

        Returns:
            A list of SimulationResult objects, one per run.
        """
        return [
            self.run(run_id=i, convert_calendar=convert_calendar)
            for i in range(num_runs)
        ]

    def summary(self, result: SimulationResult) -> str:
        """Return a summary of a simulation result.

        Args:
            result: The SimulationResult to summarize.

        Returns:
            A multi-line string with key simulation metrics.
        """
        df = result.to_dataframe()
        critical = df[df["is_critical"]]

        lines = [
            f"Simulation Run #{result.run_id}",
            "",
            f"  Project start:    {result.project_start}",
            f"  Project finish:   {result.project_finish}",
            f"  Duration (hours): {result.project_duration_hours:.1f}",
            f"  Activities:       {len(df)}",
            f"  Critical:         {len(critical)}",
        ]

        if self._resource_constrained and len(df) > 0:
            total_wait = df["wait_hours"].sum()
            max_wait = df["wait_hours"].max()
            delayed = (df["wait_hours"] > 0).sum()
            lines.extend([
                "",
                f"  Resource delays:  {delayed} activities",
                f"  Total wait hours: {total_wait:.1f}",
                f"  Max wait hours:   {max_wait:.1f}",
            ])

        summary_text = "\n".join(lines)
        print(summary_text)
        return summary_text

    def monte_carlo_summary(self, results: list[SimulationResult]) -> str:
        """Return a statistical summary of Monte Carlo results.

        Args:
            results: List of SimulationResult objects from run_monte_carlo().

        Returns:
            A multi-line string with percentile statistics.
        """
        durations = np.array([r.project_duration_hours for r in results])

        lines = [
            f"Monte Carlo Summary ({len(results)} runs)",
            "",
            f"  Mean duration:   {np.mean(durations):.1f} hours",
            f"  Std deviation:   {np.std(durations):.1f} hours",
            f"  Min duration:    {np.min(durations):.1f} hours",
            f"  P10 duration:    {np.percentile(durations, 10):.1f} hours",
            f"  P50 duration:    {np.percentile(durations, 50):.1f} hours",
            f"  P80 duration:    {np.percentile(durations, 80):.1f} hours",
            f"  P90 duration:    {np.percentile(durations, 90):.1f} hours",
            f"  Max duration:    {np.max(durations):.1f} hours",
        ]

        summary_text = "\n".join(lines)
        print(summary_text)
        return summary_text
