from __future__ import absolute_import

import os
import celery.signals
from django.conf import settings
from celery import Celery

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vboostoffice.settings')


#@celery.signals.setup_logging.connect
#def setup_logging(**kwargs):
#    """Setup logging."""
#    pass


#class Celery(celery.Celery):
#    def on_configure(self):
#        import raven
#        from raven.contrib.celery import register_signal, \
#            register_logger_signal

#        client = raven.Client()

        # register a custom filter to filter out duplicate logs
#        register_logger_signal(client)

        # hook into the Celery error handler
#        register_signal(client)


app = Celery('vboostoffice')


# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object('django.conf:settings')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
