"""Tests for the calendar engine module."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from pathlib import Path

import pytest

from src.xer_parser import XERParser
from src.calendar_engine import (
    CalendarEngine,
    CalendarDefinition,
    DaySchedule,
    WorkPeriod,
    _parse_clndr_data,
    _serial_to_date,
)


# Minimal XER with one 5-day calendar (Mon-Fri, 08:00-12:00, 13:00-17:00)
# and one 7-day calendar (08:00-16:00 every day)
SAMPLE_XER = (
    "%T\tPROJECT\n"
    "%F\tproj_id\tproj_short_name\tlast_recalc_date\n"
    "%R\t100\tTESTPROJ\t2025-06-01 08:00\n"
    "%T\tCALENDAR\n"
    "%F\tclndr_id\tclndr_name\tclndr_data\n"
    "%R\t1\tStandard 5 Day\t"
    "(0||CalendarData()("
    "(0||DaysOfWeek()("
    "(0||1()())"                                              # Sun - no work
    "(0||2()((0||0(s|08:00|f|12:00)())(0||1(s|13:00|f|17:00)())))"  # Mon
    "(0||3()((0||0(s|08:00|f|12:00)())(0||1(s|13:00|f|17:00)())))"  # Tue
    "(0||4()((0||0(s|08:00|f|12:00)())(0||1(s|13:00|f|17:00)())))"  # Wed
    "(0||5()((0||0(s|08:00|f|12:00)())(0||1(s|13:00|f|17:00)())))"  # Thu
    "(0||6()((0||0(s|08:00|f|12:00)())(0||1(s|13:00|f|17:00)())))"  # Fri
    "(0||7()())))"                                            # Sat - no work
    "(0||Exceptions()("
    "(0||0(d|45651)())"       # 2024-12-25 - holiday (no work)
    "(0||1(d|45652)())"       # 2024-12-26 - holiday (no work)
    "))))\n"
    "%R\t2\t7 Day Calendar\t"
    "(0||CalendarData()("
    "(0||DaysOfWeek()("
    "(0||1()((0||0(s|08:00|f|16:00)())))"  # Sun
    "(0||2()((0||0(s|08:00|f|16:00)())))"  # Mon
    "(0||3()((0||0(s|08:00|f|16:00)())))"  # Tue
    "(0||4()((0||0(s|08:00|f|16:00)())))"  # Wed
    "(0||5()((0||0(s|08:00|f|16:00)())))"  # Thu
    "(0||6()((0||0(s|08:00|f|16:00)())))"  # Fri
    "(0||7()((0||0(s|08:00|f|16:00)())))))" # Sat
    "(0||Exceptions()())))\n"
    "%T\tTASK\n"
    "%F\ttask_id\tproj_id\ttask_code\ttask_name\n"
    "%R\t1\t100\tA1\tDummy\n"
    "%T\tTASKPRED\n"
    "%F\ttask_pred_id\ttask_id\tpred_task_id\tpred_type\tlag_hr_cnt\n"
    "%E\n"
)


@pytest.fixture
def engine(tmp_path: Path) -> CalendarEngine:
    """Return a CalendarEngine loaded with sample calendars."""
    f = tmp_path / "test.xer"
    f.write_text(SAMPLE_XER, encoding="utf-8")
    parser = XERParser(f)
    return CalendarEngine(parser)


# Calendar ID 1 = 5-day, 8hrs/day (8-12, 13-17), Mon-Fri
CAL_5DAY = 1
# Calendar ID 2 = 7-day, 8hrs/day (8-16), every day
CAL_7DAY = 2


class TestWorkPeriod:
    """Test WorkPeriod dataclass."""

    def test_hours(self) -> None:
        p = WorkPeriod(start=time(8, 0), finish=time(12, 0))
        assert p.hours == 4.0

    def test_hours_with_minutes(self) -> None:
        p = WorkPeriod(start=time(8, 30), finish=time(12, 0))
        assert p.hours == 3.5


class TestDaySchedule:
    """Test DaySchedule dataclass."""

    def test_workday(self) -> None:
        s = DaySchedule(periods=[WorkPeriod(time(8, 0), time(16, 0))])
        assert s.is_workday
        assert s.total_hours == 8.0

    def test_non_workday(self) -> None:
        s = DaySchedule()
        assert not s.is_workday
        assert s.total_hours == 0.0

    def test_split_day(self) -> None:
        s = DaySchedule(periods=[
            WorkPeriod(time(8, 0), time(12, 0)),
            WorkPeriod(time(13, 0), time(17, 0)),
        ])
        assert s.total_hours == 8.0
        assert s.earliest_start == time(8, 0)
        assert s.latest_finish == time(17, 0)


class TestSerialDate:
    """Test P6 serial date conversion."""

    def test_known_date(self) -> None:
        # 2024-12-25 as Excel serial = 45651
        dt = _serial_to_date(45651)
        assert dt.year == 2024
        assert dt.month == 12
        assert dt.day == 25


class TestCalendarParsing:
    """Test that calendars are parsed correctly from XER data."""

    def test_two_calendars_loaded(self, engine: CalendarEngine) -> None:
        cal1 = engine.get_calendar(CAL_5DAY)
        cal2 = engine.get_calendar(CAL_7DAY)
        assert cal1.calendar_id == 1
        assert cal2.calendar_id == 2

    def test_5day_weekday_hours(self, engine: CalendarEngine) -> None:
        # Monday (0) should have 8 hours
        assert engine.get_work_hours_per_day(CAL_5DAY, 0) == 8.0

    def test_5day_weekend_hours(self, engine: CalendarEngine) -> None:
        # Saturday (5) and Sunday (6) should have 0 hours
        assert engine.get_work_hours_per_day(CAL_5DAY, 5) == 0.0
        assert engine.get_work_hours_per_day(CAL_5DAY, 6) == 0.0

    def test_7day_every_day_hours(self, engine: CalendarEngine) -> None:
        for day in range(7):
            assert engine.get_work_hours_per_day(CAL_7DAY, day) == 8.0

    def test_5day_has_exceptions(self, engine: CalendarEngine) -> None:
        cal = engine.get_calendar(CAL_5DAY)
        assert len(cal.exceptions) == 2

    def test_default_calendar_fallback(self, engine: CalendarEngine) -> None:
        cal = engine.get_calendar(9999)  # Nonexistent
        assert cal.name == "Default 5-Day 8-Hour"
        assert engine.get_work_hours_per_day(9999, 0) == 8.0  # Monday
        assert engine.get_work_hours_per_day(9999, 5) == 0.0  # Saturday


class TestIsWorkTime:
    """Test the is_work_time method."""

    def test_during_morning_work(self, engine: CalendarEngine) -> None:
        # Monday 10:00 AM
        dt = datetime(2025, 7, 7, 10, 0)
        assert engine.is_work_time(CAL_5DAY, dt)

    def test_during_afternoon_work(self, engine: CalendarEngine) -> None:
        # Monday 14:00
        dt = datetime(2025, 7, 7, 14, 0)
        assert engine.is_work_time(CAL_5DAY, dt)

    def test_during_lunch(self, engine: CalendarEngine) -> None:
        # Monday 12:30 — lunch break
        dt = datetime(2025, 7, 7, 12, 30)
        assert not engine.is_work_time(CAL_5DAY, dt)

    def test_before_work(self, engine: CalendarEngine) -> None:
        # Monday 06:00
        dt = datetime(2025, 7, 7, 6, 0)
        assert not engine.is_work_time(CAL_5DAY, dt)

    def test_after_work(self, engine: CalendarEngine) -> None:
        # Monday 18:00
        dt = datetime(2025, 7, 7, 18, 0)
        assert not engine.is_work_time(CAL_5DAY, dt)

    def test_weekend(self, engine: CalendarEngine) -> None:
        # Saturday 10:00
        dt = datetime(2025, 7, 12, 10, 0)
        assert not engine.is_work_time(CAL_5DAY, dt)

    def test_holiday(self, engine: CalendarEngine) -> None:
        # 2024-12-25 is a holiday exception
        dt = datetime(2024, 12, 25, 10, 0)
        assert not engine.is_work_time(CAL_5DAY, dt)


class TestNextWorkStart:
    """Test the next_work_start method."""

    def test_during_work_returns_same(self, engine: CalendarEngine) -> None:
        # Monday 10:00 — already working
        dt = datetime(2025, 7, 7, 10, 0)
        assert engine.next_work_start(CAL_5DAY, dt) == dt

    def test_lunch_rolls_to_afternoon(self, engine: CalendarEngine) -> None:
        # Monday 12:30 — lunch break, next is 13:00
        dt = datetime(2025, 7, 7, 12, 30)
        expected = datetime(2025, 7, 7, 13, 0)
        assert engine.next_work_start(CAL_5DAY, dt) == expected

    def test_saturday_rolls_to_monday(self, engine: CalendarEngine) -> None:
        # Saturday 10:00 -> Monday 08:00
        dt = datetime(2025, 7, 12, 10, 0)
        expected = datetime(2025, 7, 14, 8, 0)
        assert engine.next_work_start(CAL_5DAY, dt) == expected

    def test_sunday_rolls_to_monday(self, engine: CalendarEngine) -> None:
        # Sunday 15:00 -> Monday 08:00
        dt = datetime(2025, 7, 13, 15, 0)
        expected = datetime(2025, 7, 14, 8, 0)
        assert engine.next_work_start(CAL_5DAY, dt) == expected

    def test_before_work_rolls_to_start(self, engine: CalendarEngine) -> None:
        # Monday 06:00 -> Monday 08:00
        dt = datetime(2025, 7, 7, 6, 0)
        expected = datetime(2025, 7, 7, 8, 0)
        assert engine.next_work_start(CAL_5DAY, dt) == expected

    def test_after_work_rolls_to_next_day(self, engine: CalendarEngine) -> None:
        # Monday 18:00 -> Tuesday 08:00
        dt = datetime(2025, 7, 7, 18, 0)
        expected = datetime(2025, 7, 8, 8, 0)
        assert engine.next_work_start(CAL_5DAY, dt) == expected


class TestCalculateFinish:
    """Test the calculate_finish method."""

    def test_within_same_period(self, engine: CalendarEngine) -> None:
        # 2 hours starting Monday 08:00 -> Monday 10:00
        start = datetime(2025, 7, 7, 8, 0)
        finish = engine.calculate_finish(CAL_5DAY, start, 2.0)
        assert finish == datetime(2025, 7, 7, 10, 0)

    def test_spans_lunch_break(self, engine: CalendarEngine) -> None:
        # 6 hours starting Monday 08:00 -> crosses lunch -> Monday 15:00
        # 4hrs (8-12) + 2hrs (13-15) = 6hrs
        start = datetime(2025, 7, 7, 8, 0)
        finish = engine.calculate_finish(CAL_5DAY, start, 6.0)
        assert finish == datetime(2025, 7, 7, 15, 0)

    def test_full_day(self, engine: CalendarEngine) -> None:
        # 8 hours starting Monday 08:00 -> Monday 17:00
        start = datetime(2025, 7, 7, 8, 0)
        finish = engine.calculate_finish(CAL_5DAY, start, 8.0)
        assert finish == datetime(2025, 7, 7, 17, 0)

    def test_spans_weekend(self, engine: CalendarEngine) -> None:
        # 40 hours starting Friday 14:00 -> should finish Friday next week 14:00
        # Fri: 14:00-17:00 = 3hrs (but wait, lunch break: 14:00-17:00 afternoon = 3hrs)
        # Actually with 5-day, 8hr calendar:
        # Fri afternoon 14:00-17:00 = 3hrs
        # Need 37 more hours
        # Mon-Thu = 4*8 = 32hrs, then 5 more on Fri
        # Fri: 08:00-12:00 = 4hrs, 13:00-14:00 = 1hr -> Fri 14:00
        start = datetime(2025, 7, 11, 14, 0)  # Friday 14:00
        finish = engine.calculate_finish(CAL_5DAY, start, 40.0)
        expected = datetime(2025, 7, 18, 14, 0)  # Next Friday 14:00
        assert finish == expected

    def test_starts_on_weekend(self, engine: CalendarEngine) -> None:
        # Starting Saturday, 8 hours -> finishes Monday 17:00
        start = datetime(2025, 7, 12, 10, 0)  # Saturday
        finish = engine.calculate_finish(CAL_5DAY, start, 8.0)
        assert finish == datetime(2025, 7, 14, 17, 0)  # Monday 17:00

    def test_zero_duration_milestone(self, engine: CalendarEngine) -> None:
        start = datetime(2025, 7, 7, 10, 0)
        finish = engine.calculate_finish(CAL_5DAY, start, 0.0)
        assert finish == start

    def test_starts_mid_period(self, engine: CalendarEngine) -> None:
        # Start Monday 10:00, 3 hours -> Monday 14:00 (2hrs morning + 1hr afternoon)
        start = datetime(2025, 7, 7, 10, 0)
        finish = engine.calculate_finish(CAL_5DAY, start, 3.0)
        assert finish == datetime(2025, 7, 7, 14, 0)

    def test_holiday_skipped(self, engine: CalendarEngine) -> None:
        # 2024-12-25 (Wed) and 2024-12-26 (Thu) are holidays
        # Start Tue Dec 24 at 16:00 with 9 hours remaining
        # Tue: 16:00-17:00 = 1hr. Need 8 more.
        # Wed = holiday, Thu = holiday
        # Fri Dec 27: 08:00-12:00 = 4hrs, 13:00-17:00 = 4hrs -> Fri 17:00
        start = datetime(2024, 12, 24, 16, 0)
        finish = engine.calculate_finish(CAL_5DAY, start, 9.0)
        assert finish == datetime(2024, 12, 27, 17, 0)


class TestWorkHoursBetween:
    """Test the calculate_work_hours_between method."""

    def test_full_day(self, engine: CalendarEngine) -> None:
        start = datetime(2025, 7, 7, 8, 0)  # Monday 08:00
        end = datetime(2025, 7, 7, 17, 0)    # Monday 17:00
        assert engine.calculate_work_hours_between(CAL_5DAY, start, end) == 8.0

    def test_morning_only(self, engine: CalendarEngine) -> None:
        start = datetime(2025, 7, 7, 8, 0)
        end = datetime(2025, 7, 7, 12, 0)
        assert engine.calculate_work_hours_between(CAL_5DAY, start, end) == 4.0

    def test_spans_weekend(self, engine: CalendarEngine) -> None:
        # Friday 08:00 to Monday 17:00 = 8 + 0 + 0 + 8 = 16 hrs
        start = datetime(2025, 7, 11, 8, 0)   # Friday
        end = datetime(2025, 7, 14, 17, 0)     # Monday
        assert engine.calculate_work_hours_between(CAL_5DAY, start, end) == 16.0

    def test_same_time_returns_zero(self, engine: CalendarEngine) -> None:
        dt = datetime(2025, 7, 7, 10, 0)
        assert engine.calculate_work_hours_between(CAL_5DAY, dt, dt) == 0.0

    def test_end_before_start_returns_zero(self, engine: CalendarEngine) -> None:
        start = datetime(2025, 7, 7, 12, 0)
        end = datetime(2025, 7, 7, 8, 0)
        assert engine.calculate_work_hours_between(CAL_5DAY, start, end) == 0.0

    def test_partial_day(self, engine: CalendarEngine) -> None:
        # Monday 10:00 to 15:00 = 2hrs morning (10-12) + 2hrs afternoon (13-15) = 4
        start = datetime(2025, 7, 7, 10, 0)
        end = datetime(2025, 7, 7, 15, 0)
        assert engine.calculate_work_hours_between(CAL_5DAY, start, end) == 4.0

    def test_full_week(self, engine: CalendarEngine) -> None:
        # Monday 08:00 to Friday 17:00 = 5 * 8 = 40 hours
        start = datetime(2025, 7, 7, 8, 0)
        end = datetime(2025, 7, 11, 17, 0)
        assert engine.calculate_work_hours_between(CAL_5DAY, start, end) == 40.0


class TestSummary:
    """Test the summary output."""

    def test_summary_returns_string(self, engine: CalendarEngine) -> None:
        result = engine.summary()
        assert "Calendars loaded: 2" in result
        assert "Standard 5 Day" in result
        assert "7 Day Calendar" in result


class TestWithRealData:
    """Test with the real XER file if available."""

    @pytest.fixture
    def real_engine(self) -> CalendarEngine:
        xer_path = Path("data/sample-5272.xer")
        if not xer_path.exists():
            pytest.skip("Real XER file not available")
        parser = XERParser(xer_path)
        return CalendarEngine(parser)

    def test_real_calendars_loaded(self, real_engine: CalendarEngine) -> None:
        result = real_engine.summary()
        assert "Calendars loaded:" in result

    def test_real_standard_5day(self, real_engine: CalendarEngine) -> None:
        # Calendar 597 is "Standard 5 Day Workweek" with lunch break
        cal = real_engine.get_calendar(597)
        assert cal.name == "Standard 5 Day Workweek"
        # Monday should be 8 hours (4+4)
        assert real_engine.get_work_hours_per_day(597, 0) == 8.0
        # Sunday should be 0
        assert real_engine.get_work_hours_per_day(597, 6) == 0.0

    def test_real_7day_calendar(self, real_engine: CalendarEngine) -> None:
        # Calendar 1447 is "3- Glodal 7 day\8 hrs No Hoilday."
        for day in range(7):
            assert real_engine.get_work_hours_per_day(1447, day) == 8.0

    def test_real_calendar_with_exceptions(self, real_engine: CalendarEngine) -> None:
        # Calendar 642 (PHASE 2) should have exceptions
        cal = real_engine.get_calendar(642)
        assert len(cal.exceptions) > 0
