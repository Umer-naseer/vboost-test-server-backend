from django.core.management.base import BaseCommand
from django.db import IntegrityError
from clients import models
import logging
import requests
from time import sleep
from datetime import datetime, timedelta, date
from generic.utils import handle_exceptions
from imports.models import AddThis
from django.conf import settings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import data from AddThis'

    def handle(self, *args, **options):
        """Import share statistics from Google Analytics."""

        handle_exceptions(__name__)

        period = 'month'

        # Report date is yesterday
        day = date.today() - timedelta(days=1)

        campaigns = list(models.Campaign.objects.filter(
            is_active=True,
            company__status='active',
            tracking_link__isnull=False,
        ).exclude(
            tracking_password='',
            tracking_username=''
        ))

        # Campaigns which failed authentication
        failed_campaigns = {}

        # We need an iterator because we are going to modify the list in place.
        for campaign in campaigns:
            pubid = campaign.tracking_link

            if pubid.startswith('js#pubid='):
                pubid = pubid[9:]

            response = requests.get(
                'https://api.addthis.com/analytics/1.0/'
                'pub/shares/service.json',
                params={
                    'period': period,
                    'pubid': pubid,
                },
                auth=(
                    campaign.tracking_username,
                    campaign.tracking_password)
                )

            headers = response.headers
            shares = response.json()

            if isinstance(shares, dict) and shares.get('error', None):
                failed_campaigns[campaign] = {
                    'error': shares['error'],
                    'headers': headers
                }
                continue

            services = []
            for share in shares:
                services.append(share['service'])

            if services:
                for service in services:
                    items = None
                    for _ in range(3):
                        response = requests.get(
                            'https://api.addthis.com/analytics/1.0/'
                            'pub/shares/day.json',
                            params={
                                'period': period,
                                'pubid': pubid,
                                'service': service,
                            },
                            auth=(
                                campaign.tracking_username,
                                campaign.tracking_password
                            )
                        )

                        if response.status_code < 500:
                            items = response.json()
                            break

                        else:
                            sleep(0.5)  # And try again
                            print "Retrying because of code %s" \
                                  % response.status_code

                    if items is None:
                        logger.warning(
                            'Cannot get %s information for campaign %s. '
                            'Response: %s', (
                                service,
                                campaign,
                                response.text
                            )
                        )
                        continue

                    if isinstance(items, dict) and items.get('error', None):
                        raise Exception(items['error'])

                    for item in items:
                        try:
                            event, is_created = AddThis.objects.get_or_create(
                                date=datetime.strptime(item['date'], '%y%m%d'),
                                campaign=campaign,
                                service=service,
                            )
                            event.count = item['shares']
                            event.save()

                            # print event.campaign, event.date,
                            # event.service, event.count
                        except IntegrityError, exc:
                            print exc

        # We have problems.
        if failed_campaigns:
            if settings.DEBUG:
                print failed_campaigns
            else:
                raise Exception(failed_campaigns)
