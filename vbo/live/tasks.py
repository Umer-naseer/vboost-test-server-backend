import json
import os
import subprocess
import urllib.parse
import uuid
import requests
import time

from django.db.models.query import QuerySet

from live.models import MontageVideo
from vboostoffice import settings
from vboostoffice.settings import VBOOSTLIVE_URL, FFMPEG_PATH

from django.db.models import signals
from django.dispatch import receiver


EXTENSIONS = [
    '.mp4'
]
FRAME_SEC = 16.0
MAX_RETRIES = 5

CDK_CODE = """<script type='text/javascript'>(function(){var dt=document.createElement('script');dt.type='text/javascript';dt.async=true;var pa='Vboost';var src=document.location.protocol+'//dt.cobaltgroup.com/dt.js?sitetype=dealer&format=js&cblttags=1&framed=1';src+='&referrer='+encodeURIComponent(document.referrer.substr(0,2000));src+='&cs:pg='+encodeURIComponent(pa+' - VBOOST LIVE');src+='&cs:pa='+pa;dt.src=src;var s=document.getElementsByTagName('script')[0];s.parentNode.insertBefore(dt,s);})();</script>"""


def get_full_url(relative_page_name):
    return urllib.parse.urljoin(settings.VBOOSTLIVE_URL+'/',
                            relative_page_name+'/')


def embed_code(self, cdk=False):
    url = os.path.join(VBOOSTLIVE_URL, 'widget/widget')
    widget = '<script async src="{0}-{1}.js"></script>'\
        .format(url, str(self.token))
    if cdk and self.use_cdk:
        widget = '{}\n{}'.format(widget, CDK_CODE)
    return widget


def embed_preview_url(self):
    return os.path.join(VBOOSTLIVE_URL, 'embed-preview', self.slug)


def make_montage_thumbnail_ffmpeg(montage_video):
    """
    This function creates a preview image for video files in the table
    named MontageVideo by FFmpeg library
    :param montage_video: it's a QuerySet from MontageVideo table for
    requesting of preview images
    :return: nothing returns but makes changes in the QuerySet
    """
    def for_only_one_object(clip):
        if not clip.video:
            return
        clip_path = clip.video.path
        image_filename = os.path.join(
            'montage/images', '{}.jpg'.format(str(uuid.uuid4()))
        )
        image_path = os.path.join(settings.MEDIA_ROOT, image_filename)
        if subprocess.call(
                FFMPEG_PATH
                + ' -ss 00:00:02 -i "{0}" -vframes 1 -q:v 2 "{1}"'
                        .format(clip_path, image_path),
                shell=True
        ) == 0:
            clip.image = image_filename
            clip.save()
            print("\n Montage video '{}': [OK]".format(clip.name))

    if isinstance(montage_video, QuerySet):
        for video in montage_video:
            for_only_one_object(video)
    elif isinstance(montage_video, MontageVideo):
        for_only_one_object(montage_video)


def make_montage_thumbnail_stupeflix(montage_video_query):
    """
    This function creates a preview image for video files in the table
    named MontageVideo by request the Stupeflix service
    :param montage_video_query: it's a QuerySet from MontageVideo table
    for requesting of preview images
    :return: nothing returns but makes changes in the QuerySet
    """
    def for_only_one_object(video):
        headers = {"Authorization": settings.STUPEFLIX_SECRET_KEY}
        task = {
            'secret': settings.STUPEFLIX_SECRET_KEY,
            'tasks': {
                'task_name': 'video.thumb',
                'time': FRAME_SEC,
                'crop': True,
                'url': 'https://vboostoffice.com'+video.get_video_url(),
            }
        }
        task_creation = requests.post(
            '{}/v2/create'.format(settings.STUPEFLIX_HOST),
            headers=headers,
            data=json.dumps(task)
        ).json()
        try:
            task_key = task_creation[0]['key']
        except:
            print('Task creation failed. Response: {}'.format(task))
            return
        for try_response in range(MAX_RETRIES):
            response_json = requests.get(
                '{}v2/status'.format(settings.STUPEFLIX_HOST),
                params={"tasks": task_key},
                headers=headers
            ).json()[0]
            response_status = response_json['status']
            if response_status == 'success':
                image_data = requests.get(response_json['result']['output'])
                with open(os.path.join(
                        settings.MONTAGE_ROOT, 'images',
                        '{}.jpg'.format(video.name)), "wb+") \
                        as image_file:
                    image_file.write(image_data.content)
                    video.image = image_file.name[len(settings.MEDIA_ROOT):]
                    video.save()
                print('{}: [OK]'.format(video.name))
                break
            elif response_status in ['executing', 'queued']:
                print('{},  try {}/{}'\
                    .format(video.name, try_response + 1, MAX_RETRIES))
                time.sleep(5)
            elif response_status == 'error':
                print('error [{}],  {}'\
                    .format(video.name, response_json['error']))
                break

    if type(montage_video_query) == 'QuerySet':
        for video in montage_video_query:
            for_only_one_object(video)
    elif str(type(montage_video_query)) == \
            "<class 'live.models.MontageVideo'>":
        for_only_one_object(montage_video_query)


@receiver(signals.post_save, sender=MontageVideo,
          dispatch_uid='on_new_montage_video')
def on_new_montage_video(sender, instance, created=False, raw=False, **kwargs):
    """On a new loaded montage video"""
    if created:
        make_montage_thumbnail_ffmpeg(instance)
