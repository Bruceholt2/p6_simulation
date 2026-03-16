"""Calendar engine for P6 schedule simulation.

Parses P6 calendar definitions (clndr_data strings) and provides methods
to convert between work hours and calendar time, respecting work schedules
and exception dates (holidays, modified work days).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Sequence

import pandas as pd

from src.xer_parser import XERParser


# P6 serial dates use the same epoch as Excel/OLE Automation
_P6_EPOCH = datetime(1899, 12, 30)


@dataclass
class WorkPeriod:
    """A single work period within a day (e.g., 08:00–12:00).

    Attributes:
        start: Start time of the work period.
        finish: End time of the work period.
    """

    start: time
    finish: time

    @property
    def hours(self) -> float:
        """Duration of this work period in hours."""
        s = self.start.hour + self.start.minute / 60
        f = self.finish.hour + self.finish.minute / 60
        return f - s


@dataclass
class DaySchedule:
    """Work schedule for a single day.

    Attributes:
        periods: Ordered list of work periods. Empty means non-work day.
    """

    periods: list[WorkPeriod] = field(default_factory=list)

    @property
    def is_workday(self) -> bool:
        """True if this day has any work periods."""
        return len(self.periods) > 0

    @property
    def total_hours(self) -> float:
        """Total work hours for this day."""
        return sum(p.hours for p in self.periods)

    @property
    def earliest_start(self) -> time | None:
        """Earliest work start time, or None for non-work days."""
        return self.periods[0].start if self.periods else None

    @property
    def latest_finish(self) -> time | None:
        """Latest work finish time, or None for non-work days."""
        return self.periods[-1].finish if self.periods else None


@dataclass
class CalendarDefinition:
    """Parsed P6 calendar with weekly schedule and exceptions.

    Attributes:
        calendar_id: Unique calendar identifier.
        name: Calendar name.
        week_schedule: Work schedule for each day of week (0=Monday .. 6=Sunday).
        exceptions: Date-specific schedule overrides. Maps date to DaySchedule
            (empty DaySchedule means holiday/non-work).
    """

    calendar_id: int
    name: str
    week_schedule: list[DaySchedule] = field(
        default_factory=lambda: [DaySchedule() for _ in range(7)]
    )
    exceptions: dict[datetime, DaySchedule] = field(default_factory=dict)


def _parse_time(s: str) -> time:
    """Parse a time string like '08:00' or '0800' into a time object."""
    s = s.strip()
    if ":" in s:
        parts = s.split(":")
        return time(int(parts[0]), int(parts[1]))
    # Handle 4-digit format like '0800'
    return time(int(s[:2]), int(s[2:]))


def _parse_work_periods(text: str) -> list[WorkPeriod]:
    """Extract work periods from a calendar data fragment.

    Looks for patterns like (s|08:00|f|12:00) or (s|08:00|f|16:00).
    """
    periods: list[WorkPeriod] = []
    # Match (0||N(s|HH:MM|f|HH:MM)(...)) patterns
    pattern = r"\(s\|(\d{2}:\d{2})\|f\|(\d{2}:\d{2})\)"
    for match in re.finditer(pattern, text):
        start = _parse_time(match.group(1))
        finish = _parse_time(match.group(2))
        if start < finish:
            periods.append(WorkPeriod(start=start, finish=finish))
    periods.sort(key=lambda p: p.start)
    return periods


def _serial_to_date(serial: int) -> datetime:
    """Convert a P6/Excel serial day number to a datetime."""
    return _P6_EPOCH + timedelta(days=serial)


def _find_balanced_block(text: str, start: int) -> str:
    """Extract content of a balanced parenthesized block starting at '('.

    Args:
        text: The full string.
        start: Index of the opening '('.

    Returns:
        The substring between the opening '(' and its matching ')' (exclusive).
    """
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]
    return text[start + 1 :]


def _extract_section(data: str, section_name: str) -> str | None:
    """Find a named section like DaysOfWeek(...)(CONTENT) and return CONTENT.

    P6 sections follow the pattern: (0||SectionName(params)(children))
    """
    idx = data.find(section_name)
    if idx == -1:
        return None

    # Find the children block — second '(' after the section name+params
    pos = idx + len(section_name)
    # Skip the params block: (...)
    paren_count = 0
    while pos < len(data):
        if data[pos] == "(":
            paren_count += 1
            if paren_count == 1:
                # Skip past this params block
                block = _find_balanced_block(data, pos)
                pos += len(block) + 2  # +2 for the ( and )
                break
        pos += 1

    # Now pos should be at the children block '('
    if pos < len(data) and data[pos] == "(":
        return _find_balanced_block(data, pos)

    return None


def _parse_clndr_data(clndr_data: str) -> tuple[list[DaySchedule], dict[datetime, DaySchedule]]:
    """Parse a P6 clndr_data string into weekly schedule and exceptions.

    Returns:
        Tuple of (week_schedule, exceptions) where week_schedule is a list
        of 7 DaySchedule objects (0=Monday .. 6=Sunday).
    """
    week_schedule = [DaySchedule() for _ in range(7)]
    exceptions: dict[datetime, DaySchedule] = {}

    if not clndr_data or pd.isna(clndr_data):
        return week_schedule, exceptions

    data = str(clndr_data)

    # P6 day numbers: 1=Sunday, 2=Monday, ..., 7=Saturday
    # Python weekday(): 0=Monday, 1=Tuesday, ..., 6=Sunday
    p6_to_python = {1: 6, 2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5}

    # --- Parse DaysOfWeek section ---
    dow_content = _extract_section(data, "DaysOfWeek")
    if dow_content:
        # Find each day marker: (0||N()(...)
        day_positions = list(re.finditer(r"\(0\|\|(\d)\(\)", dow_content))
        for i, match in enumerate(day_positions):
            day_num = int(match.group(1))
            python_day = p6_to_python.get(day_num)
            if python_day is None:
                continue

            # Extract text from this day marker to the next day marker (or end)
            start_pos = match.end()
            if i + 1 < len(day_positions):
                end_pos = day_positions[i + 1].start()
            else:
                end_pos = len(dow_content)

            day_text = dow_content[start_pos:end_pos]
            periods = _parse_work_periods(day_text)
            week_schedule[python_day] = DaySchedule(periods=periods)

    # --- Parse Exceptions section ---
    exc_content = _extract_section(data, "Exceptions")
    if exc_content:
        # Find exception entries: (0||N(d|SERIAL)(...))
        exc_positions = list(re.finditer(r"\(0\|\|\d+\(d\|(\d+)\)", exc_content))
        for i, match in enumerate(exc_positions):
            serial = int(match.group(1))

            # Extract text from this exception to the next (or end)
            start_pos = match.end()
            if i + 1 < len(exc_positions):
                end_pos = exc_positions[i + 1].start()
            else:
                end_pos = len(exc_content)

            exc_text = exc_content[start_pos:end_pos]
            exc_date = _serial_to_date(serial)
            periods = _parse_work_periods(exc_text)
            exceptions[exc_date] = DaySchedule(periods=periods)

    return week_schedule, exceptions


def _default_calendar() -> CalendarDefinition:
    """Create a default 5-day, 8-hour calendar (Mon-Fri, 08:00-12:00, 13:00-17:00)."""
    am = WorkPeriod(start=time(8, 0), finish=time(12, 0))
    pm = WorkPeriod(start=time(13, 0), finish=time(17, 0))
    week = [DaySchedule() for _ in range(7)]
    for day in range(5):  # Monday through Friday
        week[day] = DaySchedule(periods=[am, pm])
    # Saturday (5) and Sunday (6) remain non-work
    return CalendarDefinition(
        calendar_id=-1,
        name="Default 5-Day 8-Hour",
        week_schedule=week,
    )


def _intersect_periods(a: list[WorkPeriod], b: list[WorkPeriod]) -> list[WorkPeriod]:
    """Return the intersection of two lists of work periods.

    Only time ranges present in BOTH lists are kept.
    """
    result: list[WorkPeriod] = []
    for pa in a:
        for pb in b:
            start = max(pa.start, pb.start)
            finish = min(pa.finish, pb.finish)
            if start < finish:
                result.append(WorkPeriod(start=start, finish=finish))
    result.sort(key=lambda p: p.start)
    return result


def _intersect_day_schedules(a: DaySchedule, b: DaySchedule) -> DaySchedule:
    """Return a DaySchedule with only the overlapping work periods."""
    return DaySchedule(periods=_intersect_periods(a.periods, b.periods))


def intersect_calendars(calendars: list[CalendarDefinition]) -> CalendarDefinition:
    """Create a new calendar from the intersection of multiple calendars.

    The resulting calendar only has work periods where ALL input calendars
    have work periods. Exceptions from all calendars are merged — if any
    calendar has a non-work exception on a date, that date is non-work
    in the intersection.

    Args:
        calendars: List of CalendarDefinition objects to intersect.

    Returns:
        A new CalendarDefinition representing the intersection.
    """
    if not calendars:
        return CalendarDefinition(calendar_id=-1, name="Empty Intersection")
    if len(calendars) == 1:
        return calendars[0]

    # Intersect weekly schedules
    week = list(calendars[0].week_schedule)
    for cal in calendars[1:]:
        week = [
            _intersect_day_schedules(week[d], cal.week_schedule[d])
            for d in range(7)
        ]

    # Merge all exceptions — union of exception dates
    # For each exception date, intersect the effective schedules from all calendars
    all_exc_dates: set[datetime] = set()
    for cal in calendars:
        all_exc_dates.update(cal.exceptions.keys())

    exceptions: dict[datetime, DaySchedule] = {}
    for exc_date in all_exc_dates:
        # Get effective schedule for this date from each calendar
        day_schedules = []
        for cal in calendars:
            if exc_date in cal.exceptions:
                day_schedules.append(cal.exceptions[exc_date])
            else:
                # No exception — use the standard weekly schedule
                day_schedules.append(cal.week_schedule[exc_date.weekday()])

        # Intersect all day schedules for this date
        intersected = day_schedules[0]
        for ds in day_schedules[1:]:
            intersected = _intersect_day_schedules(intersected, ds)
        exceptions[exc_date] = intersected

    cal_ids = [c.calendar_id for c in calendars]
    return CalendarDefinition(
        calendar_id=-1,
        name=f"Intersection({','.join(str(i) for i in cal_ids)})",
        week_schedule=week,
        exceptions=exceptions,
    )


class CalendarEngine:
    """Engine for calendar-aware time calculations.

    Loads calendar definitions from an XERParser and provides methods
    to convert between work hours and calendar dates.

    Args:
        parser: An XERParser instance with loaded calendar data.
    """

    def __init__(self, parser: XERParser) -> None:
        self._calendars: dict[int, CalendarDefinition] = {}
        self._default = _default_calendar()
        self._intersection_cache: dict[tuple[int, ...], CalendarDefinition] = {}
        self._load_calendars(parser)

    def _load_calendars(self, parser: XERParser) -> None:
        """Parse all calendar definitions from the XER data."""
        cal_df = parser.calendars

        for _, row in cal_df.iterrows():
            cal_id = int(row["clndr_id"])
            name = str(row.get("clndr_name", ""))
            clndr_data = row.get("clndr_data", "")

            try:
                week_schedule, exceptions = _parse_clndr_data(clndr_data)
                cal_def = CalendarDefinition(
                    calendar_id=cal_id,
                    name=name,
                    week_schedule=week_schedule,
                    exceptions=exceptions,
                )
            except Exception:
                # Fall back to default if parsing fails
                cal_def = CalendarDefinition(
                    calendar_id=cal_id,
                    name=name,
                    week_schedule=list(self._default.week_schedule),
                )

            self._calendars[cal_id] = cal_def

    def get_calendar(self, calendar_id: int) -> CalendarDefinition:
        """Return the CalendarDefinition for a given ID, or the default."""
        return self._calendars.get(calendar_id, self._default)

    def get_intersected_calendar(
        self, calendar_ids: list[int]
    ) -> CalendarDefinition:
        """Return the intersection of multiple calendars, with caching.

        Args:
            calendar_ids: List of calendar IDs to intersect.

        Returns:
            A CalendarDefinition where only work periods common to ALL
            calendars are retained.
        """
        # Deduplicate and sort for consistent cache keys
        unique_ids = sorted(set(calendar_ids))
        if len(unique_ids) == 0:
            return self._default
        if len(unique_ids) == 1:
            return self.get_calendar(unique_ids[0])

        cache_key = tuple(unique_ids)
        if cache_key in self._intersection_cache:
            return self._intersection_cache[cache_key]

        cals = [self.get_calendar(cid) for cid in unique_ids]
        intersected = intersect_calendars(cals)
        # Assign a unique negative ID and register in the calendar store
        intersected.calendar_id = -(len(self._intersection_cache) + 2)
        self._calendars[intersected.calendar_id] = intersected
        self._intersection_cache[cache_key] = intersected
        return intersected

    def _get_day_schedule(self, calendar_id: int, dt: datetime) -> DaySchedule:
        """Get the effective DaySchedule for a specific date, considering exceptions."""
        cal = self.get_calendar(calendar_id)
        # Check exceptions first (normalize to midnight for lookup)
        date_key = datetime(dt.year, dt.month, dt.day)
        if date_key in cal.exceptions:
            return cal.exceptions[date_key]
        # Fall back to standard weekly schedule
        return cal.week_schedule[dt.weekday()]

    def is_work_time(self, calendar_id: int, dt: datetime) -> bool:
        """Check if a given datetime falls within a work period.

        Args:
            calendar_id: The calendar to check against.
            dt: The datetime to check.

        Returns:
            True if dt is during a work period.
        """
        schedule = self._get_day_schedule(calendar_id, dt)
        t = dt.time()
        for period in schedule.periods:
            if period.start <= t < period.finish:
                return True
        return False

    def get_work_hours_per_day(self, calendar_id: int, day_of_week: int) -> float:
        """Return standard work hours for a weekday (0=Monday .. 6=Sunday).

        Args:
            calendar_id: The calendar to check.
            day_of_week: Day of week (0=Monday, 6=Sunday).

        Returns:
            Total scheduled work hours for that day.
        """
        cal = self.get_calendar(calendar_id)
        return cal.week_schedule[day_of_week].total_hours

    def next_work_start(self, calendar_id: int, dt: datetime) -> datetime:
        """Find the next work period start at or after the given datetime.

        Args:
            calendar_id: The calendar to use.
            dt: The starting datetime.

        Returns:
            The datetime when the next work period begins.
        """
        # If currently in a work period, return dt as-is
        schedule = self._get_day_schedule(calendar_id, dt)
        t = dt.time()
        for period in schedule.periods:
            if period.start <= t < period.finish:
                return dt

        # Check remaining periods today
        for period in schedule.periods:
            if t < period.start:
                return datetime.combine(dt.date(), period.start)

        # Move to next days until we find a work day
        current = datetime.combine(dt.date() + timedelta(days=1), time(0, 0))
        for _ in range(365):  # Safety limit
            day_sched = self._get_day_schedule(calendar_id, current)
            if day_sched.is_workday and day_sched.earliest_start is not None:
                return datetime.combine(current.date(), day_sched.earliest_start)
            current += timedelta(days=1)

        # Fallback — should not reach here with a valid calendar
        return dt

    def calculate_finish(
        self, calendar_id: int, start_datetime: datetime, work_hours: float
    ) -> datetime:
        """Calculate when an activity finishes given start time and work hours.

        All durations are in hours. Uses bulk week-skipping: divides remaining
        hours by hours-per-week to jump forward many weeks at once, using
        bisect to find the next exception boundary in O(log n).

        Args:
            calendar_id: The calendar to use.
            start_datetime: When the activity starts.
            work_hours: Total work hours to schedule.

        Returns:
            The datetime when the activity finishes.
        """
        if work_hours <= 0:
            return start_datetime

        remaining = work_hours
        current = self.next_work_start(calendar_id, start_datetime)
        cal = self.get_calendar(calendar_id)

        # Precompute weekly hours from the standard schedule
        weekly_hours = sum(s.total_hours for s in cal.week_schedule)

        # Sorted exception dates for bisect lookup
        exc_dates = sorted(cal.exceptions.keys()) if cal.exceptions else []

        # Bulk week-skip when remaining hours span many weeks
        if weekly_hours > 0 and remaining > weekly_hours * 2:
            # Consume partial first week day-by-day to align to Monday
            days_until_monday = (7 - current.weekday()) % 7
            for _ in range(days_until_monday):
                remaining = self._consume_day_hours(cal, current, remaining)
                if remaining <= 0:
                    return self._finish_in_day(
                        cal, current,
                        remaining + self._day_available(cal, current),
                    )
                current = self._advance_to_next_workday(calendar_id, current)

            # Now on a Monday — bulk skip using bisect
            import bisect

            while remaining > weekly_hours + 1e-9:
                # How many clean weeks can we skip?
                max_weeks = int(remaining / weekly_hours)
                if max_weeks < 1:
                    break

                skip_end = datetime(
                    current.year, current.month, current.day
                ) + timedelta(weeks=max_weeks)

                # Use bisect to find if any exception falls in [current, skip_end)
                idx = bisect.bisect_left(exc_dates, current)
                if idx < len(exc_dates) and exc_dates[idx] < skip_end:
                    # Exception found — only skip up to the week containing it
                    exc_dt = exc_dates[idx]
                    # Align to the Monday before the exception
                    days_to_exc_monday = (exc_dt - current).days
                    safe_weeks = days_to_exc_monday // 7
                    if safe_weeks > 0:
                        remaining -= weekly_hours * safe_weeks
                        current = datetime(
                            current.year, current.month, current.day
                        ) + timedelta(weeks=safe_weeks)
                        current = self.next_work_start(calendar_id, current)
                    # Process the exception week day-by-day
                    for _ in range(7):
                        if remaining <= 0:
                            break
                        remaining = self._consume_day_hours(
                            cal, current, remaining
                        )
                        if remaining <= 0:
                            return self._finish_in_day(
                                cal, current,
                                remaining + self._day_available(cal, current),
                            )
                        current = self._advance_to_next_workday(
                            calendar_id, current
                        )
                else:
                    # No exceptions in range — skip all weeks at once
                    remaining -= weekly_hours * max_weeks
                    current = datetime(
                        current.year, current.month, current.day
                    ) + timedelta(weeks=max_weeks)
                    current = self.next_work_start(calendar_id, current)

        # Day-by-day for the remaining hours (typically < 2 weeks)
        for _ in range(10000):  # Safety limit
            schedule = self._get_day_schedule(calendar_id, current)
            t = current.time()

            for period in schedule.periods:
                if t >= period.finish:
                    continue

                effective_start = max(t, period.start)
                available = (
                    (period.finish.hour + period.finish.minute / 60)
                    - (effective_start.hour + effective_start.minute / 60)
                )

                if remaining <= available + 1e-9:
                    finish_minutes = (
                        effective_start.hour * 60
                        + effective_start.minute
                        + remaining * 60
                    )
                    finish_hour = int(finish_minutes // 60)
                    finish_min = int(round(finish_minutes % 60))
                    if finish_min == 60:
                        finish_hour += 1
                        finish_min = 0
                    return datetime.combine(
                        current.date(), time(finish_hour, finish_min)
                    )

                remaining -= available

            next_day = datetime.combine(
                current.date() + timedelta(days=1), time(0, 0)
            )
            current = self.next_work_start(calendar_id, next_day)

        return current

    def _day_available(self, cal: CalendarDefinition, dt: datetime) -> float:
        """Total available work hours for a given date."""
        date_key = datetime(dt.year, dt.month, dt.day)
        if date_key in cal.exceptions:
            return cal.exceptions[date_key].total_hours
        return cal.week_schedule[dt.weekday()].total_hours

    def _consume_day_hours(
        self, cal: CalendarDefinition, dt: datetime, remaining: float
    ) -> float:
        """Subtract a full day's work hours from remaining. Returns new remaining."""
        return remaining - self._day_available(cal, dt)

    def _advance_to_next_workday(self, calendar_id: int, current: datetime) -> datetime:
        """Advance to the start of the next work day."""
        next_day = datetime.combine(
            current.date() + timedelta(days=1), time(0, 0)
        )
        return self.next_work_start(calendar_id, next_day)

    def _finish_in_day(
        self, cal: CalendarDefinition, dt: datetime, work_hours: float
    ) -> datetime:
        """Find the exact finish time within a day for the given work hours."""
        date_key = datetime(dt.year, dt.month, dt.day)
        if date_key in cal.exceptions:
            schedule = cal.exceptions[date_key]
        else:
            schedule = cal.week_schedule[dt.weekday()]

        consumed = 0.0
        for period in schedule.periods:
            available = period.hours
            if consumed + available >= work_hours - 1e-9:
                # Finish in this period
                hours_in_period = work_hours - consumed
                finish_minutes = (
                    period.start.hour * 60
                    + period.start.minute
                    + hours_in_period * 60
                )
                finish_hour = int(finish_minutes // 60)
                finish_min = int(round(finish_minutes % 60))
                if finish_min == 60:
                    finish_hour += 1
                    finish_min = 0
                return datetime.combine(dt.date(), time(finish_hour, finish_min))
            consumed += available

        return dt

    def calculate_work_hours_between(
        self, calendar_id: int, start_datetime: datetime, end_datetime: datetime
    ) -> float:
        """Calculate work hours between two datetimes.

        Args:
            calendar_id: The calendar to use.
            start_datetime: Start of the period.
            end_datetime: End of the period.

        Returns:
            Total work hours between start and end.
        """
        if end_datetime <= start_datetime:
            return 0.0

        total = 0.0
        current_date = start_datetime.date()
        end_date = end_datetime.date()

        while current_date <= end_date:
            dt = datetime.combine(current_date, time(0, 0))
            schedule = self._get_day_schedule(calendar_id, dt)

            for period in schedule.periods:
                period_start = datetime.combine(current_date, period.start)
                period_end = datetime.combine(current_date, period.finish)

                # Clamp to the query range
                effective_start = max(period_start, start_datetime)
                effective_end = min(period_end, end_datetime)

                if effective_start < effective_end:
                    delta = effective_end - effective_start
                    total += delta.total_seconds() / 3600

            current_date += timedelta(days=1)

        return total

    def summary(self) -> str:
        """Return a summary of loaded calendars.

        Returns:
            A multi-line string listing all calendars and their work patterns.
        """
        lines = [f"Calendars loaded: {len(self._calendars)}", ""]

        for cal in self._calendars.values():
            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            work_days = [
                day_names[i]
                for i, s in enumerate(cal.week_schedule)
                if s.is_workday
            ]
            hours = sum(s.total_hours for s in cal.week_schedule)
            n_exc = len(cal.exceptions)
            lines.append(
                f"  [{cal.calendar_id}] {cal.name}: "
                f"{', '.join(work_days)} ({hours:.0f} hrs/wk), "
                f"{n_exc} exceptions"
            )

        summary_text = "\n".join(lines)
        print(summary_text)
        return summary_text
