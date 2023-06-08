import logging

from django.shortcuts import render_to_response, get_object_or_404, \
    HttpResponse
from clients.models import Package, Event
from .models import UnsubscribedEmail, Email  # , Event


# Taken from http://css-tricks.com/snippets/html/base64-encode-of-1x1px-transparent-gif/
BLANK_GIF = 'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'


def unsubscribe(request, key):
    """Black list an email."""
    p = get_object_or_404(Package, landing_page_key=key)

    instance, is_created = UnsubscribedEmail.objects.get_or_create(
        email=p.recipient_email,
        company=p.company
    )

    msg = 'Unsubscribe %s from further communications of %s.' \
        if is_created else 'Cannot unsubscribe %s from further ' \
                           'communications of %s: already unsubscribed.'

    p.create_event('unsubscribe', msg % (p.recipient_email, p.company))

    return render_to_response('mailer/unsubscribed.html', {
        'email': p.recipient_email,
        'company': p.company,
    })


def track(request, key):
    """Track email open event."""

    email = Email.objects.filter(key=key).first()

    if email:
        Event.objects.create(email=email, type='open')

    else:
        logging.getLogger(__name__)\
            .warning('Email tracking: key "%s" is absent', key, extra={
                        'request': request
                    })

    response = HttpResponse(
        BLANK_GIF.decode('base64'),
        status=200 if email else 404,
        # mimetype='image/gif',
        content_type='image/gif'
    )

    response['Cache-Control'] = 'no-cache, no-store'
    response['Pragma'] = 'no-cache'

    return response
