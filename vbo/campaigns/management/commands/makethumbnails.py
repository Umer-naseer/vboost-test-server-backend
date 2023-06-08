from datetime import timedelta

from sorl.thumbnail import get_thumbnail

from django.core.management.base import BaseCommand
from django.utils import timezone

from clients.models import Package


PACKAGES_RECENT = 365  # Days


class Command(BaseCommand):
    help = 'Make masked thumbnails for performance reasons.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company',
            type=int,
            # action='store',
            dest='company_id',
            default=None,
            help='Make thumbnails only for company ID',
        )

    def handle(self, *args, **options):
        packages = Package.objects.filter(status='sent').order_by('-id')
        cid = options['company_id']
        if cid:
            packages = packages.filter(company_id=cid)

        min_date = timezone.now() - timedelta(days=PACKAGES_RECENT)
        try:
            min_id = Package.objects.filter(
                created_time__gte=min_date,
            ).values_list('id', flat=True)[0]
        except IndexError:
            pass
        else:
            packages = packages.filter(id__gte=min_id)

        for p in packages.iterator():
            print "Package ID: {}...".format(p.pk)

            if p.cover:
                # Admin thumbnail
                try:
                    get_thumbnail(p.cover.get_masked_thumbnail(), '100')
                except Exception as e:
                    print e
                # Widget thumbnail
                try:
                    get_thumbnail(
                        str(p.cover),
                        '241x140',
                        crop='faces',
                        overlay=p.company.get_stamp_path(),
                        # overlay_mode='mask'
                    )
                except Exception as e:
                    print e

        print "Done."
