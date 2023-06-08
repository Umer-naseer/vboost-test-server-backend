from . import views

from django.conf.urls import patterns, url


urlpatterns = patterns(
    '',
    url(r'^login/$', views.CustomLogin.as_view(), name="login"),

    # url(r'^$', cache_page(settings.CACHE_EXPIRY_TIME)
    # (views.IndexView.as_view()), name='index'),
    url(r'^$', views.IndexView.as_view(), name='index'),
    # url(r'^widget/widget-(?P<slug>[\w_-]+).js$',
    # cache_page(settings.CACHE_EXPIRY_TIME)
    # (views.WidgetScriptView.as_view()), name='widget'),
    url(r'^widget/widget-(?P<slug>[\w_-]+).js$',
        views.WidgetScriptView.as_view(), name='widget'),
    # url(r'^(?P<slug>[\w_-]+)/$', cache_page(settings.CACHE_EXPIRY_TIME)
    # (views.CompanyView.as_view()), name='company'),
    url(r'^(?P<slug>[\w_-]+)/$', views.CompanyView.as_view(), name='company'),
    url(r'^embed-preview/(?P<slug>[\w_-]+)/$',
        views.EmbedPreviewView.as_view(), name='test_company'),

    # url(r'^(?P<slug>[\w_-]+)/login$',
    # views.LoginView.as_view(), name='login'),

    url(r'^download_photo/(?P<pk>\d+)/', views.DownloadPhotoView.as_view(),
        name='download_photo'),
    url(r'^tracking/(?P<landing_page_key>\w+)/$',
        views.TrackingPixelView.as_view(), name='tracking-pixel'),
    url(r'^go/(?P<landing_page_key>\w+)/(?P<target>\w+)/',
        views.VisitView.as_view(), name='visit'),

    url(r'^[^/]+/[^/]+/(?P<landing_page_key>\w+)/[^/]+/$',
        views.LandingView.as_view(), name='landing-page-view'),
    url(r'^[^/]+/[^/]+/(?P<landing_page_key>\w+)/[^/]+'
        r'/(?P<modifier>(photo|recipient|shared))/$',
        views.LandingView.as_view(), name='landing-page-view-modifier'),

    # New landing page URLs
    url(r'^.+/(?P<landing_page_key>\w+)/(?P<modifier>'
        r'(photo|recipient|shared))/$',
        views.LandingView.as_view(), name='landing-page-view-modifier'),
    url(r'^.+/(?P<landing_page_key>\w+)/$', views.LandingView.as_view(),
        name='landing-page-view-new'),
)
