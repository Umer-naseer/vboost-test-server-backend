# packages/check.py
from __future__ import unicode_literals
from __future__ import absolute_import

from django.core.management.base import BaseCommand
from django.utils import timezone

from clients.models import Package, Event
from packages import tasks


THRESHOLD = timezone.timedelta(days=5)


def produce(queryset):
    """Produce selected packages."""

    queryset.update(session=None)

    for p in queryset:
        tasks.production.delay(p.id)


class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    def handle(self, *args, **options):
        time_threshold = timezone.now() - THRESHOLD
        error_packages = Package.objects.filter(
            status='erroneus',
            events__time__gt=time_threshold,
        ).distinct()
        id_package_list = []
        for package in error_packages:
            last_error_event = Event.objects.filter(
                package=package,
                type='error'
            ).last()
            if last_error_event:
                id_package_list += [package.id]
        error_packages = error_packages.filter(id__in=id_package_list)
        if error_packages:
            produce(error_packages)
