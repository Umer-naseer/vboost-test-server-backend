from django.core.management.base import BaseCommand
from clients import models
import analytics
import logging
import time
from datetime import datetime
from generic.utils import handle_exceptions
from apiclient.errors import HttpError


logger = logging.getLogger(__name__)


def execute(endpoint):
    """
    Make a Google Analytics endpoint call. Retry 3 times if got an HttpError.
    """

    num_retries = 3
    for i in range(num_retries):
        try:
            return endpoint.execute()
        except HttpError:
            if i == num_retries - 1:
                raise
            else:
                time.sleep(1)


class Command(BaseCommand):
    help = 'Import data from Google Analytics'

    def handle(self, *args, **options):
        """Import share statistics from Google Analytics."""

        handle_exceptions(__name__)

        today = datetime.today().strftime('%Y-%m-%d')

        # Campaigns
        campaigns = list(models.Campaign.objects.filter(
            is_active=True,
            company__status='active',
            google_analytics__isnull=False
        ).exclude(
            google_analytics=''
        ))

        # Analytics API
        service = analytics.service()

        # Account list
        accounts = execute(service.management().accounts().list())['items']

        orphan_properties = []
        for account in accounts:
            account_id = account['id']

            properties = execute(service.management().webproperties().list(
                accountId=account_id
            ))['items']

            for property in properties:
                property_id = property['id']
                try:
                    campaign = models.Campaign.objects.get(
                        google_analytics=property_id,
                    )

                    if campaign in campaigns:
                        campaigns.remove(campaign)
                except models.Campaign.DoesNotExist:
                    # No such campaign at all. Signalize that.
                    orphan_properties.append((property['name'], property_id))
                    continue

                if not campaign.is_active \
                        or campaign.company.status != 'active':
                    # Inactive campaign, skip it.
                    continue

                # Campaign is found. Now fetching data from Core Analytics API

                profiles = execute(service.management().profiles().list(
                    accountId=account_id,
                    webPropertyId=property_id
                ))['items']

                for profile in profiles:
                    profile_id = profile['id']

                    response = execute(service.data().ga().get(
                        ids='ga:' + profile_id,
                        start_date='2010-01-01',
                        end_date=today,
                        dimensions='ga:pagePath',
                        metrics='ga:socialInteractions,ga:visitors',
                        filters='ga:pagePath=~^/a/;ga:visitors>0',
                        max_results=5000,
                    ))

                    rows = response.get('rows', None)

                    if not rows:
                        print "No results for %s." % campaign
                        continue

                    # Have we imported all results?
                    if response['totalResults'] > len(rows):
                        raise Exception('We have imported %s rows for '
                                        'campaign %s from %s total rows.'
                                        % (
                                            len(rows),
                                            campaign,
                                            response['totalResults']
                                            )
                                        )

                    for url, shares, visitors in rows:
                        # Process each package URL
                        try:
                            key = url.split('/')[4]
                        except:
                            print 'Cannot figure out package key ' \
                                  'for URL %s.' % url
                            continue

                        updated = models.Package.objects.filter(
                            landing_page_key=key,
                        ).update(
                            # shares=int(shares),
                            visitors=int(visitors)
                        )

                        if not updated:
                            # print 'Problem matching landing page
                            # key %s, URL: %s' % (key, url)
                            pass

                        if updated > 1:
                            raise Exception('More than one package found '
                                            'for landing key %s.' % key)

                    time.sleep(2)

        if campaigns or orphan_properties:
            msg = '''Google Analytics wrong matches

These do exist at VBO but do not exist at Google Analytics:
%(campaigns)s

These do exist at Google Analytics but not at VBO:
%(properties)s''' % {
                'campaigns': '\n'.join(
                    ['%s: %s' % (c.name, c.google_analytics)
                     for c in campaigns]),
                'properties': '\n'.join(['%s: %s' % p
                                         for p in orphan_properties]),
            }

            # logger.warning(msg)
