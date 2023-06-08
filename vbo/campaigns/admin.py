from .models import CampaignType, CampaignTypeImage

from adminsortable.admin import SortableTabularInline, SortableAdmin
from sorl.thumbnail.admin import AdminImageMixin

from django.contrib import admin


class CampaignTypeImageInline(SortableTabularInline):
    model = CampaignTypeImage
    fields = ['title', 'name']
    extra = 0


@admin.register(CampaignType)
class CampaignTypeAdmin(AdminImageMixin, SortableAdmin):
    inlines = [CampaignTypeImageInline]
    list_display = ['name', 'category', 'order']

    fieldsets = [
        (None, {'fields': ['name', 'category']}),
        ('Creative content', {'fields': ['mask']}),
        ('Templates', {'fields': [
            'landing_template',
            'sms_template',
            'email_template',
            'video_template',
        ]}),
        ('Mobile app', {'fields': ['color']}),
        ('Photo taking', {'fields': [
            'min_count', 'max_count', 'default_count'
        ]})
    ]
