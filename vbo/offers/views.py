import json
import logging
from . import forms
from . import models
import datetime

from django.shortcuts import HttpResponse, get_object_or_404


logger = logging.getLogger(__name__)


def offer_view(request, package):
    """Submit"""

    # Prepare data
    data = request.POST.copy()
    data['package'] = str(package.id)

    form = forms.SubmissionForm(data)
    form.full_clean()

    if form.errors:
        return HttpResponse(json.dumps({
            'errors': form.errors,
        }), content_type='application/json')

    else:
        form.save()

        return HttpResponse(json.dumps({
            'ok': True,
        }), content_type='application/json')


def redeem_view(request, key):
    submission = get_object_or_404(models.Submission, key=key)

    models.Submission.objects.filter(
        id=submission.id
    ).update(
        last_redeem_time=datetime.datetime.now()
    )

    # Show the page
    return HttpResponse(submission.offer.redeem_template.render(
        submission.context()
    ))
