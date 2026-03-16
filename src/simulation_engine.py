"""SimPy-based discrete event simulation engine for P6 schedules.

Simulates project execution by processing activities in dependency order,
respecting resource constraints and calendar-aware durations. Supports
deterministic and stochastic (Monte Carlo) duration modeling.
"""

from __future__ import annotations

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
        task_code: User-visible activity code.
        task_name: Activity description.
        planned_duration_hours: Original planned duration.
        simulated_duration_hours: Duration used in this simulation run.
        sim_start: Simulation start time (hours from sim epoch).
        sim_finish: Simulation finish time (hours from sim epoch).
        calendar_start: Calendar datetime when activity started.
        calendar_finish: Calendar datetime when activity finished.
        wait_hours: Hours spent waiting for resources.
        is_critical: Whether the activity was on the critical path.
    """

    task_id: int
    task_code: str
    task_name: str
    planned_duration_hours: float
    simulated_duration_hours: float
    sim_start: float
    sim_finish: float
    calendar_start: datetime | None = None
    calendar_finish: datetime | None = None
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
                "task_code": r.task_code,
                "task_name": r.task_name,
                "planned_duration_hours": r.planned_duration_hours,
                "simulated_duration_hours": r.simulated_duration_hours,
                "sim_start": r.sim_start,
                "sim_finish": r.sim_finish,
                "calendar_start": r.calendar_start,
                "calendar_finish": r.calendar_finish,
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

        # Build resource pools
        self._resource_pools: dict[int, ResourcePool] = {}
        self._resource_assignments: dict[int, list[int]] = {}  # task_id -> [rsrc_id]
        if resource_constrained:
            self._build_resource_pools()

    def _infer_project_start(self) -> datetime:
        """Determine project start from the earliest early_start date."""
        tasks = self._parser.tasks
        if "early_start_date" in tasks.columns:
            valid = tasks["early_start_date"].dropna()
            if len(valid) > 0:
                return valid.min().to_pydatetime()
        return datetime(2025, 1, 1, 8, 0)

    def _build_resource_pools(self) -> None:
        """Create resource pools from XER resource and rate data."""
        resources = self._parser.resources
        try:
            rates = self._parser.get_table("RSRCRATE")
        except KeyError:
            rates = pd.DataFrame()

        # Build capacity lookup from rates
        capacity_map: dict[int, float] = {}
        if len(rates) > 0 and "max_qty_per_hr" in rates.columns:
            for _, row in rates.iterrows():
                rsrc_id = int(row["rsrc_id"])
                cap = float(row.get("max_qty_per_hr", 1) or 1)
                # Use the highest capacity if multiple rates exist
                capacity_map[rsrc_id] = max(capacity_map.get(rsrc_id, 0), cap)

        for _, row in resources.iterrows():
            rsrc_id = int(row["rsrc_id"])
            name = str(row.get("rsrc_name", f"Resource-{rsrc_id}"))
            capacity = capacity_map.get(rsrc_id, 1.0)
            # Convert capacity to integer units for SimPy Resource
            # (SimPy uses integer capacity for Resource)
            int_capacity = max(1, int(capacity))
            self._resource_pools[rsrc_id] = ResourcePool(
                rsrc_id=rsrc_id,
                name=name,
                capacity=int_capacity,
            )

        # Build task -> resource assignments
        assignments = self._parser.resource_assignments
        for _, row in assignments.iterrows():
            task_id = int(row["task_id"])
            rsrc_id = int(row["rsrc_id"])
            if rsrc_id in self._resource_pools:
                self._resource_assignments.setdefault(task_id, []).append(rsrc_id)

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

    def run(self, run_id: int = 0) -> SimulationResult:
        """Execute a single simulation run.

        Args:
            run_id: Identifier for this run (useful for Monte Carlo).

        Returns:
            A SimulationResult with timing data for all activities.
        """
        rng = np.random.default_rng(
            self._seed + run_id if self._seed is not None else None
        )

        env = simpy.Environment()
        result = SimulationResult(run_id=run_id, project_start=self._project_start)

        # Create SimPy resources
        simpy_resources: dict[int, simpy.Resource] = {}
        if self._resource_constrained:
            for rsrc_id, pool in self._resource_pools.items():
                simpy_resources[rsrc_id] = simpy.Resource(env, capacity=pool.capacity)
                pool.resource = simpy_resources[rsrc_id]

        # Track activity start and completion events
        start_events: dict[int, simpy.Event] = {}
        completion_events: dict[int, simpy.Event] = {}
        # Track activity start/finish sim times
        activity_starts: dict[int, float] = {}
        activity_finishes: dict[int, float] = {}

        topo_order = self._network.topological_order()

        for activity in topo_order:
            start_events[activity.task_id] = env.event()
            completion_events[activity.task_id] = env.event()

        def activity_process(
            env: simpy.Environment, activity: Activity
        ) -> simpy.events.Process:
            """SimPy process for a single activity."""
            # Wait for predecessor constraints, choosing the right event
            # based on relationship type
            for rel in activity.predecessors:
                # FS/FF wait on predecessor completion; SS/SF wait on start
                if rel.rel_type in (
                    RelationshipType.SS,
                    RelationshipType.SF,
                ):
                    pred_event = start_events.get(rel.predecessor_id)
                else:
                    pred_event = completion_events.get(rel.predecessor_id)

                if pred_event is not None:
                    yield pred_event

                    # Apply lag based on relationship type
                    pred_finish = activity_finishes.get(rel.predecessor_id, 0)
                    pred_start = activity_starts.get(rel.predecessor_id, 0)

                    if rel.rel_type == RelationshipType.FS:
                        earliest = pred_finish + rel.lag_hours
                    elif rel.rel_type == RelationshipType.SS:
                        earliest = pred_start + rel.lag_hours
                    elif rel.rel_type == RelationshipType.FF:
                        # FF: successor finish >= pred finish + lag
                        # Approximate: successor start >= pred finish + lag - duration
                        dur = activity.original_duration_hours
                        earliest = pred_finish + rel.lag_hours - dur
                    elif rel.rel_type == RelationshipType.SF:
                        dur = activity.original_duration_hours
                        earliest = pred_start + rel.lag_hours - dur
                    else:
                        earliest = pred_finish + rel.lag_hours

                    # Wait until the earliest allowed start
                    if earliest > env.now:
                        yield env.timeout(earliest - env.now)

            # Sample duration
            simulated_duration = self._duration_sampler(
                activity.original_duration_hours, rng
            )
            if activity.is_milestone:
                simulated_duration = 0.0

            # Acquire resources if constrained
            requests = []
            wait_start = env.now
            if self._resource_constrained:
                rsrc_ids = self._resource_assignments.get(activity.task_id, [])
                for rsrc_id in rsrc_ids:
                    if rsrc_id in simpy_resources:
                        req = simpy_resources[rsrc_id].request()
                        requests.append((rsrc_id, req))
                        yield req

            wait_hours = env.now - wait_start
            start_time = env.now
            activity_starts[activity.task_id] = start_time

            # Signal that this activity has started (for SS/SF successors)
            start_events[activity.task_id].succeed()

            # Execute the activity
            if simulated_duration > 0:
                yield env.timeout(simulated_duration)

            finish_time = env.now
            activity_finishes[activity.task_id] = finish_time

            # Release resources
            for rsrc_id, req in requests:
                simpy_resources[rsrc_id].release(req)

            # Convert sim times to calendar datetimes
            cal_id = activity.calendar_id
            cal_start = self._sim_hours_to_calendar(start_time, cal_id)
            cal_finish = self._sim_hours_to_calendar(finish_time, cal_id)

            result.activity_results[activity.task_id] = ActivityResult(
                task_id=activity.task_id,
                task_code=activity.task_code,
                task_name=activity.task_name,
                planned_duration_hours=activity.original_duration_hours,
                simulated_duration_hours=simulated_duration,
                sim_start=start_time,
                sim_finish=finish_time,
                calendar_start=cal_start,
                calendar_finish=cal_finish,
                wait_hours=wait_hours,
                is_critical=activity.is_critical,
            )

            # Signal completion
            completion_events[activity.task_id].succeed()

        # Start all activity processes
        for activity in topo_order:
            env.process(activity_process(env, activity))

        # Run the simulation
        env.run()

        # Calculate project totals
        if result.activity_results:
            max_finish = max(r.sim_finish for r in result.activity_results.values())
            result.project_duration_hours = max_finish

            # Find the last finishing activity for calendar finish
            last_activity = max(
                result.activity_results.values(), key=lambda r: r.sim_finish
            )
            result.project_finish = last_activity.calendar_finish

        return result

    def run_monte_carlo(self, num_runs: int = 100) -> list[SimulationResult]:
        """Execute multiple simulation runs for Monte Carlo analysis.

        Args:
            num_runs: Number of simulation runs to execute.

        Returns:
            A list of SimulationResult objects, one per run.
        """
        return [self.run(run_id=i) for i in range(num_runs)]

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
