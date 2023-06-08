# -*- coding: utf-8 -*-

'Dev settings'

from .base import *
import mysql.connector

RAVEN_CONFIG = {
    'allowDuplicates': 'false',
    'debug': 'false',
}

INSTALLED_APPS += (
    'raven.contrib.django.raven_compat',
)

DEBUG = True

_CODEBASE = dirname(realpath(__file__))
ROOT = dirname(_CODEBASE)

MONTAGE_ROOT = join(MEDIA_ROOT, 'montage')
MEDIA_URL = '/media/'

VBOOSTLIVE_URL = '/a'

VIDEO_ROOT = '/tmp/'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'vboost2',  # Or path to database file if using sqlite3.
        'USER': 'root',  # Not used with sqlite3.
        'PASSWORD': '123456',    # Not used with sqlite3.
        'HOST': 'localhost',        # Set to empty string for localhost.
                           # Not used with sqlite3.
        'PORT': '3306',        # Set to empty string for default.
                           # Not used with sqlite3.
        'STORAGE_ENGINE': 'INNODB',
    },
}

# DATABASES = {
#     'default': {
#         'NAME': 'vboost',
#         'ENGINE': 'mysql.connector.django',
#         'USER': 'root',
#         'PASSWORD': '123456',
#         'OPTIONS': {
#           'autocommit': True,
#         },
#     }
# }


TEST = bool({'test'} & set(sys.argv))

if TEST:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
        },
    }

LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'root': {
        'level': 'DEBUG',
        'handlers': ['console'],
    },
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d '
                      '%(thread)d %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        }
    },
    'loggers': {
        'django.db.backends': {
            'level': 'DEBUG' if 'SQL' in os.environ else 'WARNING',
            'handlers': ['console'],
            'propagate': False,
        },
        'celery': {
            'level': 'DEBUG',
            'handlers': ['console'],
            'propagate': True,
        },
        'raven': {
            'handlers': ['console'],
            'level': 'WARNING',
            'formatter': 'verbose'
        }
    },

}

if 'DEBUG_TOOLBAR' in os.environ.keys():
    INSTALLED_APPS += (
        'debug_toolbar',
    )

    DEBUG_TOOLBAR_PANELS = (
        'debug_toolbar.panels.versions.VersionsPanel',
        'debug_toolbar.panels.timer.TimerPanel',
        'debug_toolbar.panels.settings.SettingsPanel',
        'debug_toolbar.panels.headers.HeadersPanel',
        'debug_toolbar.panels.request.RequestPanel',
        'debug_toolbar.panels.sql.SQLPanel',
        'debug_toolbar.panels.staticfiles.StaticFilesPanel',
        'debug_toolbar.panels.templates.TemplatesPanel',
        'debug_toolbar.panels.cache.CachePanel',
        'debug_toolbar.panels.signals.SignalsPanel',
        'debug_toolbar.panels.logging.LoggingPanel',
        'debug_toolbar.panels.redirects.RedirectsPanel',
    )

    MIDDLEWARE_CLASSES += (
        'debug_toolbar.middleware.DebugToolbarMiddleware',
    )

EMAIL_BACKEND = 'django.core.mail.backends.dummy.EmailBackend'
