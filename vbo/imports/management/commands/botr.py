from django.core.management.base import BaseCommand
from clients.models import Campaign, Package
from generic.utils import handle_exceptions
import logging
import time
from datetime import date, timedelta
from imports.models import BoTR
from django.conf import settings

logger = logging.getLogger(__name__)

VERBOSE = False


def jw_date(value):
    return int(time.mktime(value.timetuple()))


def approximate_views(views, time_viewed):
    # AVG_TIME_VIEWED = 26.0
    # approx_views = int(round(time_viewed / AVG_TIME_VIEWED))
    # return max(approx_views, views)

    return views


class Command(BaseCommand):
    help = 'Import data from BoTR'

    def collect_views_per_package(self, campaign, date_from, date_to):
        """
        Grab view count for each of existing packages.
        May be optimized (stripped down to a finite period), but not now.
        It just works.
        """

        # Video count per query
        limit = 1000
        client = campaign.botr()

        response = client.call('/videos/views/list', {
            'start_date': date_from,
            'end_date': date_to,
            'result_limit': limit,  # We aim to get all videos at once
            'statuses_filter': 'active'  # Only active videos
        })

        if response['status'] != 'ok':
            logger.warning(
                'Cannot import %s data from BoTR: %s', campaign.name,
                response['message'], extra={'response': response}
            )
            return

        # Are there any videos to process?
        if not response['total']:
            return

        # Are there any videos we haven't fetched?
        if response['total'] > limit:
            logger.critical('Please implement cycling to process '
                            'all of the videos.',
                            extra={
                                'data': {
                                    'campaign': campaign,
                                    'processed_videos': limit,
                                    'total_videos': response['total']
                                }
                            })

        # Okay, we can work now
        for video in response['videos']:
            if VERBOSE:
                print '[{}] {}: {}'.format(
                    campaign.id,
                    campaign,
                    ' '.join(map(str, [
                        video['key'],
                        video['pageviews'],
                        video['views'],
                        video['viewed']
                    ]))
                )

            Package.objects.filter(
                video_key=video['key'],

                # Avoid decreasing the numbers
                viewed_time__lte=video['viewed'],
                video_views__lte=video['views'],
                page_views__lte=video['pageviews'],
            ).update(
                viewed_time=video['viewed'],
                video_views=video['views'],
                page_views=video['pageviews']
            )

        # Cleanup
        del response

    def collect_views_per_date(self, campaign, date_from, date_to):
        client = campaign.botr()

        response = client.call('/videos/views/list', {
            'list_by': 'day',
            'start_date': date_from,
            'end_date': date_to,
            'include_empty_days': True,
        })

        if response['status'] != 'ok':
            logger.error(
                'Cannot import %s data from BoTR: %s', campaign.name,
                response['message'], extra={'response': response}
            )
            return

        days = response['days']

        for item in days:
            entry, is_created = BoTR.objects.get_or_create(
                campaign=campaign,
                date=date(
                    item['date']['year'],
                    item['date']['month'],
                    item['date']['day']),
            )

            entry.__dict__.update({
                'views': item['views'],
                'viewed': item['viewed'],
                'page_views': item['pageviews'],
            })

            entry.save()

    def handle(self, *args, **options):
        """Import view statistics from BoTR."""

        # Every campaign typically has its own BoTR credentials.
        # Moreover, these credentials MUST be unique for each campaign.
        # So, we cycle through campaigns and process each of them individually.

        if not settings.DEBUG:
            handle_exceptions(__name__)

        campaigns = Campaign.objects.filter(
            is_active=True,
            company__status='active'
        ).exclude(
            streaming_username='',
            streaming_password=''
        )

        # We import data from the latest 3 months. Too bad and takes
        # a long time, but works. So why not? We'll fix if it appears
        # to be too slow.
        date_to = date.today()
        date_from = date_to - timedelta(days=5)

        date_from = jw_date(date_from)
        date_to = jw_date(date_to)

        for campaign in campaigns:
            try:
                self.collect_views_per_package(campaign, date_from, date_to)
                self.collect_views_per_date(campaign, date_from, date_to)
            except Exception as exc:
                logger.error(
                    'Error on importing JWPlatform data for %s: %s',
                    campaign.name, str(exc),
                    extra={'campaign': campaign.name}
                )
