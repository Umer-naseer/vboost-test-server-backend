from . import views

from django.conf.urls import patterns, url


urlpatterns = patterns(
    '',
    url(r'^unsubscribe/(?P<key>\w+)/$', views.unsubscribe,
        name='mailer-unsubscribe'),
    url(r'^email/tracking/(?P<key>[-\w]+)/$', views.track, name='email-track'),
)
