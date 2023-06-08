from . import models

from celery import task

from django.dispatch import receiver
from django.db.models import signals

from mailer.models import Email


@receiver(signals.post_save, sender=models.Submission,
          dispatch_uid='on_new_submission')
def on_new_submission(sender, instance, created=False, raw=False, **kwargs):
    """On a new offer submission, an email is sent."""

    # No raw data from fixtures. The submission must be newly created.
    if not raw and created:
        send_to_customer.delay(instance)

        if instance.offer.notification_emails:
            send_to_company.delay(instance)


# noinspection PyCallingNonCallable
@task(name='offers.send_to_customer')
def send_to_customer(submission):
    # Build the email

    assert isinstance(submission, models.Submission)

    email = Email.objects.create(
        package=submission.package,
        type='offer-redeem',
        to_emails=submission.email or submission.package.recipient_email,
        from_email=submission.package.company.default_from(),
        subject='Thank You from {}!'.format(submission.package.company.name),
        content=submission.offer.email_template.render(submission.context()),
    )

    email.send()


# noinspection PyCallingNonCallable
@task(name='offers.send_to_company')
def send_to_company(submission):

    assert isinstance(submission, models.Submission)

    email = Email.objects.create(
        package=submission.package,
        type='offer-notify',
        to_emails=submission.offer.notification_emails,
        from_email='Vboost Offers <offers@vbresp.com>',
        subject='Request for offer {} submitted by {}'.format(
            submission.offer.title,
            submission.name,
        ),
        content=submission.offer.email_notification_template.render(
            submission.context()
        ),
    )

    email.send()
