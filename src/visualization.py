"""Visualization module for P6 schedule simulation results.

Generates Gantt charts, duration histograms, S-curves, and resource
utilization charts from simulation output using matplotlib.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Sequence

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for file output

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

from src.simulation_engine import ActivityResult, SimulationResult


def gantt_chart(
    result: SimulationResult,
    *,
    top_n: int | None = 50,
    show_critical: bool = True,
    use_calendar_dates: bool = True,
    title: str = "Simulated Schedule — Gantt Chart",
    figsize: tuple[float, float] = (14, 8),
    save_path: str | Path | None = None,
) -> plt.Figure:
    """Generate a Gantt chart from a single simulation run.

    Args:
        result: A SimulationResult from the simulation engine.
        top_n: Maximum number of activities to display (longest first).
            None shows all.
        show_critical: Highlight critical path activities in red.
        use_calendar_dates: Use calendar datetimes on the x-axis.
            If False, uses simulation hours.
        title: Chart title.
        figsize: Figure size (width, height) in inches.
        save_path: If provided, save the figure to this path.

    Returns:
        The matplotlib Figure object.
    """
    df = result.to_dataframe()
    if df.empty:
        fig, ax = plt.subplots(figsize=figsize)
        ax.set_title(title)
        ax.text(0.5, 0.5, "No activities to display", ha="center", va="center",
                transform=ax.transAxes)
        plt.close(fig)
        return fig

    # Sort by start time, then by duration (longest first for visibility)
    df = df.sort_values("sim_start", ascending=True)

    # Limit to top_n longest activities
    if top_n is not None and len(df) > top_n:
        df = df.nlargest(top_n, "simulated_duration_hours")
        df = df.sort_values("sim_start", ascending=True)

    fig, ax = plt.subplots(figsize=figsize)

    y_labels = []
    for i, (_, row) in enumerate(df.iterrows()):
        label = f"{row['task_code']} — {row['task_name']}"
        if len(label) > 40:
            label = label[:37] + "..."
        y_labels.append(label)

        if use_calendar_dates and row["calendar_start"] is not None:
            start = mdates.date2num(row["calendar_start"])
            finish = mdates.date2num(row["calendar_finish"])
            width = finish - start
        else:
            start = row["sim_start"]
            width = row["simulated_duration_hours"]

        color = "#e74c3c" if (show_critical and row["is_critical"]) else "#3498db"

        # Draw wait time in orange if present
        if row["wait_hours"] > 0 and not use_calendar_dates:
            wait_start = start - row["wait_hours"]
            ax.barh(i, row["wait_hours"], left=wait_start, height=0.6,
                    color="#f39c12", alpha=0.5)

        ax.barh(i, width, left=start, height=0.6, color=color, alpha=0.85,
                edgecolor="white", linewidth=0.5)

    ax.set_yticks(range(len(y_labels)))
    ax.set_yticklabels(y_labels, fontsize=7)
    ax.invert_yaxis()

    if use_calendar_dates and result.project_start is not None:
        ax.xaxis_date()
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        fig.autofmt_xdate(rotation=45)
        ax.set_xlabel("Date")
    else:
        ax.set_xlabel("Simulation Hours")

    ax.set_title(title)
    ax.grid(axis="x", alpha=0.3)

    # Legend
    legend_elements = [Patch(facecolor="#3498db", label="Non-Critical")]
    if show_critical:
        legend_elements.insert(0, Patch(facecolor="#e74c3c", label="Critical"))
    ax.legend(handles=legend_elements, loc="lower right", fontsize=8)

    fig.tight_layout()

    if save_path:
        fig.savefig(str(save_path), dpi=150, bbox_inches="tight")

    plt.close(fig)
    return fig


def duration_histogram(
    results: list[SimulationResult],
    *,
    bins: int = 30,
    percentiles: list[float] | None = None,
    title: str = "Monte Carlo — Project Duration Distribution",
    figsize: tuple[float, float] = (10, 6),
    save_path: str | Path | None = None,
) -> plt.Figure:
    """Generate a histogram of project durations from Monte Carlo results.

    Args:
        results: List of SimulationResult objects from Monte Carlo runs.
        bins: Number of histogram bins.
        percentiles: Percentiles to mark with vertical lines.
            Defaults to [10, 50, 80, 90].
        title: Chart title.
        figsize: Figure size (width, height) in inches.
        save_path: If provided, save the figure to this path.

    Returns:
        The matplotlib Figure object.
    """
    if percentiles is None:
        percentiles = [10, 50, 80, 90]

    durations = np.array([r.project_duration_hours for r in results])

    fig, ax = plt.subplots(figsize=figsize)

    ax.hist(durations, bins=bins, color="#3498db", alpha=0.7, edgecolor="white",
            label="Duration")

    # Percentile lines
    colors = ["#2ecc71", "#f39c12", "#e67e22", "#e74c3c"]
    for i, pct in enumerate(percentiles):
        value = np.percentile(durations, pct)
        color = colors[i % len(colors)]
        ax.axvline(value, color=color, linestyle="--", linewidth=1.5,
                   label=f"P{pct}: {value:.0f}h")

    # Mean line
    mean_val = np.mean(durations)
    ax.axvline(mean_val, color="black", linestyle="-", linewidth=1.5,
               label=f"Mean: {mean_val:.0f}h")

    ax.set_xlabel("Project Duration (Work Hours)")
    ax.set_ylabel("Frequency")
    ax.set_title(title)
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()

    if save_path:
        fig.savefig(str(save_path), dpi=150, bbox_inches="tight")

    plt.close(fig)
    return fig


def s_curve(
    result: SimulationResult,
    *,
    num_points: int = 200,
    title: str = "Cumulative Work Hours — S-Curve",
    figsize: tuple[float, float] = (10, 6),
    save_path: str | Path | None = None,
) -> plt.Figure:
    """Generate an S-curve showing cumulative work hours over time.

    Args:
        result: A SimulationResult from the simulation engine.
        num_points: Number of time points to evaluate.
        title: Chart title.
        figsize: Figure size (width, height) in inches.
        save_path: If provided, save the figure to this path.

    Returns:
        The matplotlib Figure object.
    """
    df = result.to_dataframe()
    if df.empty:
        fig, ax = plt.subplots(figsize=figsize)
        ax.set_title(title)
        plt.close(fig)
        return fig

    max_time = df["sim_finish"].max()
    if max_time <= 0:
        max_time = 1.0

    time_points = np.linspace(0, max_time, num_points)
    cumulative_hours = np.zeros(num_points)

    for _, row in df.iterrows():
        start = row["sim_start"]
        finish = row["sim_finish"]
        duration = row["simulated_duration_hours"]
        if duration <= 0:
            continue

        for j, t in enumerate(time_points):
            if t <= start:
                continue
            elif t >= finish:
                cumulative_hours[j] += duration
            else:
                # Proportional completion
                elapsed = t - start
                cumulative_hours[j] += elapsed

    total_work = df["simulated_duration_hours"].sum()

    fig, ax = plt.subplots(figsize=figsize)

    ax.plot(time_points, cumulative_hours, color="#3498db", linewidth=2,
            label="Cumulative Work Hours")
    ax.axhline(total_work, color="#e74c3c", linestyle="--", linewidth=1,
               alpha=0.7, label=f"Total: {total_work:.0f}h")

    ax.set_xlabel("Simulation Hours")
    ax.set_ylabel("Cumulative Work Hours")
    ax.set_title(title)
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)

    fig.tight_layout()

    if save_path:
        fig.savefig(str(save_path), dpi=150, bbox_inches="tight")

    plt.close(fig)
    return fig


def resource_utilization(
    result: SimulationResult,
    resource_assignments: dict[int, list[int]],
    resource_names: dict[int, str],
    *,
    num_points: int = 200,
    title: str = "Resource Utilization Over Time",
    figsize: tuple[float, float] = (12, 6),
    save_path: str | Path | None = None,
) -> plt.Figure:
    """Generate a stacked area chart of resource utilization over time.

    Args:
        result: A SimulationResult from the simulation engine.
        resource_assignments: Mapping of task_id -> list of rsrc_ids.
        resource_names: Mapping of rsrc_id -> resource name.
        num_points: Number of time points to evaluate.
        title: Chart title.
        figsize: Figure size (width, height) in inches.
        save_path: If provided, save the figure to this path.

    Returns:
        The matplotlib Figure object.
    """
    df = result.to_dataframe()
    if df.empty:
        fig, ax = plt.subplots(figsize=figsize)
        ax.set_title(title)
        plt.close(fig)
        return fig

    max_time = df["sim_finish"].max()
    if max_time <= 0:
        max_time = 1.0

    time_points = np.linspace(0, max_time, num_points)

    # Find all resources that are actually assigned
    active_resources: set[int] = set()
    for task_id in df["task_id"]:
        for rsrc_id in resource_assignments.get(task_id, []):
            active_resources.add(rsrc_id)

    if not active_resources:
        fig, ax = plt.subplots(figsize=figsize)
        ax.set_title(title)
        ax.text(0.5, 0.5, "No resource assignments", ha="center", va="center",
                transform=ax.transAxes)
        plt.close(fig)
        return fig

    # Calculate utilization per resource over time
    rsrc_ids = sorted(active_resources)
    utilization = {rsrc_id: np.zeros(num_points) for rsrc_id in rsrc_ids}

    for _, row in df.iterrows():
        task_id = row["task_id"]
        start = row["sim_start"]
        finish = row["sim_finish"]
        if finish <= start:
            continue
        assigned = resource_assignments.get(task_id, [])
        for rsrc_id in assigned:
            if rsrc_id in utilization:
                mask = (time_points >= start) & (time_points < finish)
                utilization[rsrc_id][mask] += 1

    fig, ax = plt.subplots(figsize=figsize)

    labels = [resource_names.get(rid, f"R-{rid}") for rid in rsrc_ids]
    data = np.array([utilization[rid] for rid in rsrc_ids])

    ax.stackplot(time_points, data, labels=labels, alpha=0.7)

    ax.set_xlabel("Simulation Hours")
    ax.set_ylabel("Concurrent Resource Units")
    ax.set_title(title)
    ax.legend(loc="upper right", fontsize=8, ncol=2)
    ax.grid(alpha=0.3)

    fig.tight_layout()

    if save_path:
        fig.savefig(str(save_path), dpi=150, bbox_inches="tight")

    plt.close(fig)
    return fig


def criticality_index(
    results: list[SimulationResult],
    *,
    top_n: int = 30,
    title: str = "Activity Criticality Index",
    figsize: tuple[float, float] = (10, 8),
    save_path: str | Path | None = None,
) -> plt.Figure:
    """Generate a horizontal bar chart of criticality index per activity.

    The criticality index is the percentage of Monte Carlo runs in which
    an activity appears on the critical path (zero total float).

    Args:
        results: List of SimulationResult objects from Monte Carlo runs.
        top_n: Number of most-critical activities to display.
        title: Chart title.
        figsize: Figure size (width, height) in inches.
        save_path: If provided, save the figure to this path.

    Returns:
        The matplotlib Figure object.
    """
    num_runs = len(results)
    if num_runs == 0:
        fig, ax = plt.subplots(figsize=figsize)
        ax.set_title(title)
        plt.close(fig)
        return fig

    # Count how often each activity is critical
    critical_counts: dict[int, int] = {}
    task_labels: dict[int, str] = {}

    for result in results:
        for task_id, ar in result.activity_results.items():
            if task_id not in task_labels:
                label = f"{ar.task_code} — {ar.task_name}"
                if len(label) > 40:
                    label = label[:37] + "..."
                task_labels[task_id] = label
            if ar.is_critical:
                critical_counts[task_id] = critical_counts.get(task_id, 0) + 1

    if not critical_counts:
        fig, ax = plt.subplots(figsize=figsize)
        ax.set_title(title)
        ax.text(0.5, 0.5, "No critical activities found", ha="center",
                va="center", transform=ax.transAxes)
        plt.close(fig)
        return fig

    # Sort by criticality and take top N
    sorted_items = sorted(critical_counts.items(), key=lambda x: x[1], reverse=True)
    if top_n is not None:
        sorted_items = sorted_items[:top_n]

    task_ids = [t[0] for t in sorted_items]
    indices = [t[1] / num_runs * 100 for t in sorted_items]
    labels = [task_labels[tid] for tid in task_ids]

    fig, ax = plt.subplots(figsize=figsize)

    colors = ["#e74c3c" if idx >= 80 else "#f39c12" if idx >= 50 else "#3498db"
              for idx in indices]

    y_pos = range(len(labels))
    ax.barh(y_pos, indices, color=colors, alpha=0.85, edgecolor="white")

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("Criticality Index (%)")
    ax.set_title(title)
    ax.set_xlim(0, 105)
    ax.grid(axis="x", alpha=0.3)

    # Legend
    legend_elements = [
        Patch(facecolor="#e74c3c", label=">= 80%"),
        Patch(facecolor="#f39c12", label=">= 50%"),
        Patch(facecolor="#3498db", label="< 50%"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=8)

    fig.tight_layout()

    if save_path:
        fig.savefig(str(save_path), dpi=150, bbox_inches="tight")

    plt.close(fig)
    return fig
