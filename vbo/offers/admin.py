from .models import Offer, Submission

from templates.models import Template
from django.contrib import admin


class OfferInline(admin.StackedInline):
    model = Offer
    exclude = ['template']
    extra = 0

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        if db_field.name.endswith('template'):
            kwargs['queryset'] = Template.objects.filter(type={
                'template': 'offer',
                'email_template': 'offer-email',
                'email_notification_template': 'offer-notification-email',
                'redeem_template': 'offer-redeem',
            }[db_field.name])

        return super(OfferInline, self).formfield_for_foreignkey(
            db_field, request, **kwargs
        )


class SubmissionAdmin(admin.ModelAdmin):
    readonly_fields = ['key', 'last_redeem_time', 'created_time']
    raw_id_fields = ['package']
    list_display = [
        'name', 'mobile', 'email', 'appointment_date', 'zipcode',
        'code', 'created_time'
    ]

    list_filter = ['offer__target_audience', 'package__campaign']
    search_fields = ['name', 'email', 'mobile', 'zipcode', 'code', 'key']

    fieldsets = [
        (None, {'fields': ['package', 'offer']}),
        (
            'Recipient',
            {'fields': [
                'name', 'mobile', 'email', 'appointment_date',
                'zipcode', 'code'
            ]}
        ),
        ('Meta', {'fields': ['key', 'last_redeem_time', 'created_time']}),
    ]


admin.site.register(Submission, SubmissionAdmin)
