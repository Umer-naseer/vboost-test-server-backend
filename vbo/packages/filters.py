from django.contrib import admin
from clients.models import PACKAGE_STATUS_VALUES


class StatusFilter(admin.SimpleListFilter):
    """Filter packages by status"""

    title = 'status'
    parameter_name = 'status'
    template = 'admin/company_filter.html'

    def lookups(self, request, model_admin):
        """Returns a list of companies and their IDs to filter by."""

        return PACKAGE_STATUS_VALUES

    def queryset(self, request, queryset):
        """Filter"""

        if self.value():
            return queryset.filter(status=self.value())
        else:
            return queryset
