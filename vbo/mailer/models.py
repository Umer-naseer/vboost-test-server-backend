import uuid
# import premailer
from premailer import transform
import logging
import re

from django.conf import settings
from django.db import models
from clients.models import Company, Package
from celery.contrib.methods import task
from django.core.mail import EmailMultiAlternatives
from .utils import validate_email_list


logger = logging.getLogger(__name__)


class Email(models.Model):
    TYPES = [
        ('package-notification', 'New package notification'),
        ('offer-redeem', 'Submit offer email'),
        ('offer-notify', 'Notify company about offer')
    ]

    STATES = [
        ('pending', 'Pending'),
        ('sending', 'Sending'),
        ('sent', 'Sent')
    ]

    TRACKING_COMMENT = r'<!-- *tracking *-->'

    package = models.ForeignKey(Package, null=True, blank=True)
    type = models.CharField(max_length=32, choices=TYPES)
    status = models.CharField(max_length=32, choices=STATES, default='pending')

    subject = models.CharField(max_length=1024)

    to_emails = models.CharField('To', max_length=2048)
    from_email = models.CharField(
        'From', max_length=512, default=settings.DEFAULT_FROM_EMAIL
    )

    content = models.TextField()

    created_time = models.DateTimeField(auto_now_add=True)
    key = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    @property
    def pixel(self):
        return '<img src="https://vboostlive.com/' \
               'email/tracking/{}/" alt="" />'.format(self.key)

    @task(name='mailer.send')
    def send(self):
        """Send out the email."""

        # Already in sending state. Interrupting.
        if self.status == 'sending':
            raise Exception('Cannot send email #%s because it is '
                            'already in sending state.' % self.id)

        # Content must not be empty
        if not self.content:
            raise Exception('Content must not be empty.')

        Email.objects.filter(id=self.id).update(status='sending')

        message = EmailMultiAlternatives(
            subject=self.subject,
            from_email=self.from_email,
            to=validate_email_list(self.to_emails, required=True),
            # headers=headers,
            # cc=cc,
            # bcc=bcc,
            body='Sorry, this email cannot be displayed in your email '
                 'client as it does not support HTML emails.',
            # attachments=attachments
        )

        message.attach_alternative(transform(
            re.sub(self.TRACKING_COMMENT, self.pixel, self.content,
                   flags=re.IGNORECASE)
        ), 'text/html')

        message.send()

        Email.objects.filter(id=self.id).update(status='sent')

        self.events.create(type='send')

    def __str__(self):
        return self.subject

    class Meta:
        ordering = ['-id']


class Event(models.Model):
    """Email history."""
    TYPES = [
        ('send', 'Send'),
        ('open', 'Open'),
    ]

    email = models.ForeignKey(Email, related_name='events')
    type = models.CharField(max_length=16, choices=TYPES)
    time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return {
            'send': 'The email is sent out.',
            'open': 'The email is viewed.'
        }.get(self.type)

    class Meta:
        ordering = ['-time']


class UnsubscribedEmail(models.Model):
    company = models.ForeignKey(Company)
    email = models.EmailField(max_length=128)
    time = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return '%s for %s' % (
            self.email,
            self.company
        )

    class Meta:
        unique_together = ('company', 'email')
