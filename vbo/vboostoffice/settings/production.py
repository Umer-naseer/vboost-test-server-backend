from .base import *
import os.path
import mysql.connector

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration


ALLOWED_HOSTS = [
    #'vboostoffice.com',
    #'www.vboostoffice.com',
    #'vboostlive.com',
    #'www.vboostlive.com',
    'localhost',
    '127.0.0.1',
    '54.237.135.111',
    '54.147.94.6',
    'vboostpython3.tk',
    'vboostlive3.tk',
    'www.vboostpython3.tk',
    'www.vboostlive3.tk',
    'api.vboostlive3.tk',
]

DATABASES = {
    'default': {
        # Add 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3'
        # or 'oracle'.
        'ENGINE': 'django.db.backends.mysql', #'mysql.connector.django',
        'NAME': 'vboost',  # Or path to database file if using sqlite3.
        'USER': 'root',  # Not used with sqlite3.
        'PASSWORD': 'Umer-Ibuildx123',   # Not used with sqlite3.
        # Set to empty string for localhost. Not used with sqlite3.
        'HOST': 'test-server-vboost-p3-db02.ceezv8mmuw3t.us-east-1.rds.amazonaws.com',
        # 'HOST': 'localhost',
        'PORT': '',  # Set to empty string for default. Not used with sqlite3.
        'STORAGE_ENGINE': 'INNODB',
        'OPTIONS': {
            #  "init_command": "SET foreign_key_checks = 0;",
            'autocommit': True,
            'ssl' : False,
        },
    },
}

# Enable Setnry logging
sentry_sdk.init(
    dsn="https://d752c1f84b4c40b99a8c48ab4854d02e@o475557.ingest.sentry.io/5515737",
    integrations=[DjangoIntegration()],
    traces_sample_rate=1.0,

    # If you wish to associate users to errors (assuming you are using
    # django.contrib.auth) you may enable sending PII data.
    send_default_pii=True
)

#INSTALLED_APPS += (
#    'raven.contrib.django.raven_compat',
#)
#RAVEN_CONFIG = {
#    'dsn': 'http://e7a59d76d38147889741994eafc761b0:d8f81003808f43aa8d5bf1f83ea8f639@sentry.criterion-dev.net/5',
    # If you are using git, you can also automatically configure the
    # release based on the git info.
    # 'release': raven.fetch_git_sha(os.path.dirname(__file__)),
#}

MEDIA_ROOT = '/data/media/'
MONTAGE_ROOT = os.path.join(MEDIA_ROOT, 'montage')
FFMPEG_PATH = '/usr/local/bin/ffmpeg'
IDOMOO_HOST_URL = 'https://vboostlive3.tk'
