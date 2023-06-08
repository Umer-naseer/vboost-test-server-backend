from .tasks import production, deliver

from datetime import timedelta

from import_export import resources
from import_export.admin import ImportExportActionModelAdmin

from sorl.thumbnail import get_thumbnail

from django.contrib import messages
from django.contrib.admin import site
from django.contrib.admin.views.main import ChangeList
from django.db.models import Prefetch
from django.utils import timezone

from daterange_filter.filter import DateRangeFilter
from generic.decorators import allow_tags, short_description
from django.core.urlresolvers import reverse

from .filters import StatusFilter
from clients.filters import CompanyFilter
from .models import Inspect
from clients.models import Company, Campaign, Contact, PackageImage
from gallery.models import Mask


PACKAGES_RECENT = 365  # Days


class InspectResource(resources.ModelResource):
    class Meta:
        model = Inspect
        fields = ['contact', 'recipient_email']


class InspectChangeList(ChangeList):
    def __init__(self, *args, **kwargs):
        super(InspectChangeList, self).__init__(*args, **kwargs)

        self.title = "Packages"


@short_description('Produce selected packages')
def produce(modeladmin, request, queryset):
    """Produce selected packages."""

    queryset.update(session=None)

    for p in queryset:
        production.delay(p.id)

    messages.info(request, 'Production process initiated.')


@short_description('Deliver selected packages')
def deliver(modeladmin, request, queryset):
    """Deliver selected packages"""
    queryset.update(session=None)

    for p in queryset:
        deliver.delay(p.id)

    messages.info(request, 'Delivery process initiated.')


@short_description('Skip selected packages')
def skip(modeladmin, request, queryset):
    """Deliver selected packages"""
    queryset.update(status='skipped')

    messages.info(request, 'Packages are skipped.')


@short_description('Void selected packages')
def void(modeladmin, request, queryset):
    """Deliver selected packages"""
    queryset.update(status='void')

    messages.info(request, 'Packages are void.')


class InspectAdmin(ImportExportActionModelAdmin):
    actions = (produce, deliver, skip, void)
    resource_class = InspectResource

    list_display = (
        'package', 'campaign_link', 'company_link', 'created_time',
        'current_status', 'preview', 'user_agent',
        'email_views', 'landing_views', 'page_views', 'video_views', 'shares',
        'edit',
    )
    search_fields = [
        'company__name', 'campaign__name', 'contact__name', 'status',
        'recipient_name', 'recipient_email', 'recipient_phone',
        'landing_page_key'
    ]

    list_filter = (
        CompanyFilter, 'campaign__type', StatusFilter,
        # FIXME: Two DateRangeFilters on the same page do not work
        ('created_time', DateRangeFilter),
        'last_mailed', 'recipient_permission', 'user_agent'
    )

    list_per_page = 20
    show_full_result_count = False

    def get_queryset(self, request):
        qs = super(InspectAdmin, self).get_queryset(request)
        min_date = timezone.now() - timedelta(days=PACKAGES_RECENT)
        # try:
        #     min_id = qs.filter(
        #         created_time__gte=min_date
        #     ).values_list('id', flat=True)[0]
        # except IndexError:
        #     pass
        # else:
        #     qs = qs.filter(id__gte=min_id)
        return qs.prefetch_related(
            Prefetch(
                'campaign',
                queryset=Campaign.objects.only('name', 'type_id'),
            ),
            Prefetch(
                'company',
                queryset=Company.objects.only('name'),
            ),
            Prefetch(
                'contact',
                queryset=Contact.objects.only('name', 'email'),
            ),
            Prefetch(
                'campaign__type__mask',
                queryset=Mask.objects.only('image'),
            ),
            Prefetch(
                'images',
                queryset=PackageImage.objects.filter(is_thumbnail=True),
                to_attr='prefetch_thumbnails',
            ),
        )

    @allow_tags
    @short_description('Company')
    def company_link(self, obj):
        if obj.company_id:
            return '<a target="_blank" href="{}">{}</a>'.format(
                reverse('admin:clients_company_change',
                        args=(obj.company_id, )),
                obj.company.name
            )

    @allow_tags
    @short_description('Campaign')
    def campaign_link(self, obj):
        if obj.campaign_id:
            link = '<a target="_blank" href="{}">{}</a>'.format(
                reverse('admin:clients_campaign_change',
                        args=(obj.campaign_id, )),
                obj.campaign.name
            )
            return link

    @allow_tags
    def package_images(self, obj):
        def image(obj):
            try:
                thumbnail = get_thumbnail(obj.absolute_path(), "100")
                classes = (
                    'mini',
                    'thumbnail' if obj.is_thumbnail else '',
                    'skipped' if obj.is_skipped else '',
                )
                return '<a target="_blank" class="%s" href="%s">' \
                       '<img src="%s" alt="" /></a>' % (
                            ' '.join(classes),
                            str(obj),
                            thumbnail.url
                       )
            except:
                return ''

        return ''.join(map(image, obj.images.all().order_by(
            'inline_ordering_position')))

    @allow_tags
    def package(self, obj):
        def link(obj):

            if obj:
                return '<a href="?%s=%s">%s</a>' % (
                    obj.__class__.__name__.lower(),
                    obj.pk,
                    obj.name
                )
            else:
                return ''

        return '<br/>'.join((
            'By %s' % link(obj.contact),
            'For %s' % (obj.recipient_email or obj.recipient_phone),
        ))

    @allow_tags
    def preview(self, obj):
        """Link to the landing page."""

        try:
            return '<a target="_blank" href="{}"><img src="{}"/></a>'.format(
                obj.get_landing_page_url(),
                get_thumbnail(
                    obj.cover.get_masked_thumbnail(),
                    '100'
                ).url
            ) if obj.landing_page_url else None
        except:
            return None

    @allow_tags
    def edit(self, obj):
        return '<a href="/clients/package/%s/">Edit</a>' % obj.pk

    def __init__(self, *args, **kwargs):
        super(InspectAdmin, self).__init__(*args, **kwargs)
        self.list_display_links = (None,)

    def get_changelist(self, request, **kwargs):
        return InspectChangeList

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return True

    def has_change_permission(self, request, obj=None):
        """Inspect equals to Package. Here we go."""

        return request.user.has_perm('clients.change_package')

    class Media:
        js = (
            'admin/js/jquery.min.js',
            'datepick/jquery.datepick.js',
        )
        css = {
            'all': (
                'datepick/jquery.datepick.css',
                'datepick/smoothness.datepick.css',
            )
        }


site.register(Inspect, InspectAdmin)
