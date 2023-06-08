import logging
import requests
import time

from django.core.management.base import BaseCommand
from django.db.models import Q

from clients import models
from live.tasks import get_full_url

NUM_RETRIES = 3

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Recaches all the company pages and the main page'

    def get_page(self, full_url):
        for i in range(NUM_RETRIES):
            try:
                response = requests.get(full_url)
                if response.status_code != 200:
                    continue
                else:
                    break
            except Exception as e:
                response = str(e)
                continue

        return response

    def fetch(self, slug):
        full_url = get_full_url(slug)
        start = time.time()
        response = self.get_page(full_url)
        roundtrip = time.time() - start
        page_name = "Index page" if slug == '' else slug
        if isinstance(response, str):
            logger.warning('"%s" cannot be opened because of '
                           'connection problem.',
                           full_url)
            return False
        elif response.status_code == 200:
            logger.info(
                '"%s" page was successfully opened within %i sec.',
                page_name,
                roundtrip)
            return True
        else:
            logger.warning('"%s" cannot be opened, status code: %s.',
                           full_url,
                           response.status_code)
            return False

    def handle(self, *args, **options):
        company_slug_list = models.Company.objects.exclude(
            Q(slug__isnull=True) | Q(slug='') | Q(slug=' ')
        ).values_list('slug', flat=True)

        results = map(self.fetch, company_slug_list)
        success_count = results.count(True)
        failed_count = results.count(False)

        self.fetch('')
        logger.info("Total, opened pages are %s, and not opened pages "
                    "are %s.", success_count, failed_count)
