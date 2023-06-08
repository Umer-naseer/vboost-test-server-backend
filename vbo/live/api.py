import rest_framework

from sorl.thumbnail import get_thumbnail
from rest_framework import generics, serializers
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from django.conf import settings
from django.db.models import Prefetch
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from clients.models import Company, Contact, Package, PackageImage
from live.models import MontageVideo


class MontageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    def get_image(self, obj):
        if obj.image:
            return get_thumbnail(
                str(obj.image),
                '325x264',
                crop='faces',
                overlay=self.context['view'].mask_image,
                # overlay_mode='mask'
            ).url
        else:
            return None

    class Meta:
        model = MontageVideo
        fields = ('image', 'video', 'date')


class MontageView(generics.ListAPIView):
    # queryset = MontageVideo.objects.all()
    serializer_class = MontageSerializer
    permission_classes = (AllowAny,)

    def get_queryset(self):
        cid = self.kwargs['pk']
        company = get_object_or_404(Company, pk=cid)
        self.mask_image = company.get_stamp_path()
        return MontageVideo.objects.filter(
            company=cid,
            is_visible=True,
            date__isnull=False
        ).order_by('-date')[:4]

    def finalize_response(self, request, *args, **kwargs):
        response = super(MontageView, self)\
            .finalize_response(request, *args, **kwargs)
        response['Access-Control-Allow-Origin'] = '*'
        return response


class WidgetPackageSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    url = serializers.ReadOnlyField(source='get_landing_page_url')
    contact = serializers.SerializerMethodField()

    def get_image(self, obj):
        if obj.thumbnail():
            return get_thumbnail(
                str(obj.thumbnail()),
                '241x140',
                crop='faces',
                overlay=self.context['view'].mask_image,
                # overlay_mode='mask'
            ).url
        else:
            return None

    def get_contact(self, obj):
        return getattr(obj.contact, 'name', '')

    class Meta:
        model = Package
        fields = ('image', 'url', 'contact', 'last_mailed')


class WidgetPackageView(generics.ListAPIView):
    serializer_class = WidgetPackageSerializer
    pagination_class = rest_framework.pagination.LimitOffsetPagination
    permission_classes = (AllowAny,)
    response = Response()
    response['Access-Control-Allow-Origin'] = '*'

    def get_queryset(self):
        cid = self.kwargs['pk']
        company = get_object_or_404(Company, pk=cid)
        self.mask_image = company.get_stamp_path()
        return Package.objects.filter(
            company_id=cid,
            status='sent',
            campaign__is_active=True,
        ).exclude(
            recipient_permission=False,
        ).prefetch_related(
            Prefetch(
                'contact',
                queryset=Contact.objects.only('name'),
            ),
            Prefetch(
                'images',
                queryset=PackageImage.objects.filter(is_thumbnail=True),
                to_attr='prefetch_thumbnails',
            ),
        ).order_by('-last_mailed')

    def finalize_response(self, request, *args, **kwargs):
        response = super(WidgetPackageView, self)\
            .finalize_response(request, *args, **kwargs)
        response['Access-Control-Allow-Origin'] = '*'
        return response

    @method_decorator(cache_page(settings.CACHE_EXPIRY_TIME))
    def dispatch(self, *args, **kwargs):
        return super(WidgetPackageView, self).dispatch(*args, **kwargs)
