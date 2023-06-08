from django.core.management.base import BaseCommand
import logging
import requests
from django.conf import settings
from datetime import timedelta, date
from generic.utils import handle_exceptions
from imports.models import AddThis
from clients.models import Campaign

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import data from AddThis'

    def handle(self, *args, **options):
        """Import share statistics from Google Analytics."""

        if not settings.DEBUG:
            handle_exceptions(__name__)

        # Report date is yesterday
        day = date.today() - timedelta(days=1)

        campaigns = list(Campaign.objects.filter(
            is_active=True,
            company__status='active',
            tracking_link__isnull=False
        ).exclude(
            tracking_password='',
            tracking_username=''
        ))

        # Sequence of campaigns to process
        sequence = iter(campaigns)

        # Campaigns which failed authentication
        failed_campaigns = {}

        # We need an iterator because we are going to modify the list in place.
        for campaign in sequence:
            pubid = campaign.tracking_link

            if pubid.startswith('js#pubid='):
                pubid = pubid[9:]

            response = requests.get('https://api.addthis.com/analytics/1.0/'
                                    'pub/shares/service.json', params={
                'period': 'last24',
                'pubid': pubid,
            }, auth=(campaign.tracking_username, campaign.tracking_password))

            headers = response.headers
            shares = response.json()

            if isinstance(shares, dict) and shares.get('error', None):
                failed_campaigns[campaign] = {
                    'error': shares['error'],
                    'headers': headers
                }
                continue

            for share in shares:
                AddThis.objects.create(
                    date=day,
                    campaign=campaign,
                    service=share['service'],
                    count=share['shares']
                )

        # We have problems.
        if failed_campaigns:
            if settings.DEBUG:
                from pprint import pprint
                pprint(failed_campaigns)
            else:
                raise Exception(failed_campaigns)
