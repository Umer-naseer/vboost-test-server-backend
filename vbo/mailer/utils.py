import re
import time

from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.forms import ValidationError
from django.core.validators import validate_email
from smtplib import SMTPServerDisconnected


def send_email(content, subject, to, from_email=None, headers=None,
               cc=None, bcc=None, attachments=None, body=None):
    """Send an HTML email."""

    if not headers:
        headers = {}

    if not isinstance(to, (list, tuple)):
        to = [to]

    if body is None:
        body = 'Sorry that this email cannot be displayed in your ' \
               'email client as it does not support HTML emails.'

    msg = EmailMultiAlternatives(
        subject=subject,
        from_email=from_email or settings.DEFAULT_FROM_EMAIL,
        to=to,
        headers=headers,
        cc=cc,
        bcc=bcc,
        body=body,
        attachments=attachments
    )

    if content is not None:
        msg.attach_alternative(content, 'text/html')

    exc = None
    for _ in range(3):
        try:
            print('Trying...')
            msg.send()
            return

        except SMTPServerDisconnected as exc:
            print(str(exc))
            time.sleep(0.5)

    if exc:
        raise exc


def validate_email_list(value, required=False):
    """Validate the list of emails."""

    SEPARATOR = re.compile(r'[^\w\.\-\+@_]+')

    emails = list(filter(bool, SEPARATOR.split(value)))

    if not emails and required:
        raise ValidationError(u'Enter at least one email address.')

    for email in emails:
        try:
            validate_email(email)
        except ValidationError:
            raise ValidationError('"%s" is not a valid email address.' % email)

    return emails
