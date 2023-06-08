import os
from dateutil import parser
import json
import requests
import time

from django.core.management.base import BaseCommand
from django.conf import settings

from clients.models import Company
from live.models import MontageVideo


EXTENSIONS = [
    '.mp4'
]
FRAME_SEC = 16.0
MAX_RETRIES = 5


class Command(BaseCommand):

    def handle(self, *args, **options):
        existing_video = list(MontageVideo.objects.values_list('name',
                                                               flat=True))
        video_file_list = os.listdir(os.path.join(settings.MONTAGE_ROOT,
                                                  'videos'))
        video_filenames = [os.path.splitext(filename)[0]
                           for filename in video_file_list]

        for video in existing_video:
            if video not in video_filenames:
                MontageVideo.objects.filter(
                    name=video).update(is_visible=False)

        for video in MontageVideo.objects.filter(is_visible=False):
            if video.name in video_filenames:
                MontageVideo.objects.filter(name=video).update(is_visible=True)

        for filename in video_file_list:
            name, extension = os.path.splitext(filename)
            if extension in EXTENSIONS and name not in existing_video:
                try:
                    company_slug, description = name.split('.', 1)
                except Exception as exc:
                    print '{}: [FAILED] {}'.format(filename, exc)
                    company_slug = name
                    description = None

                try:
                    company = Company.objects.get(slug=company_slug)
                except Company.DoesNotExist, exc:
                    print '{}: [FAILED] {}'.format(filename, exc)
                    continue

                try:
                    video_date = parser.parse(description).date()
                except (ValueError, TypeError, AttributeError):
                    video_date = None

                video = MontageVideo(
                        name=name, date=video_date, company=company
                )
                headers = {"Authorization": settings.STUPEFLIX_SECRET_KEY}
                task = {
                    'secret': settings.STUPEFLIX_SECRET_KEY,
                    'tasks': {
                        'task_name': 'video.thumb',
                        'time': FRAME_SEC,
                        'crop': True,
                        'url': video.get_video_url(),
                    }
                }
                task_creation = requests.post(
                    '{}/v2/create'.format(settings.STUPEFLIX_HOST),
                    headers=headers, data=json.dumps(task)).json()
                try:
                    task_key = task_creation[0]['key']
                except:
                    print 'Task creation failed. Response: {}'.format(task)
                    continue
                for try_response in range(MAX_RETRIES):
                    response_json = \
                        requests.get('{}/v2/status'
                                     .format(settings.STUPEFLIX_HOST),
                                     params={"tasks": task_key},
                                     headers=headers).json()[0]
                    response_status = response_json['status']
                    if response_status == 'success':
                        video.save()
                        image_data = \
                            requests.get(response_json['result']['output'])
                        with open(os.path.join(
                                settings.MONTAGE_ROOT, 'images',
                                '{}.jpg'.format(name)), "wb+") as image_file:
                            image_file.write(image_data.content)
                        print '{}: [OK]'.format(filename)
                        break
                    elif response_status in ['executing', 'queued']:
                        print '{},  try {}/{}'.format(filename,
                                                      try_response+1,
                                                      MAX_RETRIES)
                        time.sleep(5)
                    elif response_status == 'error':
                        print 'error [{}],  {}'\
                            .format(filename, response_json['error'])
                        break

        self.stdout.write('end')
