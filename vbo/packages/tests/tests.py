from requests import Response
from mock import patch

from django import test
from django.core.management import call_command

from clients.models import Campaign, Package, Company, Event
from campaigns.models import CampaignType
from offers.models import Offer
from templates.models import Template


class ReproduceErrorPackageByCheckFramework(test.TestCase):
    """All error packages should be reproduce by the command: manage.py check"""
    def setUp(self):
        self.company = Company.objects.create()
        self.template = Template.objects.create()
        self.campaign_type = CampaignType.objects.create()
        self.campaign = Campaign.objects.create(type=self.campaign_type)
        self.offer = Offer.objects.create(
            target_audience="recipient",
            campaign=self.campaign,
            email_template=self.template,
            email_notification_template=self.template,
            redeem_template=self.template,
            image='offers/images/Eta2.JPG',
            link_url='notempty',
        )
        self.offer1 = Offer.objects.create(
            target_audience="others",
            campaign=self.campaign,
            email_template=self.template,
            email_notification_template=self.template,
            redeem_template=self.template,
            image='offers/images/Eta2.JPG',
            link_url='notempty',
        )
        self.package = Package.objects.create(
            company=self.company,
            campaign=self.campaign,
            landing_page_key='abc'
        )

    def test_error_packages_reproduce(self):
        self.package.status = 'erroneus'
        self.package.save()
        event = Event.objects.create(
            package=self.package,
            description='Once again that weak service Stupeflix '
                        'is lying breathless',
            type='error'
        )
        event.save()
        with patch('packages.video_backends.stupeflix.push') as \
                stupeflix_push_mock:
            with patch('packages.tasks.storage.apply_async') as storage_mock:
                response = Response()
                response.status_code = 200
                response._content = b'{ "key" : "a"}'
                response = response.json()
                response = [response, ]
                stupeflix_push_mock.return_value = response
                storage_mock.return_value = 0
                call_command('package_reproducing')
        self.package.refresh_from_db()
        self.assertNotEqual(self.package.status, 'erroneus')
