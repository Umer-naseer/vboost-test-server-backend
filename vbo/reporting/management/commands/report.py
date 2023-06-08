import logging
from datetime import date

from django.core.management.base import BaseCommand

from generic.utils import handle_exceptions
from reporting.models import Schedule

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send out all reports for current date'

    def handle(self, *args, **options):
        """Import share statistics from Google Analytics."""

        handle_exceptions(__name__)

        today = date.today()

        for schedule in Schedule.objects.filter(is_active=True):
            schedule.attempt(today)
