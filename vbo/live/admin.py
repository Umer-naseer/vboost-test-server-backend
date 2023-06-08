from django.contrib import admin
from django import forms

from clients.models import Campaign
from live import models
from adminsortable2.admin import SortableInlineAdminMixin


class LinksInlineForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(LinksInlineForm, self).__init__(*args, **kwargs)
        # raise Exception('!')
        self.fields['campaign'].queryset = Campaign.objects.none() if (
            self.instance.company_id is None
        ) else Campaign.objects.filter(
            company=self.instance.company
        )

    class Meta:
        model = models.Link
        fields = '__all__'


class LinksInline(SortableInlineAdminMixin, admin.TabularInline):
    model = models.Link
    extra = 0
    form = LinksInlineForm


class MontageVideoAdmin(admin.ModelAdmin):
    list_filter = ['company', 'is_visible', ]
    list_display = ['name', 'company', 'date', 'is_visible', 'video']


admin.site.register(models.MontageVideo, MontageVideoAdmin)
