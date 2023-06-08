import logging
from .models import Report, Schedule, ReportForm

from datetime import date
from generic.decorators import allow_tags, short_description
from feincms.admin.item_editor import ItemEditor

from django.utils.html import escape
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib import admin
from django.contrib import messages
from django.contrib.admin.options import add_preserved_filters
from django.db.models import Prefetch, F
from django.shortcuts import get_object_or_404, render_to_response
from django.conf.urls import patterns, url
from django.conf import settings

from clients.filters import CompanyFilter
from clients.models import Contact
from .forms import ContactForm, ScheduleForm


logger = logging.getLogger(__name__)


class Mixin(admin.ModelAdmin):
    def response_change(self, request, obj):
        """If generating, we do not go to Schedules."""

        opts = self.model._meta
        preserved_filters = self.get_preserved_filters(request)

        if {'_generate', '_send'} & set(request.POST.keys()):
            redirect_url = request.path
            redirect_url = add_preserved_filters(
                {'preserved_filters': preserved_filters, 'opts': opts},
                redirect_url
            )
            return HttpResponseRedirect(redirect_url)

        else:
            return super(Mixin, self).response_change(request, obj)

    @allow_tags
    def send_to(self, obj):
        return '<br/>'.join(escape(str(c)) for c in obj.contact_list())

    class Media:
        js = ('reporting/add_contact.js', )


@short_description('Update selected reports')
def generate(modeladmin, request, queryset):
    for report in queryset:
        Report.generate.delay(report)


@short_description('Deliver selected reports by email')
def deliver(modeladmin, request, queryset):
    for report in queryset:
        Report.send.delay(report)


class ReportAdmin(Mixin, admin.ModelAdmin):
    form = ContactForm
    filter_horizontal = ('contacts', )
    list_display = (
        'title', 'state', 'campaigns', 'date_created', 'send_to',
        'preview_link'
    )
    list_filter = (
        'state', CompanyFilter, 'campaigns', 'form', 'date_created',
        'is_mailed'
    )
    search_fields = (
        'title', 'body', 'company__name', 'form__name', 'form__title'
    )
    readonly_fields = (
        'date_created', 'title', 'preview_link', 'is_mailed', 'send_to',
        'state', 'status'
    )
    actions = [generate, deliver]

    fieldsets = (
        (None, {'fields': ('company', 'campaigns', 'form', 'status')}),
        ('Dates', {'fields': ('date_created', 'date_from', 'date_to')}),
        (
            'Delivery',
            {'fields': ('contacts', 'more_contacts', 'message', 'is_mailed')}
        ),
        ('Contents', {'fields': (('title', 'preview_link'))}),
    )

    def get_queryset(self, request):
        qs = super(ReportAdmin, self).get_queryset(request)
        qs = qs.prefetch_related(
            Prefetch(
                'contacts',
                queryset=Contact.objects.filter(
                        company_id=F('company_id'),
                        is_active=True,
                        type='manager',
                    ).exclude(
                        email='',
                    ),
                to_attr='prefetch_contacts',
            ),
        )
        return qs

    def status(self, obj):
        assert isinstance(obj, Report)

        if obj.state != 'error':
            return dict(Report.STATES)[obj.state]

        else:
            return 'Error (%s)' % obj.error()

    def get_urls(self):
        """Additional views."""

        return patterns(
            '',
            url(r'^(?P<instance_id>\d+)/html/$', self.html,
                name='report-preview-html'
                ),
            url(r'^(?P<instance_id>\d+)/pdf/$', self.pdf,
                name='report-preview-pdf'
                ),
        ) + super(ReportAdmin, self).get_urls()

    def save_model(self, request, obj, form, change):
        assert isinstance(obj, Report)

        if not obj.is_available():
            messages.add_message(
                request, messages.WARNING,
                'Cannot process the report "%s" because it is already '
                'in processing.' % obj
            )

        else:
            super(ReportAdmin, self).save_model(request, obj, form, change)

            if '_send' in request.POST:
                try:
                    obj.send()
                except Exception as exc:
                    messages.add_message(request, messages.ERROR, str(exc))

                    if settings.DEBUG:
                        raise
                    else:
                        logger.error(str(exc))
                else:
                    messages.add_message(
                        request, messages.INFO, 'Report email was sent.'
                    )

            else:
                Report.generate.delay(obj)

    def html(self, request, instance_id):
        """HTML report"""

        # form
        instance = get_object_or_404(Report, id=int(instance_id))

        if 'dynamic' in request.GET.keys():
            content = instance.render(render_pdf=False)[1]
        else:
            if instance.state == 'generation':  # Yeah! Warn about it.
                return render_to_response('reporting/report_loading.html', {
                    'generating': True,
                })

            content = instance.body

        try:
            return HttpResponse(content)

        except Exception as exc:
            if settings.DEBUG:
                raise
            else:
                logger.error(str(exc))
            return HttpResponse(
                'An error occured: <strong>%s</strong>' % str(exc)
            )

    def pdf(self, request, instance_id):
        """PDF report"""

        instance = get_object_or_404(Report, id=int(instance_id))

        if 'dynamic' in request.GET.keys():
            content = instance.render()[1]

            pdf = instance.render_pdf(content)
        else:
            # Is the thing generating right now?
            if instance.state == 'generation':  # Yeah! Warn about it.
                return render_to_response('reporting/report_loading.html', {
                    'generating': True,
                })

            # No, it is not, so we can try accessing the PDF.
            try:
                pdf = open(instance.pdf_filename(), 'rb')
            except IOError:
                # Hey, no PDF found! It is a problem actually.
                # Let's generate it, then.
                Report.generate.delay(instance)
                return render_to_response('reporting/report_loading.html')

        return HttpResponse(pdf, content_type='application/pdf')


class ReportInline(admin.TabularInline):
    model = Report
    extra = 0

    fields = readonly_fields = (
        'title', 'state', 'form', 'company', 'campaigns', 'date_created',
        'is_mailed', 'preview_link', 'edit'
    )

    @allow_tags
    def edit(self, obj):
        if obj:
            return '<a href="/reporting/report/%s/">Edit</a>' % obj.id

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False


class ScheduleAdmin(Mixin, admin.ModelAdmin):
    filter_horizontal = ('contacts', )
    form = ScheduleForm
    inlines = (ReportInline, )

    list_display = (
        'id', 'form', 'company', 'campaigns', 'pattern', 'period', 'send',
        'is_active', 'send_to'
    )
    list_filter = (
        'form', CompanyFilter, 'campaigns', 'pattern', 'period',
        'is_active', 'send'
    )

    fieldsets = (
        (None, {'fields': ('company', 'campaigns', 'form', 'period')}),
        ('Delivery', {'fields': ('is_active', 'pattern')}),
        ('To', {'fields': ('send', 'contacts', 'more_contacts', 'message')})
    )

    def save_model(self, request, obj, form, change):
        super(ScheduleAdmin, self).save_model(request, obj, form, change)

        if '_generate' in request.POST:
            try:
                instance = obj.attempt(date.today(), force=True)
            except Exception as exc:
                msg = 'There was an unexpected error generating a report ' \
                      'from schedule #%s: %s. The developers have been ' \
                      'notified.' % (obj.id, str(exc))
                messages.add_message(request, messages.ERROR, msg)
                if settings.DEBUG:
                    raise
                else:
                    logger.error(msg)

            else:
                if instance and instance.state == 'generated':
                    messages.add_message(
                        request, messages.INFO,
                        'A new report was created: %s' % instance
                    )

                elif instance and instance.state == 'error':
                    # msg = 'For some weird reason, nothing was created.'
                    messages.add_message(
                        request, messages.ERROR,
                        'There was an unexpected error generating a report '
                        'from schedule #%s: %s. The developers have been '
                        'notified.' % (obj.id, instance.error)
                    )


admin.site.register(Schedule, ScheduleAdmin)
admin.site.register(Report, ReportAdmin)
admin.site.register(ReportForm, ItemEditor)
