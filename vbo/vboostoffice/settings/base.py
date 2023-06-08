
# Django settings for vboost project.

import os
import sys
from os.path import realpath, dirname, join
from django.conf.global_settings import TEMPLATE_CONTEXT_PROCESSORS as TCP


_CODEBASE = dirname(dirname(dirname(realpath(__file__))))
ROOT = dirname(_CODEBASE)

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    # ('admin', 'altaisoft@gmail.com'),
)

MANAGERS = ADMINS

# SOUTH_TESTS_MIGRATE = False

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/0',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
CACHE_EXPIRY_TIME = 60 * 60 * 12 - 1

SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30    # 30 days
SESSION_SAVE_EVERY_REQUEST = True

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'US/Pacific'  # 'US/Pacific'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = False

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

USE_TZ = False

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
#MEDIA_ROOT = join(ROOT, 'media')
MEDIA_ROOT = join(ROOT, 'media')
VBOOSTLIVE_ROOT = "/data/media/"

VIDEO_ROOT = '/data/video/'

LIVE_MEDIA_URL = 'https://vboostlive3.tk/media/'
# LIVE_MEDIA_URL = 'http://vboostoffice.com/media/'

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL =  'https://vboostlive3.tk/media/'

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = join(ROOT, 'static')

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

VBOOSTLIVE_URL = 'https://vboostlive3.tk'
HOST_URL = 'https://vboostlive3.tk'

# URL prefix for admin static files -- CSS, JavaScript and images.
# Make sure to use a trailing slash.
# Examples: "http://foo.com/static/admin/", "/static/admin/".
ADMIN_MEDIA_PREFIX = '/static/admin/'

# Additional locations of static files
STATICFILES_DIRS = [
    os.path.join(_CODEBASE, "vboostoffice/static"),
]

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    # 'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = '895gsc%3k7umaf-7#r88#xaou@n2!!^^_o#f=1k+86zu6$*#u@'

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'login_required.LoginRequiredMiddleware',
)

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            'vboostoffice/templates'
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': list(TCP) + [
                'django.core.context_processors.request',
                'vboostoffice.context_processors.index',
                'django.core.context_processors.static',
            ],
        },
    },
    {
        'BACKEND': 'django.template.backends.jinja2.Jinja2',
        'DIRS': [
            os.path.join(_CODEBASE, 'campaigns/templates/campaigns')
        ],
        'OPTIONS': {
            'extensions': ['jinja2.ext.with_']
        }
    }
]

ROOT_URLCONF = 'vboostoffice.urls'

PROJECT_APPS = (
    'clients',
    'live',
    'packages',
    'offers',
    'mailer',
    'campaigns',
    'incoming',
    'templates',
    'daterange_filter',
    'reporting',
    'imports',
    'users',
)

INSTALLED_APPS = (
    'django.contrib.staticfiles',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.humanize',

    'sorl.thumbnail',
    'inline_ordering',
    'adminsortable',
    'adminsortable2',
    'feincms',
    # 'feincms.module.medialibrary',
    'django_extensions',
    'gallery',

    'import_export',
    'rest_framework',
    'rest_framework.authtoken',
    'djoser',


    # Uncomment the next line to enable the admin:
    # Uncomment the next line to enable admin documentation:
    # 'django.contrib.admindocs',
) + PROJECT_APPS + ('django.contrib.admin',)

# FEINCMS_USE_PAGE_ADMIN = False

CELERYD_HIJACK_ROOT_LOGGER = False
# BROKER_URL  = 'amqp://vbo:vbo@localhost:5672/vbo'
BROKER_URL = 'redis://localhost:6379/1'


# URL of login page
LOGIN_URL = '/login/'

# Exempted from login protection
LOGIN_EXEMPT_URLS = (
    'password_reset',
    'reset',
    'api',
    'unsubscribe',
    'email/tracking',
    'o/redeem',
    'a/',
    'a',
    'media',
    'users',
    'favicon.ico'
)

# Page where to redirect after login
LOGIN_REDIRECT_URL = '/'

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
)

CUSTOM_USER_MODEL = 'clients.User'

FORCE_SCRIPT_NAME = ''

DEFAULT_FROM_EMAIL = 'vboost@vbresp.com'

# IMAGES_PER_PACKAGE = 6
PACKAGES_PER_PAGE = 3

# Stupeflix settings
# STUPEFLIX_ACCESS_KEY = 'le96QaB2reGqk4UORO1E'
# STUPEFLIX_SECRET_KEY = 'h5HokCxLjTCEX4c7jQVLHFO62qGJlPP3gMhgSuhm'
# STUPEFLIX_ACCESS_KEY = 'od0yuVN5eShHrih2wIO1'
# STUPEFLIX_SECRET_KEY = '9j4YpMH9cAF6rsKSsznnWEw0Gdinf09gQ05ysr6d'
# STUPEFLIX_HOST       = 'http://services.stupeflix.com/'
STUPEFLIX_USER = 'vboost'
STUPEFLIX_PROFILE = '720p'

STUPEFLIX_HOST = 'https://dragon.stupeflix.com/'
# STUPEFLIX_ACCESS_KEY = 'zwqgf4as2vhki'
# STUPEFLIX_SECRET_KEY = 'J2AMD6A2NZCNLE67L7OWKS74AE'

STUPEFLIX_ACCESS_KEY = 'o6twp4c33jce2'
STUPEFLIX_SECRET_KEY = '5FNLFFNM7JDXPKCJ7LNYUQGYIA'


# BitsOnTheRun settings
BOTR_KEY = 'EHF6AuqM'
BOTR_SECRET = 'lBLdlYJtQjKhgZBtyBs1GFeT'

# BitsOnTheRun video player. %s stands for video key.
VIDEO_EMBED = '<script type="text/javascript" src="http://content.' \
              'bitsontherun.com/players/%s-sZh5Cjaw.js"></script>'


ALLOWED_HOSTS = [
#    'vboostoffice.com',
#    'www.vboostoffice.com',
#    'vboostlive.com',
#    'api.vboostlive.com',
#    'www.vboostlive.com',
    'localhost',
    '127.0.0.1'
]

# Dev settings


MONTAGE_ROOT = join(MEDIA_ROOT, 'montage')

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
#LOGGING = {
#    'version': 1,
#    'disable_existing_loggers': True,
#    'root': {
#        'level': 'INFO',
#        'handlers': ['sentry'],
#    },
#    'formatters': {
#        'verbose': {
#            'format': '%(levelname)s %(asctime)s %(module)s %(process)d '
#                      '%(thread)d %(message)s'
#        },
#    },
#    'handlers': {
#        'sentry': {
#            'level': 'INFO',
#            'class': 'raven.contrib.django.raven_compat.handlers.'
#                     'SentryHandler',
#        },
#        'console': {
#            'level': 'DEBUG',
#            'class': 'logging.StreamHandler',
#            'formatter': 'verbose'
#        }
#    },
#    'loggers': {
#        'sentry': {
#            'handlers': ['sentry'],
#            'level': 'INFO',
#            'propagate': False,
#        },
#        'django.db.backends': {
#            'level': 'ERROR',
#            'handlers': ['console'],
#            'propagate': False,
#        },
#        'raven': {
#            'level': 'DEBUG',
#            'handlers': ['console', 'sentry'],
#            'propagate': False,
#        },
#        'sentry.errors': {
#            'level': 'DEBUG',
#            'handlers': ['console'],
#            'propagate': False,
#        },
#        'celery': {
#            'level': 'INFO',
#            'handlers': ['sentry'],
#            'propagate': False,
#        },
#        'celery.redirected': {
#            'level': 'DEBUG',
#            'handlers': ['console'],
#            'propagate': False,
#        },
#        'apiclient.discovery': {
#            'level': 'CRITICAL',
#            'handlers': ['sentry'],
#            'propagate': False,
#        },
#        'lamson': {
#            'level': 'INFO',
#            'handlers': ['sentry'],
#            'propagate': False,
#        },
#    },
#}

#if DEBUG:
#    INSTALLED_APPS = list(INSTALLED_APPS)
#    INSTALLED_APPS.remove('raven.contrib.django.raven_compat')

if False and DEBUG:
    INSTALLED_APPS += ('debug_toolbar', )
    MIDDLEWARE_CLASSES += ('debug_toolbar.middleware.DebugToolbarMiddleware',)


def custom_show_toolbar(request):
    return True  # Always show toolbar, for example purposes only.


INTERNAL_IPS = ('127.0.0.1', )

LOCK_TIME = 600  # 10 minutes to lock

DATE_INPUT_FORMATS = ('%Y-%m-%d', )

AUTH_PROFILE_MODULE = 'clients.UserProfile'

# Mail settings
DEFAULT_BOUNCE_EMAIL = 'bounce@vboostlive.com'

# OUTBOUND_EMAIL_HOST = 'vboostlive.com'
OUTBOUND_EMAIL_HOST = 'vbresp.com'

# SES via SMTP
EMAIL_HOST = 'email-smtp.us-east-1.amazonaws.com'
EMAIL_HOST_USER = "AKIAT7CAZ5JFLEWKFD5T"
EMAIL_HOST_PASSWORD = "BATya5Xt4jtxxOKK1Jm2or4yaambgfMXuJ99FK4aRUAw"
EMAIL_PORT = 587
EMAIL_USE_TLS = True

# SMTP server
# EMAIL_HOST = "zentano.smtp.com"
# EMAIL_HOST_USER = "cmiller@adsoftdirect.com"
# EMAIL_HOST_PASSWORD = "iloveAmanda1"
# EMAIL_PORT = 25025

REST_FRAMEWORK = {
    # Use Django's standard `django.contrib.auth` permissions,
    # or allow read-only access for unauthenticated users.
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
}

# SES via API
# EMAIL_BACKEND = 'django_ses.SESBackend'
# AWS_SES_ACCESS_KEY_ID = 'AKIAIKVG3JONYRFYPTYQ'
# AWS_SES_SECRET_ACCESS_KEY = "ApFLMdgPfSs43iky2XwjOVJ9bbPCsOT9/V1vaUEWpTR2"

# AWS_SES_REGION_ENDPOINT = 'email.us-east-1.amazonaws.com'
# AWS_SES_REGION_NAME = 'us-east-1'

PLIVO_SETTINGS = {
    'AUTH_ID': "SAODDLNMU1ZTDJYWY1OW",
    'AUTH_TOKEN': "Zjk5YmI2ZDFmYmQyYzg1YmQwZmQ3N2IzNmI2YmNi",
    'SRC': [
        "18772211531",
    ],
}

# BROKER_URL = 'amqp://vbo:vbo@localhost:5672/vbo'
BROKER_URL = 'redis://localhost:6379/1'


# Sorl.thumbnail settings
THUMBNAIL_ENGINE = 'vboostoffice.thumbnail.VboostEngine'
TEST_RUNNER = 'django.test.runner.DiscoverRunner'

# iPython Notebook
NOTEBOOK_ROOT = os.path.join(ROOT, 'notebook')
NOTEBOOK_ARGUMENTS = [
    '--no-browser',
    '--notebook-dir', NOTEBOOK_ROOT
]


# Speeding up testing by disabling database migrations.
# See http://stackoverflow.com/a/28560805/1245471
class DisableMigrations(object):
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return "notmigrations"


TESTS_IN_PROGRESS = False

if 'test' in sys.argv[1:]:
    TESTS_IN_PROGRESS = True
    MIGRATION_MODULES = DisableMigrations()
