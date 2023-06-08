# Necessary to enable the tasks and signal handlers
# noinspection PyUnresolvedReferences
from .views import redeem_view

from django.conf.urls import patterns, url


urlpatterns = patterns(
    '',
    url(r'^redeem/(?P<key>[-\w]+)/', redeem_view, name='offers-redeem'),
)
