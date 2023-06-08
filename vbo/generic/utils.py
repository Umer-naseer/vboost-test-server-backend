from datetime import timedelta, datetime, date as date_type
from functools import wraps
from django.db import connection


def user_ip(request):
    """Get remote IP address."""
    # http://stackoverflow.com/questions/4581789/how-do-i-get-user-ip-address-in-django
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')

    return ip


def handle_exceptions(module_name):
    """Handle all unhandled exceptions and log them."""
    import logging
    import sys

    logger = logging.getLogger(module_name)

    def excepthook(type, value, traceback):
        logger.error(value, exc_info=(type, value, traceback))

    sys.excepthook = excepthook


def daterange(start_date, end_date):
    for n in range((end_date - start_date).days + 1):
        day = start_date + timedelta(n)
        yield day


def last_minute(date):
    """Last minute of the day."""

    assert isinstance(date, date_type)

    return datetime(date.year, date.month, date.day, 23, 59, 59)


def ensure_db(f):
    """
    Check if Django database connection is usable before starting the function.
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        # Check db
        # See https://code.djangoproject.com/ticket/21597#comment:9
        try:
            connection.connection.ping()
        except:
            # Closing the connection. It should be reopened on request
            connection.close()

        # Do work
        return f(*args, **kwargs)

    return wrapper
