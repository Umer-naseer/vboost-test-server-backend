"""Import per-package shares from AddThis."""

from django.core.management.base import BaseCommand
import logging
import requests
from django.conf import settings
from generic.utils import handle_exceptions
from clients.models import Campaign, Package
import re

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'AddThis shares per package'

    def handle(self, *args, **options):
        """Import share statistics from Google Analytics."""

        if args:
            period = args[0]
        else:
            period = '6months'

        if not settings.DEBUG:
            handle_exceptions(__name__)

        campaigns = Campaign.objects.filter(
            is_active=True,
            company__status='active',
            tracking_link__isnull=False
        ).exclude(
            tracking_password='',
            tracking_username=''
        ).exclude(tracking_link='')

        # We need an iterator because we are going to modify the list in place.
        for campaign in campaigns:
            with requests.Session() as session:
                # First, we need to login
                response = session.post(
                    'https://www.addthis.com/darkseid/account/login',
                    data={
                        'type': 0,
                        'eee': campaign.tracking_username,
                        'password': campaign.tracking_password,
                        'next': '',
                    },
                    headers={
                        'content-type': 'application/x-www-form-urlencoded',
                    }
                )

                # Check that we are logged in
                if not response.url.endswith('dashboard'):
                    logger.error('%s: cannot login to AddThis', campaign)
                    continue

                data = session.get(
                    'https://www.addthis.com/darkseid/dashboard-analytics/'
                    'shares/top-content/{}'.format(campaign.get_tracking_id()),
                    params={
                        'domain': 'all',
                        'range': period,
                        'sort': 'share'
                    }
                ).json()

                if isinstance(data, dict) and data.get('error'):
                    logger.error('%s: error fetching data', campaign, extra={
                        'response': data
                    })
                    continue

                logger.info('%s: fetched data', campaign)

                for row in data:
                    match = re.match(
                        r'vboostlive\.com/(a/)*[^/]+/[^/]+/([^/]+)',
                        row['url']
                    )

                    if match:
                        key = match.group(2)
                        shares = row['counts']['share']

                        Package.objects.filter(
                            landing_page_key=key,
                            shares__lt=shares
                        ).update(
                            shares=shares
                        )
