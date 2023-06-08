"""Package processing system."""
import errno
import logging
import os
import plivo
import random
import requests
import string
import uuid
import video_backends.idomoo
import video_backends.stupeflix

from datetime import datetime
from dateutil.relativedelta import relativedelta
from sorl.thumbnail import get_thumbnail

# Async tasks
from celery import Task, task
from celery.exceptions import MaxRetriesExceededError

from django.conf import settings
from django.db.models import signals
from django.dispatch import receiver
from django.utils.timezone import now

from clients import models
from live.views import LandingView
from models import RestartProcessing, InterruptProcessing, Wait
from mailer.models import Email, UnsubscribedEmail
from mailer.utils import send_email as send, validate_email_list
from .thumbnail import make_thumbnails

logger = logging.getLogger(__name__)


@receiver(signals.pre_save, sender=models.Package,
          dispatch_uid='check_contact_integrity')
def check_contact_integrity(sender, instance, raw=False, **kwargs):
    """If a package is assigned to another company or campaign, its contact
    must be consistent. In other words:
    1) (package.company == company) => (package.contact.company == company);
    2) (package.campaign.default_contact exists) =>
    (package.contact == package.campaign.default_contact)
    """

    if raw:
        pass

    elif instance.campaign_id and instance.campaign.default_contact and \
            (not instance.contact_id
             or (instance.campaign.default_contact != instance.contact)):
        instance.contact = instance.campaign.default_contact

    elif instance.contact_id and instance.contact.name \
            and instance.company_id \
            and (instance.contact.company != instance.company):
        instance.contact, is_created = models.Contact.objects.get_or_create(
            company=instance.company,
            name=instance.contact.name,
        )


@receiver(signals.post_save, sender=models.Package, dispatch_uid='pending')
def pending(sender, instance, created=False, raw=False, **kwargs):
    """If package is pending, we can try to approve it automatically."""

    if raw:
        pass

    elif instance.status == 'pending' and instance.campaign_id \
            and not instance.campaign.is_active:
        # The campaign is inactive. We void the package.
        instance.status = 'void'
        instance.save()

    elif instance.status == 'pending' and instance.campaign_id:
        # Yes, it qualifies! At first, we skip the "approve" stage
        # and select the thumbnail image automatically.
        # Just taking the first one.

        if not instance.thumbnail():
            try:
                thumbnail = instance.images.filter(
                    is_skipped=False,
                    campaign__isnull=True
                ).order_by('inline_ordering_position')[:1].get()
            except models.PackageImage.DoesNotExist:
                instance.error('Auto approval failed: this package lacks '
                               'an image suitable for thumbnail.')
                return

            thumbnail.is_thumbnail = True
            thumbnail.save()

        # We have approved this package automatically. Reflect this fact.
        instance.status = 'approved'
        # This will implicitly start thumbnail masking procedure.
        instance.save()


@receiver(signals.post_save, sender=models.Package, dispatch_uid='approved')
def approved(sender, instance, created=False, raw=False, **kwargs):
    """If package bypasses approval, we can mask it automatically."""

    if raw:
        pass

    elif instance.status == 'approved' and instance.campaign_id \
            and not instance.campaign.is_active:
        instance.status = 'void'
        instance.save()

    elif instance.status == 'approved' and instance.campaign_id:
        instance.status = 'ready'
        instance.save()


@receiver(signals.post_save, sender=models.Package, dispatch_uid='ready')
def ready(sender, instance, created=False, raw=False, **kwargs):
    """Time to start package production."""

    if raw:
        pass

    elif instance.is_duplicate():
        logger.info('Package is DUPLICATE. Instance save().', extra={
            'tags': {
                'package': instance.id
            },
        })
        if instance.status != 'duplicate':
            #instance.status = 'duplicate'
            #instance.status = 'starting'
            models.Package.objects.filter(id=instance.id).update(status='starting')
            production.delay(instance.pk)
            #instance.save()

        else:
            pass  # Do nothing. We are not going to change anything.

    elif instance.status == 'ready' and instance.campaign_id:
        instance.status = 'starting'
        models.Package.objects.filter(id=instance.id).update(status='starting')
        production.delay(instance.pk)


@receiver(signals.post_save, sender=models.Package, dispatch_uid='delivery')
def delivery(sender, instance, created=False, raw=False, **kwargs):
    """Start email delivery process."""
    if not raw and not created and instance.status == 'sending' \
            and instance.status != instance._initial_status:
        deliver.apply_async(args=(instance.id, ), countdown=10)


@receiver(signals.post_save, sender=models.Package, dispatch_uid='creation')
def package_created(sender, instance, created=False, raw=False, **kwargs):
    """
    We need to catch the moment when the package was just
    in preparation and now is pending.
    """

    assert isinstance(instance, models.Package)

    if raw:
        return

    if instance.status in ('pending', 'ready') \
            and instance._initial_status == 'preparation' and \
            instance.campaign.notification_email \
            and instance.campaign.notification_email_template_id and \
            not Email.objects.filter(package=instance).exists():
        send_notification_email(instance)


def send_notification_email(package):
    assert isinstance(package, models.Package)

    context = package.context()

    title = '{campaign}: {contact} - {company}'.format(
        campaign=package.campaign,
        contact=package.contact.name,
        company=package.company
    )

    context.update({
        'title': title,
    })

    email = Email.objects.create(
        package=package,
        type='package-notification',
        to_emails=package.campaign.notification_email,
        from_email='Vboost Support <support@vbresp.com>',
        subject=title,
        content=package.campaign.notification_email_template.render(context)
    )

    email.send()

    return email


class PackageTask(Task):
    """Task base class."""

    abstract = True

    # Restart tasks if online services are working too slowly
    max_retries = 30

    # Restart tasks if online services return errors
    max_retries_on_errors = 10

    # But sequential retries should be separated by a timeout
    default_retry_delay = 60

    # We generally do not need task results...
    # ignore_result = True

    # Unless they are errors.
    store_errors_even_if_ignored = True

    # Which also lead to sending emails.
    send_error_emails = True

    # A task is marked completed after it is executed.
    # On daemon crash or system reboot it may lead to repeating the task,
    # which is not too bad.
    acks_late = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """If a package fails processing, its state is set to 'erroneus'
        and a record is saved in the package history."""

        try:
            package_id = args[0]
        except IndexError:
            logger.critical(
                'On_failure does not know which package it belongs to',
                extra={
                    'index_error': {
                        'args': args,
                        'task_id': task_id,
                        'kwargs': kwargs,
                        'einfo': einfo
                    }
                }
            )
            return

        session = kwargs.get('session', None)

        if isinstance(exc, MaxRetriesExceededError):
            exc = Exception(
                'Package processing failed at %s: retries limit exceeded.'
                % self.name
            )

        models.Package.objects.get(id=package_id).error(exception=exc)
        models.Package.objects.filter(id=package_id).update(session=None)

        if not isinstance(exc, InterruptProcessing):
            logger.critical(str(exc), exc_info=einfo, extra={
                'tags': {'package': package_id, 'session': session},
            })

    def on_success(self, retval, task_id, args, kwargs):
        logger.info('Task %s completed.', self.name, extra={
            'tags': {
                'package': args[0],
                'session': kwargs.get('session', None)
            },
        })


def validate_session(package, session, task=None):
    """
    Our session can work with package if package has no session
    OR belongs to our session.
    """

    if not session:
        session = ''.join(random.sample(string.ascii_lowercase
                                        + string.digits, 16))

    if not package.session:
        package.session = session
        models.Package.objects.filter(
            id=package.id
        ).update(
            session=session
        )
        return session

    else:
        if package.session == session:
            return session
        else:
            logger.error(
                'Session %s interrupted at %s: package belongs to session %s.',
                session,
                task,
                package.session,
                extra={'tags': {
                    'package': package.id,
                    'session': session,
                }}
            )
            return False


@task(base=PackageTask, name='packages.production')
def production(id, session=None, count=0):
    """Make video for the specified package."""
    package = models.Package.objects.get(pk=id)

    session = validate_session(package, session, 'packages.production')
    if not session:
        return

    package.set_status('production')

    if package.campaign.is_idomoo_backend:
        url = video_backends.idomoo.push(package)

        models.Package.objects.filter(
            id=package.id
        ).update(
            stupeflix_key=uuid.uuid4().hex,  # to have a random video file name
            asset=url   # That field is unused, why not use it here
        )

        storage.delay(id, session, count)

    else:
        response = video_backends.stupeflix.push(package)

        models.Package.objects.filter(
            id=package.id
        ).update(
            stupeflix_key=response[0]['key'],
        )

        storage.apply_async(args=(id, session, count), countdown=120)


@task(base=PackageTask, name='packages.storage')
def storage(id, session=None, count=0):
    """Receive a video from Stupeflix and send it to BitsOnTheRun."""

    package = models.Package.objects.get(id=id)

    session = validate_session(package, session, 'packages.storage')
    if not session:
        return

    if package.campaign.is_idomoo_backend:
        url = package.asset

    else:
        try:
            url = video_backends.stupeflix.pull(package, session=session)

        except RestartProcessing:
            production.apply_async(args=(id, session, count + 1),
                                   countdown=10 * 60)  # Restart later
            return

        except Wait:
            logger.info('Trying again.', extra={
                'tags': {'package': id, 'session': session},
            }, exc_info=True)

            storage.retry(countdown=60 * (storage.request.retries + 1))
            return

    response = requests.get(url, stream=True)
    logger.info('URL for storing package {}'.format(url))
    logger.info('Received status {} when storing package...'.format(response.status_code))
    if response.status_code not in ('200', 200):
        if storage.request.retries <= 10:
            logger.info('Trying again for {} package, count {}'.format(id, storage.request.retries))
            storage.retry(countdown=5 * (storage.request.retries + 1))
        else:
            raise MaxRetriesExceededError()
    
    # We might send the package to JWPlatform...
    if package.campaign.streaming_enable:
        video_key = _send_to_botr(package, url)

    else:
        video_key = None

    # And, in parallel, just save video on disk
    # Prepare directory
    try:
        os.makedirs(os.path.dirname(package.video_path()))
    except OSError, error:
        if error.errno == errno.EEXIST:
            pass
        else:
            raise

    with open(package.video_path(), 'wb+') as f:
        for chunk in response:
            f.write(chunk)

    models.Package.objects.filter(
        id=id
    ).update(
        video_key=video_key,
        status='storage'
    )

    publish.apply_async(args=(id, session, count), countdown=10)


def _send_to_botr(package, url):
    """
    Publish the video (from URL given) to BoTR and attach to the package given.
    """

    botr = package.campaign.botr()

    title = '_'.join(map(
        lambda s: s.replace(' ', '-').lower(), filter(
            lambda s: bool(s), [
                package.company.name,
                package.contact.name,
                package.recipient_email,
                str(package.created_time or ''),
            ]
        )
    ))

    # Try to call several times if necessary
    response = None
    iteration = 0
    for iteration in range(3):
        response = botr.call('/videos/create', {
            'title': title,
            'tags': ', '.join([
                'Package: %s' % package.pk,
                'Company: %s' % package.company.name,
                'Campaign: %s' % package.campaign.name,
                'Contact: %s' % package.contact.name,
            ]),
            'description': 'A video for %s.' % package.recipient_email,
            'link': 'http://www.vboost.com',
            'author': package.contact.name,
            'download_url': url,
        })

        if response['status'] == 'error' \
                and response['code'] == 'EmptyResponse':
            continue

        else:
            break

    if response['status'] == 'error':
        logger.error(
            'Failed to upload video to BitsOnTheRun on iteration %s. %s',
            iteration, response['message'],
            extra={
                'tags': {
                    'package': package.id,
                    'session': package.session
                },
                'response': response,
            }
        )

        raise InterruptProcessing()

    else:
        video_key = response['video']['key']

        # Uploading thumbnail image
        params = botr.call('/videos/thumbnails/update', {
            'video_key': video_key,
        })['link']

        if package.thumbnail():
            botr.upload(params, package.thumbnail().absolute_path())

        return video_key


def _botr_is_ready(package):
    """Is BoTR video ready?"""

    botr_api = package.campaign.botr()

    response = botr_api.call('/videos/show', {
        'video_key': package.video_key,
    })

    video = response.get('video', None)

    if not video:
        raise Exception("No video data: %s" % response)

    status = video['status']

    if status == 'failed':
        if 'content storage limit exceeded' in video['error']['message']:
            # This means that BoTR is out of balance and we can just give up.
            logger.critical('BitsOnTheRun failed processing video. %s',
                            video['error']['message'],
                            extra={
                                'tags': {
                                    'package': package.id,
                                    'session': package.session
                                },
                                'response': video,
                            }
            )
            raise InterruptProcessing(
                'BitsOnTheRun failed processing video. %s'
                % video['error']['message'])

        else:  # In all other cases, we can retry.
            logger.info(
                'BitsOnTheRun failed processing video: %s Trying again.',
                video['error']['message'],
                extra={
                    'tags': {
                        'package': package.id,
                        'session': package.session
                    },
                    'response': video,
                }
            )
            raise RestartProcessing()

    elif status == 'ready':
        # View conversions
        conversions = botr_api.call('/videos/conversions/list', {
            'video_key': package.video_key,
        }).get('conversions')

        # No conversions yet, retrying
        if not conversions:
            return False

        # Check if all conversions are okay
        for conversion in conversions:
            if conversion.get('error', None):
                logger.error(
                    'BitsOnTheRun failed to convert the video.',
                    extra={
                        'tags': {
                            'package': package.id,
                            'session': package.session
                        },
                        'response': conversion,
                    }
                )
                raise InterruptProcessing(
                    'BitsOnTheRun failed to convert the video.'
                )

            elif conversion['status'] != 'Ready' \
                    and conversion.get('required', False):
                logger.info('BoTR conversion is not ready yet.', extra={
                    'tags':
                        {'package': package.id, 'session': package.session},
                    'response': conversion,
                })
                return False

        # Okay, no failed conversions found.
        return True

    else:  # Any other cases
        logger.info('BoTR video is not ready yet.', extra={
            'tags': {'package': package.id, 'session': package.session},
            'response': video,
        })
        return False


# noinspection PyCallingNonCallable
@task(base=PackageTask, name='packages.publish', max_retries=6)
def publish(id, session=None, count=0):
    """Get all things done."""

    package = models.Package.objects.get(pk=id)

    session = validate_session(package, session, 'packages.publish')
    if not session and not package.is_duplicate():
        return

    # Check that package video has been published, if it exists.
    try:
        if package.video_key and not _botr_is_ready(package):
            # 1 min, 2 min, 4 min, 8 min, 16 min
            eta = 60*(2**publish.request.retries)
            estimate = datetime.now() + relativedelta(seconds=eta)

            models.Package.objects.filter(id=package.id)\
                .update(queued_until=estimate)

            publish.retry(countdown=eta)
            return

    except (RestartProcessing, MaxRetriesExceededError):
        # We need to try posting to BoTR again.
        logger.info(
            'Tired of waiting for BoTR. Trying to upload video again.',
            extra={
                'tags': {'package': package.id, 'session': session}
            }
        )
        storage.apply_async(args=(id, session, count + 1), countdown=5*60)
        return

    # Okay, we are done with video... Making thumb.
    make_thumbnails(package)

    if package.cover:
        # Make Admin thumbnail
        get_thumbnail(package.cover.get_masked_thumbnail(), '100')

        # Make Widget thumbnail
        get_thumbnail(
            str(package.cover),
            '241x140',
            crop='faces',
            overlay=package.company.get_stamp_path(),
            # overlay_mode='mask',
        )

    # Landing page
    if not package.landing_page_key or not package.landing_page_url:
        # Generate a unique key
        while True:
            key = ''.join(
                random.sample(string.ascii_lowercase + string.digits, 7)
            )
            if not models.Package.objects.filter(landing_page_key=key):
                package.landing_page_key = key

                package.product_keywords, package.geo_keywords = \
                    package.generate_keywords()

                package.landing_page_url = package.generate_landing_page_url()
                break

    package.status = 'produced'
    package.session = None
    package.queued_until = None

    package.save()

    logger.info('Package is published.', extra={
        'tags': {
            'package': id,
            'session': session
        },
    })

    package.create_event('publish')

    package.cover.get_masked_thumbnail()

    deliver.delay(package.id, session)

    # Trying to create thumbnails on the landing page
    # prefetching it
    view = LandingView(
        object=package,
        kwargs={'landing_page_key': package.landing_page_key},
        request=None
    )
    view.render_to_response(view.get_context_data(
        skip_create_event=True
    )).render()


# To ensure we do not violate SES throttling policy
@task(base=PackageTask, name='packages.deliver', rate_limit='10/m')
def deliver(id, session=None):
    """Send email message for specified package"""

    package = models.Package.objects.get(pk=id)

    session = validate_session(package, session, 'packages.email')
    if not session:
        return

    if package.recipient_email:
        deliver_email(package, session)

        package.__dict__.update({
            'status': 'sent',
            'last_mailed': now(),
            'session': None
        })

        package.save()

    elif package.recipient_phone:
        deliver_text(package, session)

    if package.campaign.vin_solutions_email:
        deliver_vin_solutions(package, session)


def deliver_text(package, session):
    # if settings.DEBUG:
    #     logger.info('Skipping sending an SMS.')
    #     return False

    p = plivo.RestAPI(
        settings.PLIVO_SETTINGS['AUTH_ID'],
        settings.PLIVO_SETTINGS['AUTH_TOKEN']
    )

    status_code, message = p.send_message({
        'src': random.choice(settings.PLIVO_SETTINGS['SRC']),
        'dst': '1' + package.recipient_phone.replace('-', ''),
        'text': package.campaign.type.render('sms', package.context()),
        'type': 'sms'
    })

    logger.info(
        'Text message is sent out to %s.', package.recipient_phone,
        extra={
            'response': (status_code, message),
            'tags': {
                'package': package.id,
                'session': session
            },
        }
    )
    message_uuid = message['message_uuid'][0]
    package.create_event(
        'text',
        'Text message is sent out to %s. message_uuid: %s' %
        (package.recipient_phone, message_uuid)
    )
    package.create_event(
        'text',
        'Text message is sent out to %s.' %
        package.recipient_phone
    )

    if (status_code != 202) or isinstance(message, str):
        logger.warning('Unknown status code %s.', status_code, extra={
            'message_state': message,
            'tags': {
                'package': package.id,
                'session': session
            }
        })
        raise Exception(
            message.get('error', 'Unknown status code {}.'.format(status_code))
        )

    package.create_event('text', 'Text message UUID %s.' % message_uuid)

    # Now checking if the message was successfully sent
    return text_delivery_check.apply_async(
        args=(package.id, message_uuid, session, 100),
        countdown=10
    )


@task(base=PackageTask, name='packages.text_delivery_check')
def text_delivery_check(package_id, message_uuid, session=None,
                        retry_count=100):
    if retry_count <= 0:
        raise Exception(
            'Interrupt processing of deliver sms because of exceed '
            'of try limit'
        )

    package = models.Package.objects.get(id=package_id)
    p = plivo.RestAPI(
        settings.PLIVO_SETTINGS['AUTH_ID'],
        settings.PLIVO_SETTINGS['AUTH_TOKEN']
    )

    status_code, message_status = p.get_message({
        'message_uuid': message_uuid
    })

    if status_code != 200:
        logger.warning('Unknown status code %s.', status_code, extra={
            'message': message_status,
            'tags': {
                'package': package.id,
                'session': session
            }
        })

    message_state = message_status.get('message_state')

    if message_state == 'queued':
        text_delivery_check.apply_async(
            args=(package_id, message_uuid, session, retry_count - 1),
            countdown=30
        )

    elif message_state == 'failed':
        logger.info('Failed to deliver a text message.', extra={
            'message_status': message_status,
            'tags': {
                'package': package.id,
                'session': session
            }
        })
        raise Exception('Failed to deliver a text message.')

    else:
        is_delivered = {
            'sent': True,
            'delivered': True,
            'undelivered': False
        }.get(message_state)

        if is_delivered is None:
            logger.info('Plivo returned non recognized response.', extra={
                'message_status': message_status,
                'tags': {
                    'package': package.id,
                    'session': session
                }
            })
            raise Exception('Plivo has returned a non recognized response. '
                            'See logging for details.')

        package.__dict__.update({
            'status': {
                True: 'sent',
                False: 'bounced'
            }[is_delivered],
            'last_mailed': now(),
            'session': None
        })

        if is_delivered:
            deliver_text_info_email(package, session)

        package.save()


def deliver_text_info_email(package, session):
    # And the contact
    to = []
    if package.company.forward_to_contacts and package.contact \
            and package.contact.email:
        to.append(package.contact.email)

    email_managers = validate_email_list(package.campaign.email_managers)
    if email_managers:
        to.extend(email_managers)

    if not to:
        return

    # Render email content
    content = package.campaign.type.render('email', package.context())

    subject = "[SMS] Photos from {} for {}".format(
        package.company,
        package.recipient_phone
    )

    # Who is responsible for the message?
    host = settings.OUTBOUND_EMAIL_HOST
    from_email = '%s <%s@%s>' % (
        package.company.default_display_name or package.company.name,
        package.company.slug,
        host
    )

    # Where to send a copy?
    bcc = ['vboostdeliveries@gmail.com']

    # Bounce path
    bounce = 'bounce@%s' % host

    headers = {
        'From': from_email,
        'Reply-To': from_email,

        'Sender': from_email,
        'Return-Path': bounce,

        'Bcc': ','.join(bcc),
    }

    send(content, subject, to, from_email, headers, bcc=bcc)


def deliver_email(package, session):
    # Is this email address allowed for this company?
    if UnsubscribedEmail.objects.filter(
            email=package.recipient_email, company=package.company):
        msg = 'Email is not sent to %s because this address has ' \
              'unsubscribed from %s communications.' % (
                  package.recipient_email,
                  package.company
              )

        package.create_event('suppress_email', msg)

        logger.info(msg, extra={
            'tags': {'package': id, 'session': session},
        })

        package.status = 'suppressed'
        package.save()
        return

    # Render email content
    try:
        content = package.campaign.type.render('email', package.context())
    except Exception, exc:
        raise Exception('Cannot render email template. %s' % exc)

    subject = package.campaign.default_subject \
                  or "Your photos from %s" % package.company

    if package.recipient_name:
        to = '%s <%s>' % (
            package.recipient_name,
            package.recipient_email
        )
    else:
        to = package.recipient_email

    # Who is responsible for the message?
    host = settings.OUTBOUND_EMAIL_HOST
    from_email = '%s <%s@%s>' % (
        package.company.default_display_name or package.company.name,
        package.company.slug,
        host
    )

    # Where to send a copy?
    bcc = ['vboostdeliveries@gmail.com']

    # And the contact
    if package.company.forward_to_contacts and package.contact \
            and package.contact.email:
        bcc.append(package.contact.email)

    email_managers = validate_email_list(package.campaign.email_managers)
    if email_managers:
        bcc.extend(email_managers)

    # Bounce path
    bounce = 'bounce@%s' % host

    headers = {
        'From': from_email,
        'Reply-To': from_email,

        'Sender': from_email,
        'Return-Path': bounce,

        'Bcc': ','.join(bcc),
    }

    send(content, subject, to, from_email, headers, bcc=bcc)

    package.create_event('email', 'Email is sent out to %s.'
                         % package.recipient_email)

    logger.info('Email is sent out to %s.', package.recipient_email, extra={
        'tags': {'package': package.id, 'session': session},
    })


def deliver_vin_solutions(package, session):
    from django.template import loader, Context

    content = loader.get_template('campaigns/email/vinsolutions.xml')
    content = content.render(Context({
        'package': package
    }))

    subject = "VIN solutions Lead"

    to = package.campaign.vin_solutions_email

    host = settings.OUTBOUND_EMAIL_HOST
    from_email = '%s <%s@%s>' % (
        package.company.default_display_name or package.company.name,
        package.company.slug,
        host
    )

    # Bounce path
    bounce = 'bounce@%s' % host

    bcc = ['chris@vboost.com', 'altaisoft@gmail.com']

    headers = {
        'From': from_email,
        'Reply-To': from_email,

        'Sender': from_email,
        'Return-Path': bounce,

        'Bcc': ','.join(bcc),
    }

    send(None, subject, to, from_email, headers, body=content, bcc=bcc)

    package.create_event(
        'vinsolutions', 'VIN Solutions Email is sent out to %s.' % to)

    logger.info('Email is sent out to %s.', package.recipient_email, extra={
        'tags': {'package': package.id, 'session': session},
    })
