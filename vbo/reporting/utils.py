"""Date manipulation utilities for reporting."""
import calendar

from datetime import date
from dateutil.relativedelta import relativedelta

from clients.models import Contact


def _last_quarter(today):
    """Last quarter range."""

    # What is the last month of last full calendar quarter?
    # First, its number is divisible by 3.
    last_month = int(today.month / 3) * 3
    year = today.year

    # If today belongs to the last month, we must select the previous quarter.
    if last_month == today.month:
        last_month -= 3

    # But if we come to zero, the last month is December of the previous year.
    if last_month == 0:
        last_month = 12
        year = year - 1

    last_day = calendar.monthrange(year, last_month)[1]

    # So we have the end date. Let's yield it with the start date,
    # which is easy to calculate.
    end = date(year, last_month, last_day)
    return (
        date(year, last_month - 2, 1),
        end
    )


def period(today, period):
    """Return time range for the report instance."""

    # Period
    yesterday = today + relativedelta(days=-1)
    last_sunday = today + relativedelta(days=-(today.weekday() + 1))
    last_monday = today + relativedelta(days=-today.weekday())

    last_month_end = today + relativedelta(days=-today.day)
    last_month_start = date(last_month_end.year, last_month_end.month, 1)

    # From - to
    return {
        'yesterday': (yesterday,  yesterday),
        'week':      (today + relativedelta(weeks=-1),  yesterday),
        'biweek':    (today + relativedelta(weeks=-2),  yesterday),
        'month':     (today + relativedelta(months=-1), yesterday),
        'prev_month': (
            today + relativedelta(months=-2),
            today + relativedelta(months=-1),
        ),
        'quarter': (today + relativedelta(months=-3), yesterday),
        'prev_quarter': (
            today + relativedelta(months=-6),
            today + relativedelta(months=-3)
        ),
        'year':      (today + relativedelta(years=-1),  yesterday),
        'prev_year': (
            today + relativedelta(years=-2),
            today + relativedelta(years=-1)
        ),

        'cal_this_week': (
            last_monday,
            yesterday if yesterday >= last_monday else today
        ),
        'cal_week': (
            last_sunday + relativedelta(days=-6),
            last_sunday
        ),
        'cal_prev_week': (
            last_sunday + relativedelta(days=-13),
            last_sunday + relativedelta(days=-7)
        ),
        'cal_biweek': (
            last_sunday + relativedelta(days=-13),
            last_sunday
        ),
        'cal_this_month': (
            date(today.year, today.month, 1),
            yesterday if yesterday.month == today.month else today
        ),
        'cal_month': (
            last_month_start,
            last_month_end
        ),
        'cal_this_quarter': (
            _last_quarter(today)[1] + relativedelta(days=1),
            yesterday
        ),
        'cal_quarter': _last_quarter(today),
        'cal_quarter_last_year':
            tuple(d + relativedelta(years=-1) for d in _last_quarter(today)),
        'cal_this_quarter_last_year': (
            _last_quarter(today)[1] + relativedelta(days=1, years=-1),
            yesterday + relativedelta(years=-1)
        ),
        'cal_year': (
            date(today.year - 1, 1, 1),
            date(today.year - 1, 12, 31)
        ),
        'cal_this_year': (
            date(today.year, 1, 1),
            yesterday
        )
    }[period]


def contacts_for_company(company):
    if company:
        return company.contact_set.filter(
            is_active=True,
            type='manager',
        ).exclude(
            email=''
        )
    else:
        return Contact.objects.none()
