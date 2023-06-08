"""Generic admin classes."""

import re

from sorl.thumbnail import get_thumbnail
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.admin.views.main import ChangeList
from django.utils.safestring import mark_safe
from django.db.models import Q


class Illustrated(object):
    """Mixin which provides basic functions for image and thumbnail fields."""

    def _thumbnail(self, image, width=190):
        """Generate a thumbnail of specified width
        from the specified ImageField image."""

        try:
            thumbnail = get_thumbnail(image.file, str(width))
            return mark_safe('<img src="%s" alt="" />' % thumbnail.url)
        except:
            pass

    def _image(self, image):
        """Show the image."""

        try:
            return mark_safe('<img src="%s" alt="" />' % image.url)
        except:
            pass


class ConcurrentChangeList(ChangeList):
    def get_query_set(self, request):
        queryset = super(ConcurrentChangeList, self).get_query_set(request)

        # Filter by approver and last access time
        latest_access_time = \
            datetime.now() - timedelta(seconds=settings.LOCK_TIME)
        queryset = queryset.filter(
            Q(approver=None) | \
            Q(approver=request.user) | \
            Q(access_time__lt=latest_access_time)
        )

        # If form data is supplied, show only the packages which appear
        # in the forms
        # In other words, adjust queryset to formsets
        if request.POST:
            ids = [int(request.POST[field]) for field in request.POST.keys()
                   if re.match(r'^form-\d+-id$', field)
            ]
            return queryset.filter(id__in=ids)
        else:
            return queryset

    def get_results(self, request):
        """Update approver and access time data."""

        results = super(ConcurrentChangeList, self).get_results(request)

        ids = [item.id for item in self.result_list]
        if ids:
            self.queryset.filter(id__in=ids).update(
                approver=request.user,
                access_time=datetime.now()
            )

        return results
