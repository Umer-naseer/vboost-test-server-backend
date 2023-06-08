import os
import json
import base64
import random

from rest_framework.authtoken.models import Token

from django.test import TestCase, Client
from django.db.models.signals import post_save

from packages.models import Package
from clients.tests.factories import (
    UserFactory,
    CampaignFactory,
    ContactFactory,
    PackageFactory,
)


IMAGES_ROOT = os.path.join(
    os.path.dirname(__file__),
    'test_static',
)


class ReceivingDataAndCreatingPackage(TestCase):
    def setUp(self):
        post_save.disconnect(sender=Package, dispatch_uid='pending')

        self.url = '/api/v1/packages/?format=json'
        self.user = UserFactory()
        self.company = self.user.profile.company
        self.token = Token.objects.get(user=self.user).key
        self.campaign = CampaignFactory(company=self.company)
        self.contact = ContactFactory(company=self.company)
        self.client = Client(HTTP_AUTHORIZATION='Token {}'.format(self.token))

    def _get_images(self):
        images = []
        for i in range(1, 4):
            image_path = os.path.join(IMAGES_ROOT, '{}.jpg'.format(i))
            with open(image_path, 'rb') as f:
                images.append(base64.b64encode(f.read()))

        return json.dumps([{
            'image': image,
            'name': name,
        } for (name, image) in zip(
            ['abadu', 'zuku', 'kabu'],
            images,
        )])

    def test_receiving_data_and_creating_a_package(self):

        data = {
            'campaign': self.campaign.pk,
            'contact': self.contact.pk,
            'recipient_name': 'John Smith',
            'recipient_permission': '1',
            'recipient_email': 'test-{}@criterion-dev.net'.format(
                random.randint(1, 1000),
            ),
            'recipient_phone': '123-45-67',
            'images': self._get_images(),
        }

        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 201)
        content = json.loads(response.content)
        package = Package.objects.filter(id=content['id']).first()
        self.assertIsNotNone(package)
        self.assertEqual(package.status, 'pending')
        self.assertEqual(package.company_id, self.company.pk)
        self.assertEqual(package.campaign_id, self.campaign.pk)
        self.assertEqual(package.contact_id, self.contact.pk)
        self.assertEqual(package.recipient_name, data['recipient_name'])
        self.assertEqual(package.recipient_email, data['recipient_email'])
        self.assertEqual(package.recipient_phone, data['recipient_phone'])
        self.assertEqual(len(content['images']), 3)
        for i in content['images']:
            image = package.images.filter(name=i['name']).first()
            self.assertIsNotNone(image)
            self.assertEqual(image.name, i['name'])
            self.assertTrue(i['image'].endswith(str(image.image)))


class PackagesTasksTestCase(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.company = self.user.profile.company
        self.campaign = CampaignFactory(company=self.company)
        self.contact = ContactFactory(company=self.company)
        self.package = PackageFactory(
            company=self.company,
            campaign=self.campaign,
            contact=self.contact,
        )

    def test_render_wrong_template_prefix(self):
        with self.assertRaisesRegexp(ValueError, 'Prefix wrong is not allowed'):
            self.package.campaign.type.render('wrong', self.package.context())

    def test_render_sms_template(self):
        text = self.package.campaign.type.render('sms', self.package.context())
        link = self.package.get_landing_page_url()
        self.assertEqual(text, 'Here are your photos! {}'.format(link))

    def test_render_email_template(self):
        content = self.package.campaign.type.render('email', self.package.context())
        link = self.package.get_landing_page_url()
        self.assertIn(link, content)
