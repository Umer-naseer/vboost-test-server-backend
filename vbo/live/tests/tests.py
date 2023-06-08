from django.test import TestCase

from clients.models import Campaign, Package, Company
from clients.tests.factories import (
    UserFactory,
    CampaignFactory,
    ContactFactory,
    PackageFactory,
)
from campaigns.models import CampaignType
from live.models import Link
from offers.models import Offer
from templates.models import Template


class CountingOfVisitingOfSitesTestCase(TestCase):
    """Counting of visiting review, social and dealer's sites"""
    def setUp(self):
        self.company = Company.objects.create()
        self.template = Template.objects.create()
        self.campaigntype = CampaignType.objects.create()
        self.campaign = Campaign.objects.create(
            type=self.campaigntype,
        )
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

    def test_link_url(self):
        link = Link.objects.create(company=self.company, type='review')
        response = self.client.get('/a/go/abc/{}/'.format(link.id))
        self.assertEqual(response.status_code, 200)

    def test_review_counter(self):
        link = Link.objects.create(company=self.company, type='review')

        self.client.get('/a/go/abc/{}/'.format(link.id))

        self.assertEqual(Package.objects.get().review_site_views, 1)

    def test_website_counter(self):
        link = Link.objects.create(company=self.company, type='website')

        self.client.get('/a/go/abc/{}/'.format(link.id))

        self.assertEqual(Package.objects.get().website_views, 1)

    def test_social_site_counter(self):
        link = Link.objects.create(company=self.company, type='social')

        self.client.get('/a/go/abc/{}/'.format(link.id))

        self.assertEqual(Package.objects.get().social_site_views, 1)


"""
    def test_true_offer_url_in_page(self):
        # for offer_recipient
        response = self.client.get('/a/lexus_stevens_creek/lexus-san-francisco-san-jose/lexus-stevens-creek/lexus-bay-area/abc/recipient/#.WDGDz7WfFZ6')
        self.assertEqual(Package.objects.get().landing_views, 1)
        self.assertInHTML(needle='<a href="/a/go/abc/offer_recipient/"></a>',
                          haystack=response.rendered_content)
        response = self.client.get('/a/go/abc/offer_recipient/')
        self.assertEqual(Package.objects.get().offer_recipient_views, 1)

        # for offer_others
        response = self.client.get('/a/lexus_stevens_creek/lexus-san-francisco-san-jose/lexus-stevens-creek/lexus-bay-area/abc/photo/#.WDGDz7WfFZ6')
        # print response.rendered_content
        self.assertEqual(Package.objects.get().landing_views, 2)
        self.assertInHTML(needle='<a href="/a/go/abc/offer_others/"></a>',
                          haystack=response.rendered_content)
        response = self.client.get("/a/go/abc/offer_others/")
        self.assertEqual(Package.objects.get().offer_others_views, 1)
"""


class LandingViewTestCase(TestCase):
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
        self.url = self.package.get_landing_page_url()
        self.video_tag = '<meta property="og:video" content="{}" />'.format(
            self.package.video_url(),
        )

    def test_landing_view(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Play Slideshow')
        self.assertContains(response, self.video_tag)

    def test_wrong_modifier(self):
        url = '{}wrong/'.format(self.url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_photo_modifier(self):
        url = '{}photo/'.format(self.url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Play Slideshow')
        self.assertNotContains(response, self.video_tag)

    def test_recipient_modifier(self):
        url = '{}recipient/'.format(self.url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Play Slideshow')
        self.assertContains(response, self.video_tag)

    def test_shared_modifier(self):
        url = '{}shared/'.format(self.url)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Play Slideshow')
        self.assertContains(response, self.video_tag)
