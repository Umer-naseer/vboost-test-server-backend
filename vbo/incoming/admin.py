from inline_ordering.admin import OrderableStackedInline
from concurrency.admin import ConcurrencyListEditableMixin
from generic.admin import Illustrated, ConcurrentChangeList
from generic.decorators import allow_tags
from generic.forms import ConcurrentFormSet

from django import forms
from django.conf import settings
from django.conf.urls import patterns, url
from django.contrib.admin.options import capfirst, force_text
from django.contrib.admin.options import add_preserved_filters, \
    HttpResponseRedirect
from django.contrib import admin, messages
from django.contrib.admin import site, ModelAdmin
from django.core.exceptions import PermissionDenied
from django.forms.util import ValidationError
from django.forms.models import BaseModelFormSet, ModelForm, \
    modelformset_factory
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render_to_response, Http404
from django.template import RequestContext
from django.template.response import TemplateResponse

from clients import models


INLINE_ORDERING_JS = getattr(settings,
                             'INLINE_ORDERING_JS', 'inline_ordering.js')

ORDERING_FIELD_NAME = 'inline_ordering_position'


class BaseImageFormSet(BaseModelFormSet):
    """Base for imageformset."""

    def clean(self):
        if any(self.errors) or not self.approved:
            return

        has_thumbnail = False
        approved_count = 0
        for form in self.forms:
            is_skipped = form.cleaned_data.get('is_skipped', False)
            if not is_skipped:
                approved_count += 1

            if form.cleaned_data.get('is_thumbnail', False):
                if not has_thumbnail:
                    # We actually have at least one thumbnail.
                    has_thumbnail = True

                else:  # We have more than none which is impossible.
                    raise ValidationError(
                        "There cannot be more than one thumbnail "
                        "in the package."
                    )

                if is_skipped:
                    raise ValidationError(
                        "Skipped image cannot be a thumbnail."
                    )

        if not has_thumbnail:  # We have no thumbnails selected
            raise ValidationError("Please select a thumbnail.")

            # if not (1 <= approved_count <= settings.IMAGES_PER_PACKAGE):
            #     raise ValidationError(
            #        """A package must include from 1 to %s non-skipped images.
            #        Now, it includes %s images.""" %
            # (settings.IMAGES_PER_PACKAGE, approved_count))

    def get_ordered_forms(self):
        """
        Returns a list of form in the order specified by the incoming data.
        Raises an AttributeError if ordering is not allowed.
        """

        ordering = []
        for form in self.forms:
            ordering.append((form['inline_ordering_position'].value(), form))

        ordering.sort(key=lambda item: item[0])

        return [item[1] for item in ordering]


class ImageForm(ModelForm):
    source = forms.IntegerField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = models.PackageImage
        fields = '__all__'
        widgets = {
            'campaign': forms.HiddenInput(),
            'inline_ordering_position': forms.HiddenInput(),
            'angle': forms.HiddenInput(),
        }


ImageFormSet = modelformset_factory(
    models.PackageImage,
    formset=BaseImageFormSet,
    form=ImageForm,
    exclude=('package', 'x1', 'x2', 'y1', 'y2'),
    extra=0,
    can_order=True
)


class PackageForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(PackageForm, self).__init__(*args, **kwargs)

        # Change options and value for "status" field
        self.fields['status'].choices = (
            ('skipped', 'Skip'),
            ('void', 'Void'),
            ('approved', 'Approve'),
        )

        self.fields['status'].required = False

        instance = kwargs.get('instance', None)
        if instance and instance.status == 'produced':
            self.fields['status'].widget.attrs['disabled'] = True

    def clean(self):
        """Full package validation."""

        cleaned_data = super(PackageForm, self).clean()

        if not cleaned_data.get('status', None):
            cleaned_data['status'] = self.instance.status

        # If package is skipped or void, no validation is necessary.
        if cleaned_data['status'] != 'approved':
            return cleaned_data

        # Require some fields
        if not cleaned_data.get('campaign', None):
            self._errors['campaign'] = self.error_class([
                'This field is required.'])

        return cleaned_data

    def has_changed(self):
        """Has the formset changed?"""

        return (self.nested and self.nested.has_changed()) \
            or super(PackageForm, self).has_changed()

    class Meta:
        model = models.Package
        fields = '__all__'


class PackageFormSet(ConcurrentFormSet):
    """Formset for the Package ChangeList form."""

    def add_fields(self, form, index):
        super(PackageFormSet, self).add_fields(form, index)

        # created the nested formset
        try:
            # instance = self.get_queryset()[index]
            # instance = self.get_queryset().get(pk=form.instance.pk)
            instance = form.instance
            pk_value = instance.pk

        except IndexError:
            instance = None
            pk_value = hash(form.prefix)

        if instance and instance.status == 'erroneus':
            form.last_problem = \
                models.Package.objects.get(id=pk_value).last_error()

        # store the formset in the .nested property
        data = form.data or None

        form.nested = ImageFormSet(
            queryset=models.PackageImage.objects.filter(
                package=pk_value).order_by('inline_ordering_position'),
            prefix='IMAGES_%s' % pk_value,
            data=data
        )

    def is_valid(self):
        valid = super(PackageFormSet, self).is_valid()

        for form in self.forms:
            if hasattr(form, 'nested') and form.nested:
                imageformset = form.nested

                imageformset.data = form.data
                if form.is_bound:
                    imageformset.is_bound = True

                for imageform in imageformset:
                    imageform.data = form.data
                    if form.is_bound:
                        imageform.is_bound = True

                        # Make sure each nested formset is valid as well
                        # You need an intermediate variable here.
                        # Or validation crushes.
                imageformset.approved = (form['status'].value() == 'approved')
                imageformset_valid = imageformset.is_valid()

                if not imageformset_valid:
                    pass

                valid = valid and imageformset_valid

        return valid

    def save_all(self, commit=True):
        objects = self.save(commit=False)

        for form in set(self.initial_forms + self.saved_forms):
            for subform in form.nested:
                subform.save(commit=commit)

        if commit:
            for o in objects:
                o.save()

        else:
            self.save_m2m()


class PackageChangeList(ConcurrentChangeList):
    """Unordered ChangeList."""

    def __init__(self, request, *args, **kwargs):
        super(PackageChangeList, self).__init__(request, *args, **kwargs)

        status = request.GET['status__exact']

        self.title = {
            'pending': 'Incoming images',
            'skipped': 'Skipped images',
            'void': 'Void images',
            'erroneus': 'Errors',
            'ready': 'Awaiting video production',
            'produced': 'Produced videos',
        }.get(status, 'Images')


class PackageImageInline(OrderableStackedInline, Illustrated):
    model = models.PackageImage

    fields = ('thumbnail', 'image', 'angle', 'is_skipped', 'is_thumbnail', )
    readonly_fields = ('thumbnail', )

    extra = 0

    def thumbnail(self, obj):
        """Create a thumbnail"""

        return self._thumbnail(obj.image)


class PackageAdmin(ConcurrencyListEditableMixin, ModelAdmin):
    list_display = ('id', 'company', 'campaign', 'company_name', 'contact',
                    'recipient_email', 'status', 'edit')
    list_editable = ('company', 'campaign', 'recipient_email', 'status')
    radio_fields = {'status': admin.HORIZONTAL}
    list_display_links = ('edit', )
    readonly_fields = (
        'company', 'contact', 'campaign',
        'current_status',
        'submitted_time', 'created_time', 'last_mailed',
        'video_preview', 'video_key', 'landing_page_key', 'video_url',
        'company_name', 'company_key', 'campaign_key',
        'status',
        'email_views', 'landing_views', 'page_views', 'video_views',
        'viewed_duration', 'shares', 'visitors',
        'website_views', 'review_site_views', 'social_site_views',
        'photo_downloads',
        'offer_recipient_views', 'offer_others_views',
        'stupeflix_key', 'user_agent',
    )

    object_history_template = 'packages/events.html'

    list_filter = ('status', 'company')
    actions = None
    list_per_page = 10
    inlines = (PackageImageInline, )
    save_on_top = True

    fieldsets = (
        (None, {'fields': ('company', 'contact', 'campaign', 'current_status',
                           'landing_page_key')}),
        ('Recipient', {'fields': (
            ('recipient_name', 'recipient_email', 'recipient_phone'),
            'recipient_signature',
            'recipient_permission',
            'last_mailed')}),
        ('Video', {'fields': ('video_url', 'stupeflix_key',
                              'video_key', 'video_preview')}),
        ('Statistics', {'fields': (
            ('email_views', 'landing_views', 'page_views'),
            ('video_views', 'viewed_duration'),
            'shares',
            ('website_views', 'review_site_views', 'social_site_views'),
            ('offer_recipient_views', 'offer_others_views'),
        )}),
        ('Time', {'fields': ('created_time', 'submitted_time'),
                  'classes': ('collapse', )}),
        ('Debug info', {'classes': ('collapse', ),
                        'fields': ('company_key', 'company_name',
                                   'campaign_key', 'user_agent')})
    )

    TEMPLATE_TYPES = {
        'video': ('stupeflix_template', 'Craftsman XML code', 'text/plain'),
        'landing': ('landing_template', 'landing page', 'text/html'),
        'email': ('email_template', 'email text', 'text/html'),
    }

    def preview(self, request, id, template_type):
        """Preview video script, landing page and email."""

        # Get package
        instance = get_object_or_404(models.Package, pk=int(id))

        # and template
        try:
            field, label, ctype = self.TEMPLATE_TYPES.get(template_type, None)
        except ValueError:
            raise Http404()

        opts = self.model._meta

        return render_to_response('packages/preview.html', {
            'title': 'Preview %s' % label,
            'original': instance,
            'object': instance,
            'module_name': capfirst(force_text(opts.verbose_name_plural)),
            'object_id': instance.id,
            'opts': opts,
            'template_type': template_type,
            'app_label': 'clients',
            'links': ((template_type, label)
                      for template_type, (field, label, ctype)
                      in self.TEMPLATE_TYPES.items()),
        }, RequestContext(request))

    def preview_iframe(self, request, id, template_type):
        """The iframe contents to preview."""

        # Get package
        instance = get_object_or_404(models.Package, pk=int(id))

        # and template
        try:
            field, label, ctype = self.TEMPLATE_TYPES.get(template_type, None)
        except ValueError:
            raise Http404()

        if template_type == 'video':
            return HttpResponse(
                instance.render_video_template(),
                content_type='text/plain'
            )
        else:
            try:
                content = instance.campaign.type\
                    .render(template_type, instance.context())
            except Exception as exc:
                return HttpResponse('Error occured. <p>%s</p>' % exc)

            return HttpResponse(content, content_type=ctype)

    def get_urls(self):
        urls = super(PackageAdmin, self).get_urls()

        return patterns(
            '',
            url(r'^(?P<id>\d+)/preview/(?P<template_type>\w+)/$',
                self.preview, name='preview'),
            url(r'^(?P<id>\d+)/preview_iframe/(?P<template_type>\w+)/$',
                self.preview_iframe, name='preview_iframe'),
        ) + urls

    @allow_tags
    def video_preview(self, obj):
        if obj.video_key:
            return settings.VIDEO_EMBED % obj.video_key

        elif obj.stupeflix_key \
                and obj.campaign_id \
                and not obj.campaign.streaming_enable:
            return '<video src="{}" style="max-width: 800px" controls />'\
                .format(obj.video_url())

        else:
            return 'Video not available.'

    def edit(self, *args, **kwargs):
        return 'Edit'

    def get_changelist(self, request, **kwargs):
        return PackageChangeList

    def changelist_view(self, request, extra_context=None):
        if not request.GET.__contains__('status__exact'):
            q = request.GET.copy()
            q['status__exact'] = 'pending'
            request.GET = q
            request.META['QUERY_STRING'] = request.GET.urlencode()

        return super(PackageAdmin, self).changelist_view(
            request,
            extra_context=extra_context)

    def get_changelist_form(self, request, **kwargs):
        kwargs['form'] = PackageForm
        return super(PackageAdmin, self).get_changelist_form(request, **kwargs)

    def get_changelist_formset(self, request, **kwargs):
        kwargs['formset'] = PackageFormSet
        return ModelAdmin.get_changelist_formset(self, request, **kwargs)

    def save_related(self, request, form, formsets, change):
        """Trigger saving formsets."""

        if hasattr(form, 'nested') and form.nested:
            formsets = [form.nested]

            # duplicate images
            package_id = form.instance.id
            for subform in form.nested.forms:
                if not subform.instance.id:
                    subform.instance.package_id = package_id
                    subform.instance.image = models.PackageImage.objects.get(
                        id=subform.cleaned_data['source']
                    ).image

        super(PackageAdmin, self).save_related(request, form, formsets, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """In Company dropdown, limit choices to the companies where
        the current user has change_campaign permission.
        In Base dropdown, limit choices to the campaigns of these companies,
        excluding current one."""

        if db_field.name == 'company':
            kwargs['queryset'] = models.Company.objects.all().order_by('name')

        return super(PackageAdmin, self).formfield_for_foreignkey(
            db_field,
            request,
            **kwargs)

    def response_change(self, request, obj):
        """If production or email sending is activated,
        we do not go to Packages."""

        opts = self.model._meta
        preserved_filters = self.get_preserved_filters(request)

        if {'_produce', '_send', '_skip', '_void'} & set(request.POST.keys()):
            redirect_url = request.path
            redirect_url = add_preserved_filters({
                    'preserved_filters': preserved_filters,
                    'opts': opts
                },
                redirect_url)
            return HttpResponseRedirect(redirect_url)

        else:
            return super(PackageAdmin, self).response_change(request, obj)

    def save_model(self, request, obj, form, change):
        """Status changes."""

        latest_package = models.Package.objects.get(id=obj.id)

        if latest_package.status not in {
                'pending', 'erroneus', 'void', 'skipped', 'approved',
                'produced', 'sent', 'bounced', 'archived'}:
            messages.add_message(
                request, messages.ERROR,
                'Package #%s is now in production and cannot be changed. '
                'Please wait until complete.' % obj.id
            )
            return

        if '_skip' in request.POST:
            obj.status = 'skipped'

        elif '_void' in request.POST:
            obj.status = 'void'

        elif '_produce' in request.POST:
            obj.status = 'ready'

        elif '_send' in request.POST:
            obj.status = 'sending'

        super(PackageAdmin, self).save_model(request, obj, form, change)

    def history_view(self, request, object_id, extra_context=None):
        """Package history as stored in Events table."""

        try:
            object_id = int(object_id)
        except ValueError:
            raise Http404()

        package = get_object_or_404(models.Package, id=object_id)

        if not self.has_change_permission(request, package):
            raise PermissionDenied

        model = self.model
        opts = model._meta
        app_label = opts.app_label

        events = package.events.all()

        context = {
            'title': 'Events for %s' % str(package),
            'module_name': capfirst(force_text(opts.verbose_name_plural)),
            'object': package,
            'app_label': app_label,
            'opts': opts,
            'event_list': events,
            'preserved_filters': self.get_preserved_filters(request),
        }

        context.update(extra_context or {})

        return TemplateResponse(
            request,
            self.object_history_template,
            context,
            current_app=self.admin_site.name
        )

    def has_add_permission(self, *args):
        return False

    class Media:
        js = (
            'admin/js/jquery.js',
            'lib/jquery-global.js',
            'ui/jquery-ui.min.js',
            # 'http://ajax.googleapis.com/ajax/libs/jqueryui/1.8.5/jquery-ui.'
            # 'min.js',
            'lib/jquery.mousewheel-3.0.6.pack.js',
            'fancybox/jquery.fancybox.js',
            INLINE_ORDERING_JS,
        )
        css = {'all': (
            'css/package.css',
            'ui/jquery-ui.min.css',
            'fancybox/jquery.fancybox.css',
        )}


site.register(models.Package, PackageAdmin)
