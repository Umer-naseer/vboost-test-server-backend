from sorl.thumbnail.admin import AdminImageMixin
from rest_framework.authtoken.models import Token
from generic.decorators import allow_tags, short_description

from generic.admin import Illustrated
from django.contrib.admin import site
from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin, GroupAdmin

from clients import models, forms
from .filters import CompanyFilter
from live.admin import LinksInline
from offers.admin import OfferInline
from templates.models import Template


class UserProfileInline(admin.StackedInline):
    model = models.UserProfile
    can_delete = False
    verbose_name_plural = 'profile'


class TokenInline(admin.StackedInline):
    model = Token
    fields = ['key', 'created']
    readonly_fields = ['created']


# Define a new User admin
class UserAdmin(DefaultUserAdmin):
    inlines = [UserProfileInline, TokenInline]

    def add_view(self, *args, **kwargs):
        self.inlines = []
        return super(UserAdmin, self).add_view(*args, **kwargs)

    def change_view(self, *args, **kwargs):
        self.inlines = [UserProfileInline, TokenInline]
        return super(UserAdmin, self).change_view(*args, **kwargs)


class UserProxy(User):
    class Meta:
        proxy = True

class UserProxyAdmin(DefaultUserAdmin):
    inlines = [UserProfileInline, TokenInline]
    list_display = ('username', 'email', 'first_name', 'last_name', 'company', 'is_active')
    actions = ["set_active", "set_deactive"]
    list_filter = ['is_active']
    
    def company(self, instance):
        if instance.profile:
            if instance.profile.company:
                return instance.profile.company.name
        return ''

    def add_view(self, *args, **kwargs):
        self.inlines = []
        return super(UserAdmin, self).add_view(*args, **kwargs)

    def change_view(self, *args, **kwargs):
        self.inlines = [UserProfileInline, TokenInline]
        return super(UserAdmin, self).change_view(*args, **kwargs)

    def set_active(self, request, queryset):
        for query in queryset:
            query.is_active = True
            query.save()

    set_active.short_description = "Set user active"

    def set_deactive(self, request, queryset):
        for query in queryset:
            query.is_active = False
            query.save()

    set_deactive.short_description = "Set user deactive"


site.unregister(User)
site.unregister(Group)
site.register(User, UserAdmin)
site.register(Group, GroupAdmin)
site.register(UserProxy, UserProxyAdmin)


class CompanyUserInline(admin.TabularInline):
    model = models.UserProfile
    extra = 0


class CompanyImageInline(admin.TabularInline):
    model = models.CompanyImage
    extra = 0


class CompanyAdmin(AdminImageMixin, admin.ModelAdmin):
    """Companies administration interface."""

    list_display = ('name', 'status', 'key', 'default_email', 'company_email')
    search_fields = (
        'name', 'key', 'slug', 'keywords1', 'keywords2',
        'default_email', 'company_email'
    )

    list_filter = ['status']
    inlines = [CompanyUserInline, LinksInline, CompanyImageInline]

    readonly_fields = (
        'dealer_widget_embed_code',
        'dealer_widget_embed_preview',
    )
    fieldsets = (
        (None, {'fields': (
            'name', 'status', 'key', 'slug', 'website', 'use_cdk',
            'dealer_widget_embed_code', 'dealer_widget_embed_preview',
        )}),
        ('SEO keywords', {'fields': ('keywords1', 'keywords2')}),
        (
            'Images',
            {
                'fields': (
                    'logo', 'mobile_logo', 'watermark_logo', 'about_image',
                )
            }
        ),
        ('Contacts', {
            'classes': ('collapse', ),
            'fields': (
                'default_company_name', 'default_display_name',
                'company_email', 'default_email', 'default_phone',
                'forward_to_contacts'
            )
        }),
        ('Bio', {'classes': ('collapse', ), 'fields': ('bio',)}),
        ('Location', {'classes': ('collapse', ),
                      'fields': ('address', 'address2', 'city', 'state',
                                 'zipcode', 'country'
                                 )
                      }
         ),
        ('Mobile app configuration', {
            'classes': ['collapse'],
            'fields': ['terms', 'filter_contacts']
        }),
        ('Device', {
            'classes': ('collapse', ),
            'fields': (
                'device_username', 'device_password', 'device_name',
                'device_serial_number', 'device_phone_number',
                'guided_access_password', 'logo_received', 'meid'
            )
        }),
    )

    def changelist_view(self, request, extra_context=None):
        if not 'status__exact' in request.GET:
            q = request.GET.copy()
            q['status__exact'] = 'active'
            request.GET = q
            request.META['QUERY_STRING'] = request.GET.urlencode()
        return super(CompanyAdmin, self).changelist_view(
            request, extra_context=extra_context
        )

    def save_model(self, request, obj, form, change):
        """If a company is marked inactive, all of its campaigns
        are marked inactive too."""

        if obj.status == 'inactive':
            obj.campaign_set.update(
                is_active=False
            )

        return super(CompanyAdmin, self).save_model(request, obj, form, change)


class CampaignImageInline(admin.TabularInline, Illustrated):
    model = models.CampaignImage

    fields = ('name', 'thumbnail', 'image', )
    readonly_fields = ('thumbnail', )

    extra = 0

    def thumbnail(self, obj):
        """Create a thumbnail"""
        return self._thumbnail(obj.image)


class CampaignMediaInline(admin.TabularInline):
    model = models.CampaignMedia
    fields = ('name', 'file', )
    extra = 0


class CampaignTextInline(admin.TabularInline):
    model = models.CampaignText
    fields = ('name', 'value', )
    extra = 0


class CampaignAdmin(Illustrated, admin.ModelAdmin):
    form = forms.CampaignForm
    list_display = (
        'name', 'company_name', 'campaign_type', 'key',
        'default_email', 'is_active'
    )
    list_filter = (CompanyFilter, 'type', 'is_active')
    readonly_fields = ('logo_image',)
    inlines = [
        CampaignImageInline, CampaignMediaInline, CampaignTextInline,
        OfferInline
    ]
    search_fields = (
        'name', 'default_email', 'default_phone', 'default_subject'
    )
    actions = None

    fieldsets = (
        (None, {'fields': (
            'name', 'key', 'company', 'type', 'is_active',
            'google_analytics', 'details', 'vin_solutions_email')
        }),
        ('About', {'fields': ('logo_image', 'logo', )}),
        ('Templates', {'fields': (
            'video_template',
        )}),
        ('Landing page settings', {
            'fields': (
                'landing_title', 'photo_title',
                'about_title', 'about_subtitle', 'about_image', 'about_text',
                'sharing_title', 'sharing_description',
            ),
            'classes': ['collapse']
        }),
        ('Email settings', {'classes': ('collapse', ), 'fields': (
            'use_contact_info',
            'default_from', 'default_email', 'default_phone',
            'email_greeting', 'default_subject',
            'notification_email', 'notification_email_template',
            'email_managers'
        )}),
        (
            'Workflow',
            {'classes': ('collapse', ), 'fields': ('approval_instructions',)}
        ),
        ('Tracking',
            {
                'classes': ('collapse',),
                'fields': (
                    'tracking_username',
                    'tracking_password', 'tracking_link'
                )
            }
         ),
        (
            'Streaming',
            {'classes': ('collapse', ),
             'fields': ('streaming_enable', 'streaming_username',
                        'streaming_password', 'streaming_key',
                        'streaming_secret')
             }
        ),
        (
            'Custom',
            {
                'classes': ('collapse', ),
                'fields': (
                    'custom_download_link', 'custom_email_account',
                    'custom_email_password'
                )
            }
        ),
        (
            'Email provider',
            {
                'classes': ('collapse', ),
                'fields': (
                    'email_provider_username',
                    'email_provider_password',
                    'email_provider_reply_email'
                )
            }
        ),
        (
            'Etc',
            {
                'classes': ('collapse', ),
                'fields': ('address_bar_sharing', 'template_version')
            }
        ),
    )

    @allow_tags
    @short_description('Company')
    def company_name(self, obj):
        return obj.company.name

    @allow_tags
    @short_description('Type')
    def campaign_type(self, obj):
        return obj.type.name

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        if db_field.name == 'company':
            kwargs['queryset'] = models.Company.objects.all().order_by('name')

        elif db_field.name.endswith('template'):
            try:
                kwargs['queryset'] = Template.objects.filter(type={
                   'notification_email_template': 'package-notification-email',
                }[db_field.name])
            except KeyError:
                pass

        return super(CampaignAdmin, self).\
            formfield_for_foreignkey(db_field, request, **kwargs)

    def logo_image(self, obj):
        """Logo"""

        return self._thumbnail(obj.logo, 300)

    def changelist_view(self, request, extra_context=None):
        if not 'is_active__exact' in request.GET:
            q = request.GET.copy()
            q['is_active__exact'] = '1'
            request.GET = q
            request.META['QUERY_STRING'] = request.GET.urlencode()

        return super(CampaignAdmin, self).\
            changelist_view(request, extra_context=extra_context)

    class Media:
        js = ('js/admin/campaign.js',)


class ContactAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'is_active', 'company', 'title', 'type', 'email',
        'phone', 'businesscard_photo', 'photo'
    )
    list_filter = (CompanyFilter, 'is_active', 'type')
    search_fields = ('name', 'email')

    fieldsets = (
        (None, {'fields': ('name', 'title', 'type', 'company', 'is_active')}),
        (
            'Contact',
            {'fields': ('photo', 'businesscard_photo', 'email', 'phone')}
        ),
    )

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        if db_field.name == 'company':
            kwargs['queryset'] = models.Company.objects.all().order_by('name')

        return super(ContactAdmin, self).\
            formfield_for_foreignkey(db_field, request, **kwargs)


# Register models
registrations = (
    (models.Company, CompanyAdmin),
    (models.Campaign, CampaignAdmin),
    (models.Contact, ContactAdmin),
)

for model, admin_class in registrations:
    site.register(model, admin_class)
