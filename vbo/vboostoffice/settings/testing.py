from .base import *
import sys

ALLOWED_HOSTS = [
    'vboostoffice.criterion-dev.net',
    'www.vboostoffice.criterion-dev.net',
    'vboostlive.criterion-dev.net',
    'www.vboostlive.criterion-dev.net',
]
DATABASES = {
    'default': {
        # Add 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3'
        # or 'oracle'.
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'vboost',  # Or path to database file if using sqlite3.
        'USER': 'vboost',  # Not used with sqlite3.
        'PASSWORD': '',    # Not used with sqlite3.
        # Set to empty string for localhost. Not used with sqlite3.
        'HOST': '',
        'PORT': '',  # Set to empty string for default. Not used with sqlite3.
        'STORAGE_ENGINE': 'INNODB',
        'OPTIONS': {
             "init_command": "SET foreign_key_checks = 0;",
        },
    },
}


TEST = bool({'test'} & set(sys.argv))

if TEST:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
        },
    }

INSTALLED_APPS += (
    'raven.contrib.django.raven_compat',
)

RAVEN_CONFIG = {
    'dsn': 'http://03125186e0e8409f9930f138dc94d651:140e29c81a064dec8230248b4dc54767@sentry.criterion-dev.net/6',
    # If you are using git, you can also automatically configure the
    # release based on the git info.
    # 'release': raven.fetch_git_sha(os.path.dirname(__file__)),
}

DEBUG = True

MEDIA_URL = 'http://vboostoffice.criterion-dev.net/media/'

VBOOSTLIVE_URL = 'http://vboostoffice.criterion-dev.net/a'
HOST_URL = 'http://vboostoffice.criterion-dev.net'
FFMPEG_PATH = '/usr/bin/ffmpeg'
FFPROBE_PATH = '/usr/bin/ffprobe'

EMAIL_BACKEND = 'django.core.mail.backends.dummy.EmailBackend'
