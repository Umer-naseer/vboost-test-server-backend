import factory

from django.db.models.signals import post_save
from django.contrib.auth.models import User

from clients.models import create_user_profile
from campaigns.tests.factories import CampaignTypeFactory


class CompanyFactory(factory.DjangoModelFactory):
    name = factory.Sequence(lambda n: 'Acme Company #{}'.format(n))
    slug = factory.LazyAttribute(
        lambda o: o.name.replace(' ', '-').replace('#', '')
    )

    class Meta:
        model = 'clients.Company'


class UserProfileFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(
        'clients.tests.factories.UserFactory', profile=None
    )
    title = factory.Faker('job')
    phone = factory.faker.Faker('phone_number')
    company = factory.SubFactory(CompanyFactory)

    class Meta:
        model = 'clients.UserProfile'


class UserFactory(factory.django.DjangoModelFactory):
    username = factory.Faker('user_name')
    email = factory.Faker('email')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    profile = factory.RelatedFactory(UserProfileFactory, 'user')

    class Meta:
        model = User

    @classmethod
    def _generate(cls, create, attrs):
        """Override the default _generate() to disable the post-save signal."""

        # Note: If the signal was defined with a dispatch_uid,
        # include that in both calls.
        post_save.disconnect(create_user_profile, User)
        user = super(UserFactory, cls)._generate(create, attrs)
        post_save.connect(create_user_profile, User)
        return user


class CampaignFactory(factory.django.DjangoModelFactory):
    company = factory.SubFactory(CompanyFactory)
    type = factory.SubFactory(CampaignTypeFactory)
    name = factory.Sequence(lambda n: 'Acme Campaign #{}'.format(n))
    key = factory.Sequence(lambda n: 'key_{}'.format(n))

    class Meta:
        model = 'clients.Campaign'


class ContactFactory(factory.django.DjangoModelFactory):
    company = factory.SubFactory(CompanyFactory)
    name = factory.Faker('name')

    class Meta:
        model = 'clients.Contact'


def _generate_landing_page_url(package):
    return '{slug}/{key}/'.format(
        slug=package.company.slug.lower().replace(' ', '-'),
        key=package.landing_page_key,
    )


class PackageFactory(factory.django.DjangoModelFactory):
    company = factory.SubFactory(CompanyFactory)
    contact = factory.SubFactory(ContactFactory)
    campaign = factory.SubFactory(CampaignFactory)
    geo_keywords = factory.Faker('state')
    product_keywords = factory.Faker('word')
    landing_page_key = factory.Sequence(lambda n: 'key{}'.format(n))
    landing_page_url = factory.LazyAttribute(_generate_landing_page_url)

    class Meta:
        model = 'clients.Package'
