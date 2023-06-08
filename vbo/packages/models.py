"""Packages and related models"""

from clients.models import Package


class RestartProcessing(Exception):
    """This means that processing must be restarted from scratch."""


class Wait(Exception):
    """We should wait and try again."""


class InterruptProcessing(Exception):
    """Giving up."""


class Inspect(Package):
    class Meta:
        proxy = True
        verbose_name = 'package'
