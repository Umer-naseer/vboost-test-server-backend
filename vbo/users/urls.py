from django.conf.urls import patterns, url

from . import views

urlpatterns = patterns(
    url(r'^$', views.UsersViews.as_view(), name="users"),
)
