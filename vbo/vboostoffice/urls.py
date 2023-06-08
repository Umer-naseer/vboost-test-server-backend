from django.contrib import admin
from django.conf.urls import patterns, include, url
from django.conf import settings

admin.autodiscover()

urlpatterns = patterns(
    '',
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # API
    url(r'^api/v1/', include('vboostoffice.api')),

    # smart_selects
    # url(r'^chaining/', include('smart_selects.urls')),

    # ATC
    url(r'^o/', include('offers.urls')),
    url(r'^', include('mailer.urls')),
    url(r'^users/', include('users.urls')),
    url(r'^a/', include('live.urls', namespace='live')),

    # Login and logout
    (r'^login', 'django.contrib.auth.views.login',
        {'template_name': 'clients/login.html'}),
    (r'^logout', 'django.contrib.auth.views.logout_then_login'),

    url(r'^password_reset/$', 'django.contrib.auth.views.password_reset',
        name='admin_password_reset'),
    url(r'^password_reset/done/$',
        'django.contrib.auth.views.password_reset_done',
        name='password_reset_done'),
    (r'^reset/(?P<uidb36>[0-9A-Za-z]+)-(?P<token>.+)/$',
     'django.contrib.auth.views.password_reset_confirm'),
    (r'^reset/done/$', 'django.contrib.auth.views.password_reset_complete'),

    url(r'^', include(admin.site.urls)),
)

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += patterns(
        '',
        url(r'^__debug__/', include(debug_toolbar.urls)),
    )

if settings.DEBUG:
    urlpatterns += patterns(
        '',
        url(r'^media/(?P<path>.*)$', 'django.views.static.serve', {
            'document_root': settings.MEDIA_ROOT,
        }),
    )
