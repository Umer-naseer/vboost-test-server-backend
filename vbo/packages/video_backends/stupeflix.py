import json

import logging
from django.conf import settings
import requests
from packages.models import Wait, InterruptProcessing, RestartProcessing


logger = logging.getLogger(__name__)


def push(package):
    # Craftsman video template
    definition = package.render_video_template()

    if not definition:
        raise Exception('Video template is empty. Please check if a video '
                        'template is assigned to "%s" campaign.'
                        % package.campaign)

    response = requests.post('%s/v1/create' % settings.STUPEFLIX_HOST,
                             data=json.dumps({
                                 'secret': settings.STUPEFLIX_SECRET_KEY,
                                 'tasks': [{
                                     'task_name': 'video.create',
                                     'preview': False,
                                     'profile': settings.STUPEFLIX_PROFILE,
                                     'definition': definition, }]
                             }),
                             verify=False)

    if response.status_code != 200:
        logger.error(
            'Stupeflix refuses to accept the video for production.',
            extra={
                'tags': {
                            'package': id,
                            'session': package.session,
                        },
                'response': response.json(),
            }
        )
        raise Exception()  # to retry

    return response.json()


def pull(package, session):
    # Okay, first, we go to Stupeflix to see if there is something for us.
    key = package.stupeflix_key

    response = requests.post('%s/v1/status' % settings.STUPEFLIX_HOST,
                             data=json.dumps({
                                'secret': settings.STUPEFLIX_SECRET_KEY,
                                'tasks': [key], }),
                             verify=False).json()[0]

    status = response['status']

    # Are we still waiting for Stupeflix?
    if status in ('queued', 'executing'):
        raise Wait('Stupeflix is still busy')

    elif status == 'error':
        logger.warning(
            'Stupeflix returned a critical error. %s',
            response['result'],
            extra={
                'tags':
                    {
                        'package': id,
                        'session': session
                    },
                    'response': response,
            }
        )

        if any(s in response['result'] for s in [
            'InvalidXMLError',
            'InvalidContentError',
            'InvalidFontError',
            'InvalidImageError',
            'Need to download some file',
            'there is no task with this ID',
            'We should stop immediately',
            'CouldNotDownloadError'
        ]):
            raise InterruptProcessing(
                'Stupeflix error: %s' % response['result'])

        else:
            raise RestartProcessing('Stupeflix threw an error.')

    elif status != 'success':
        logger.critical('Unknown Stupeflix status "%s".' % status, extra={
            'tags': {'package': id, 'session': session},
            'response': response,
        })

    # Yeah, we finally have the video! Returning it.
    logger.info('Stupeflix is done processing video.', extra={
        'tags': {'package': id, 'session': session},
        'response': response,
    })

    url = response['result']['export']

    # Resolving URL redirect
    url = requests.get(
        url, stream=True, verify=False
    ).url.replace(
        'https', 'http'
    )

    return url
