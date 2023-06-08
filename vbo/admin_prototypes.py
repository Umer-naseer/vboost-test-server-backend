"""Administration utilities."""

from django.contrib import admin
from django.contrib.auth.models import Permission


def get_permission(app_label, codename):
    'Resolve app_label and codename to Permission object'
    return Permission.objects.get(
        content_type__app_label=app_label, codename=codename
    )


# List of applications which permissions are not shown to non-super-users
EXCLUDE_PERMISSIONS_OF_APPS = (
    'admin',
    'auth',
    'contenttypes',
    'sites',
    'sessions',
)


class ProtectedAdmin(admin.ModelAdmin):
    """Protected administration class."""

    def queryset(self, request):
        """Filter queryset by user permissions"""

        opts = self.opts

        # Default QuerySet
        qs = super(ProtectedAdmin, self).queryset(request)

        # We don't need any filtering for superuser.
        if request.user.is_superuser:
            return qs

        # And for others - we do need.
        # Get the change_MODEL permission
        perm = get_permission(opts.app_label, opts.get_change_permission())

        return self.restricted_queryset(qs, request, perm)

    # O_o Don't really remember what the following two methods
    # are needed for...
    def has_change_permission(self, request, obj=None):
        """Does this user have change perm?"""
        opts = self.opts
        if opts.auto_created:
            # The model was auto-created as intermediary for a
            # ManyToMany-relationship, find the target model
            for field in opts.fields:
                if field.rel and field.rel.to != self.parent_model:
                    opts = field.rel.to._meta
                    break

        return request.user.has_perm(
            opts.app_label + '.' + opts.get_change_permission(), obj)

    def has_delete_permission(self, request, obj=None):
        """And delete one?"""
        if self.opts.auto_created:
            # We're checking the rights to an auto-created intermediate model,
            # which doesn't have its own individual permissions. The user needs
            # to have the change permission for the related model in order to
            # be able to do anything with the intermediate model.
            return self.has_change_permission(request, obj)

        return request.user.has_perm(
            self.opts.app_label + '.' + self.opts.get_delete_permission(), obj)


class CompanyBoundAdmin(ProtectedAdmin):
    """Administration interface for company-bound models."""

    def restricted_queryset(self, queryset, request, perm):
        return queryset.filter(  # Show an object if and only if
            # It is linked with a Company which is linked with current User
            company__userrole__user=request.user,
            # With a Role which includes the change_OBJECT permission
            company__userrole__role__permissions=perm
        ).distinct()
