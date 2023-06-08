from django.conf.urls import patterns, url, include
from rest_framework import routers
from clients.api import (
    CampaignViewSet, ContactViewSet, PackageViewSet, EventViewSet,
    CompanyView, help_view,
    PackageImageViewSet, PackageCompleteView)
from live.api import MontageView, WidgetPackageView

router = routers.DefaultRouter()

router.register(r'campaigns', CampaignViewSet)
router.register(r'contacts', ContactViewSet)
router.register(r'packages', PackageViewSet)
router.register(r'packageimage', PackageImageViewSet)
router.register(r'events', EventViewSet)


urlpatterns = patterns(
    '',
    url(r'^auth/', include('djoser.urls')),
    url(r'^company/', CompanyView.as_view(), name='company'),
    url(r'^package/(?P<pk>[\d]+)/complete/$', PackageCompleteView.as_view(),
        name='packagecomplete'),
    url(r'^live/montage/(?P<pk>[\w_-]+)/$', MontageView.as_view(),
        name='montage'),
    url(r'^live/packages/(?P<pk>[\w_-]+)/$', WidgetPackageView.as_view(),
        name='packagewidget'),
    url(r'^help/', help_view, name='help'),
    url(r'^', include(router.urls)),
)
