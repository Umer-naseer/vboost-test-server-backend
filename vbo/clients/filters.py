from .models import Company

from django.contrib import admin
from django.http import Http404


class CompanyFilter(admin.SimpleListFilter):
    """Filter objects by company.

    Can be applied to any model which has a 'company' ForeignKey."""

    title = 'company'
    parameter_name = 'company'
    template = 'admin/company_filter.html'

    def lookups(self, request, model_admin):
        'Returns a list of companies and their IDs to filter by.'

        queryset = Company.objects.only('id', 'name')\
            .order_by('name')\
            .iterator()

        return tuple((str(company.id), company.name) for company in queryset)

    def queryset(self, request, queryset):
        'Filter roles'

        # Raw company ID from URL
        cid = self.value()
        if cid:
            # Translate to int
            try:
                cid = int(cid)
            except:
                raise Http404()

            # Get the list of objects by company with an overridable function
            return self.restricted_queryset(queryset, cid)

    def restricted_queryset(self, queryset, company_id):
        return queryset.filter(company=company_id).distinct()


class InlineFilter(admin.AllValuesFieldListFilter):
    # template = 'inline-filter.html'
    pass
