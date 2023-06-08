import os
import json
import base64
import random

from rest_framework.authtoken.models import Token

from django.test import TestCase, Client
from django.db.models.signals import post_save

from clients.models import PackageImage
from packages.models import Package
from clients.tests.factories import (
    UserFactory,
    CampaignFactory,
    ContactFactory,
)


IMAGES_ROOT = os.path.join(
    os.path.dirname(__file__),
    'test_static',
)


class PartialPackageSendingAPITest(TestCase):
    def setUp(self):
        post_save.disconnect(sender=Package, dispatch_uid='pending')

        self.url_full_package = '/api/v1/packages/?format=json'
        self.url_one_image_sending = '/api/v1/packageimage/?format=json'
        self.url_package_complete = '/api/v1/package/{}/complete/'
        self.user = UserFactory()
        self.company = self.user.profile.company
        self.token = Token.objects.get(user=self.user).key
        self.campaign = CampaignFactory(company=self.company)
        self.contact = ContactFactory(company=self.company)
        self.client = Client(HTTP_AUTHORIZATION='Token {}'.format(self.token))

    def _get_image(self, image_number):
        if image_number > 4:
            raise Exception('Image number more then 4')

        image_path = os.path.join(IMAGES_ROOT, '{}.jpg'.format(image_number))
        f = open(image_path, 'rb')
        image = base64.b64encode(f.read())
        name = ['abadu', 'zuku', 'kabu', 'utal'][image_number]
        return {
            'image': image,
            'name': name
        }

    def _sending_one_image(self, package, image_number):
        image = self._get_image(image_number)
        data = {
            'package': package.id,
            'image': image['image'],
            'name': image['name'],
        }
        response = self.client.post(self.url_one_image_sending, data)
        return response

    def _create_package(self):
        package = Package.objects.create(
            company_id=self.company.id,
            contact_id=self.contact.id,
            campaign_id=self.campaign.id,
            recipient_email='test-42352345@crit.gre',
            recipient_permission=1,
            status='preparation',
            user_agent='python-requests/2.1.0 CPython/'
                       '2.7.12 Linux/4.4.0-97-generic'
        )
        return package

    def test_creating_empty_package(self):

        data = {
            'campaign': self.campaign.pk,
            'contact': self.contact.pk,
            'recipient_name': 'John Smith',
            'recipient_permission': '1',
            'recipient_email': 'test-{}@criterion-dev.net'.format(
                random.randint(1, 1000),
            ),
            'recipient_phone': '123-45-67',
        }

        response = self.client.post(self.url_full_package, data)

        self.assertEqual(response.status_code, 201)
        content = json.loads(response.content)
        package = Package.objects.filter(id=content['id']).first()

        self.assertIsNotNone(package)
        self.assertEqual(package.status, 'preparation')
        self.assertEqual(package.company_id, self.company.pk)
        self.assertEqual(package.campaign_id, self.campaign.pk)
        self.assertEqual(package.contact_id, self.contact.pk)
        self.assertEqual(package.recipient_name, data['recipient_name'])
        self.assertEqual(package.recipient_email, data['recipient_email'])
        self.assertEqual(package.recipient_phone, data['recipient_phone'])
        if content['images']:
            self.assertEqual(len(content['images']), 0)

    def test_sending_one_image_to_package(self):

        package = self._create_package()

        response = self._sending_one_image(package, 1)

        self.assertEqual(response.status_code, 201)
        content = json.loads(response.content)

        package_from_content = Package.objects.get(id=content['package'])
        self.assertIsNotNone(package)
        self.assertEqual(package.id, package_from_content.id)
        self.assertEqual(package.status, 'preparation')
        self.assertIsNotNone(content['image'])
        images = PackageImage.objects.filter(
            package_id=package_from_content.id
        )
        self.assertEqual(images.count(), 1)

        response = self._sending_one_image(package, 2)
        self.assertEqual(response.status_code, 201)
        images = PackageImage.objects.filter(
            package_id=package_from_content.id
        )
        self.assertEqual(images.count(), 2)

    def test_package_complete(self):
        package = self._create_package()
        self._sending_one_image(package, 1)
        self._sending_one_image(package, 2)
        self._sending_one_image(package, 3)

        response = self.client.patch(
            self.url_package_complete.format(package.id)
        )
        package.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        package_from_content = Package.objects.get(id=content['id'])
        result = content['result']
        self.assertIsNotNone(package)
        self.assertEqual(package.id, package_from_content.id)
        self.assertEqual(package.status, 'pending')
        self.assertEqual(result, 'Success')
