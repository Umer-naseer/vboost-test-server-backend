from django.contrib import admin
from clients.models import Company
from .models import UnsubscribedEmail, Email, Event


class UnsubscribedEmailAdmin(admin.ModelAdmin):
    list_display = ('email', 'company', 'time')
    readonly_fields = ('time', )

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        if db_field.name == 'company':
            kwargs['queryset'] = Company.objects.all().order_by('name')

        return super(UnsubscribedEmailAdmin, self)\
            .formfield_for_foreignkey(db_field, request, **kwargs)


class EventInline(admin.TabularInline):
    model = Event
    fields = readonly_fields = ['type', 'time']
    extra = 0

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class EmailAdmin(admin.ModelAdmin):
    list_display    = ['subject', 'from_email', 'to_emails', 'type',
                       'status', 'views']
    readonly_fields = ['created_time', 'package', 'status', 'key', 'views']
    list_filter     = ['type', 'package__campaign', 'status']
    search_fields   = ['subject', 'from_emails', 'to_emails', 'content', 'key']
    inlines = [EventInline]
    save_on_top = True

    fieldsets = [
        (None, {'fields': ['package', 'type', 'status']}),
        ('Addresses', {'fields': ['to_emails', 'from_email']}),
        ('Content', {'fields': ['subject', 'content']}),
        ('Meta', {'fields': ['created_time', 'key'], 'classes': ['collapse']})
    ]

    def views(self, obj):
        return obj.events.filter(type='open').count()

    def _has_add_permission(self, request):
        return False


admin.site.register(UnsubscribedEmail, UnsubscribedEmailAdmin)
admin.site.register(Email, EmailAdmin)
