import uuid
import random
import string

from django.db import models
from clients.models import Package
from django.forms.models import model_to_dict
from django.core.urlresolvers import reverse


class Offer(models.Model):
    AUDIENCE_CHOICES = (
        ('recipient', 'Recipient'),
        ('others', 'Friends, family and contacts'),
    )

    LANDING_TEMPLATE_CHOICES = (
        ('image', 'Clickable Image'),
        ('postit', 'Post-It Note'),
    )

    campaign = models.ForeignKey('clients.Campaign', related_name='offers')

    landing_template = models.CharField(
        max_length=128, choices=LANDING_TEMPLATE_CHOICES, default='image'
    )

    email_template = models.ForeignKey(
        'templates.Template', related_name='using_offer_email'
    )
    email_notification_template = models.ForeignKey(
        'templates.Template', related_name='using_offer_notification_email'
    )
    redeem_template = models.ForeignKey(
        'templates.Template', related_name='using_offer_redeem'
    )

    target_audience = models.CharField(
        choices=AUDIENCE_CHOICES, max_length=32, db_index=True
    )

    image = models.ImageField(upload_to='offers/images', blank=True, null=True)
    title = models.CharField(max_length=255, blank=True)
    subtitle = models.CharField(max_length=255, blank=True)
    text = models.CharField(max_length=255, blank=True)

    link_text = models.CharField(max_length=255, blank=True)
    link_url = models.URLField(blank=True)

    notification_emails = models.CharField(
        max_length=1024,
        blank=True,
        help_text='To notify about new offer submission'
    )

    def context(self):
        context = model_to_dict(self)

        context.update({
            'template_key': self.template.key,
        })

        return context

    def __str__(self):
        return self.title


class Submission(models.Model):
    package = models.ForeignKey(Package)
    offer = models.ForeignKey(Offer)

    name = models.CharField(max_length=255)
    mobile = models.CharField(max_length=16)
    email = models.EmailField()

    appointment_date = models.DateField(blank=True, null=True)
    zipcode = models.CharField(max_length=16, blank=True)

    code = models.CharField(max_length=16, unique=True, blank=True)
    key = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    last_redeem_time = models.DateTimeField(blank=True, null=True)

    created_time = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_code()

        super(Submission, self).save(*args, **kwargs)

    def generate_code(self):
        """Generate redemption code for this submission."""

        # Length of the random part
        RANDOM_LENGTH = 4

        # Exclude some symbols that may be read ambiguously
        EXCLUDE_SYMBOLS = 'OQ'

        SYMBOLS = (string.ascii_uppercase + string.digits).translate(
            None, EXCLUDE_SYMBOLS
        )

        # For each campaign, this procedure might generate max
        # len(SYMBOLS) ** RANDOM_LENGTH distinct codes.
        # If someone tries to generate more, we'll get an infinite loop.

        while True:
            code = '{}-{}'.format(
                self.package.campaign.id,
                ''.join(random.sample(SYMBOLS, RANDOM_LENGTH))
            )

            # Only if unique
            if not Submission.objects.filter(code=code).count():
                return code

    @property
    def redeem_url(self):
        return 'https://vboostlive.com' + \
               reverse('offers-redeem', args=[self.key])

    def context(self):
        context = model_to_dict(self)

        context.update({
            'package': self.package.context(),
            'offer': self.offer.context(),
            'key': str(self.key),
            'redeem_url': self.redeem_url,
        })

        return context

    def __str__(self):
        return 'Submission by {} <{}>'.format(self.name, self.email)
