import os
import time

from sorl.thumbnail import get_thumbnail
from class_based_auth_views.views import LoginView

from django.db.models import Q, Prefetch
from django.shortcuts import get_object_or_404
from django.views import generic
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponse, Http404
from django.conf import settings

from clients import models
from live.models import MontageVideo, Link
from live.tasks import embed_code
from offers.models import Offer


class VisitView(generic.DetailView):
    model = models.Package
    slug_url_kwarg = 'landing_page_key'
    slug_field = 'landing_page_key'
    template_name = 'live/visit.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        url_tail = self.kwargs['target']

        if url_tail.isdigit():
            link_id = int(self.kwargs['target'])
            link = get_object_or_404(Link, id=link_id)
            self.target_url = link.value
            service = {
                'website': link.type,
                'social': link.type + '_site',
                'review': link.type + '_site',
            }.get(link.type)
        elif url_tail in ['offer_others', 'offer_recipient']:
            service = url_tail
            target_audience = url_tail.split('_')[1]
            self.target_url = Offer.objects.filter(
                campaign=self.object.campaign_id,
                target_audience=target_audience,
            ).first().link_url
        else:
            raise Http404

        models.Event.objects.try_create_event(
            package=self.object,
            type='visit',
            description='Visited {}: {}'.format(
                service.replace('_', ' '),
                self.target_url,
            ),
            service=service,
            request=request,
        )

        return super(VisitView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(VisitView, self).get_context_data(**kwargs)

        context.update({
            'target_url': self.target_url,
        })

        return context


class TrackingPixelView(generic.DetailView):
    model = models.Package
    slug_url_kwarg = 'landing_page_key'
    slug_field = 'landing_page_key'

    # From: http://css-tricks.com/snippets/html/base64-encode-of-1x1px-
    # transparent-gif/
    BLANK_GIF = 'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'

    def render_to_response(self, context, **response_kwargs):
        models.Event.objects.try_create_event(
            package=self.object,
            type='open_email',
            request=self.request,
        )

        response = HttpResponse(
            self.BLANK_GIF.decode('base64'),
            content_type='image/gif',
        )

        response['Cache-Control'] = 'no-cache'

        return response


class DownloadPhotoView(generic.DetailView):
    model = models.PackageImage

    def render_to_response(self, context, **response_kwargs):
        """Return the image to download."""

        # Register this event
        models.Event.objects.try_create_event(
            package=self.object.package,
            type='share',
            service='download_photo',
            description='Image #{} was downloaded.'.format(self.object.id),
            request=self.request,
        )

        image = self.object.image

        image = get_thumbnail(
            image, '{}x{}'.format(image.width, image.height),
            overlay=self.object.package.company.get_stamp_path()
        )

        # Generate the image and return it.
        response = HttpResponse(image.read(), content_type='image/jpeg')
        response['Content-Disposition'] = \
            'attachment; filename={}-{}.jpg'.format(
                self.object.package.landing_page_key,
                self.object.inline_ordering_position or 0
        )

        return response


class LandingView(generic.DetailView):
    model = models.Package
    slug_url_kwarg = 'landing_page_key'
    slug_field = 'landing_page_key'

    def get_template_names(self):
        if not self.object.campaign.type_id:
            raise Exception('Camapign has no template.')
        return ['campaigns/landing/{}.jinja'.format(
            self.object.campaign.type.landing_template_name
        )]

    def get_context_data(self, **kwargs):
        context = super(LandingView, self).get_context_data(**kwargs)

        self.object.prefetch_thumbnails = self.object.images.filter(
            is_thumbnail=True)
        campaign = self.object.campaign

        if not kwargs.get('skip_create_event'):
            models.Event.objects.try_create_event(
                package=self.object,
                type='open_landing',
                service=self.kwargs.get('modifier', ''),
                request=self.request,
            )

        # Flags
        flags = {
            'shared': False,  # This means that landing page is opened
                              # from social network
            'photo': False,   # Landing page focus is photo
            'recipient': False,  # Force recipient  (for debugging)
        }

        modifier = self.kwargs.get('modifier')
        if modifier:
            for flag in modifier.lower().split('-'):
                if flag in flags:
                    flags[flag] = True

        # Offers

        context['offer'] = \
            (self.object.landing_views == 0 or flags['recipient']) \
            and campaign.offers.filter(target_audience='recipient').first() \
            or campaign.offers.filter(target_audience='others').first()

        links = Link.objects.filter(
            company_id=self.object.company_id,
        ).filter(
            Q(campaign__isnull=True) | Q(campaign_id=self.object.campaign_id)
        )
        website_link = links.filter(type='website').first()
        social_link = links.filter(type='social').first()

        review_links = links.filter(type='review').order_by('position')[:4]

        images = self.object.images.exclude(
            image='',
        ).filter(
            is_skipped=False,
            image__isnull=False,
        ).order_by('inline_ordering_position')
        campaign_images = images.filter(campaign__isnull=True)
        plain_images = campaign_images.filter(is_thumbnail=False)

        context.update({
            'flags': flags,

            'images': images,
            'campaign_images': campaign_images,
            'plain_images': plain_images,

            'campaign_media': campaign.attachments(campaign.media),

            'timestamp': int(time.time()),

            'website_link': website_link,
            'social_link': social_link,
            'review_links': review_links,
            'review_link': review_links.first(),

            'VBOOSTLIVE_URL': settings.VBOOSTLIVE_URL,
        })

        # Thumbnail image
        try:
            context['thumb'] = self.object.thumbnail()
            context['cropped_thumb'] = self.object.cropped_thumbnail()
            context['photo_thumb'] = self.object.photo_thumbnail()
        except models.PackageImage.DoesNotExist:
            context['thumb'] = None
            context['cropped_thumb'] = None

        return context


class Mixin(object):
    def _get_packages(self, prefetch_thumbnails=True):
        packages = models.Package.objects.exclude(
            company__is_test=True,
        ).filter(
            campaign__is_active=True,
            recipient_permission=True,
            status='sent',
        ).select_related(
            'contact',
        )
        if prefetch_thumbnails:
            packages = packages.prefetch_related(
                Prefetch(
                    'images',
                    queryset=models.PackageImage.objects.filter(
                        is_thumbnail=True),
                    to_attr='prefetch_thumbnails',
                ),
            )
        return packages

    def top_viewed_packages(self, days=30, filter_by_company=True,
                            prefetch_thumbnails=True):
        result = self._get_packages(
            prefetch_thumbnails=prefetch_thumbnails).filter(
                last_mailed__gte=(timezone.now()
                                  - timezone.timedelta(days=days)),
        ).select_related(
            'company',
        ).order_by('-video_views')
        company = getattr(self, 'object', None)
        if company and filter_by_company:
            result = result.filter(company=company)
        return result

    def happy_customer(self):
        result = self._get_packages().filter(
            last_mailed__gte=(timezone.now() - timezone.timedelta(days=30)),
        ).order_by('-page_views')[:12]
        return result

    def top_viewed_packages_last_m(self):
        result = self._get_packages(prefetch_thumbnails=False).filter(
            last_mailed__gte=(timezone.now() - timezone.timedelta(days=60)),
            last_mailed__lte=(timezone.now() - timezone.timedelta(days=30)),
        ).order_by('-video_views')
        company = getattr(self, 'object', None)
        if company:
            result = result.filter(company=company)
        return result[:1]

    def top_viewed_packages_this_m(self):
        result = self._get_packages(prefetch_thumbnails=False).filter(
            last_mailed__gte=(timezone.now().replace(day=1)),
            last_mailed__lte=timezone.now(),
        ).order_by('-video_views')
        company = getattr(self, 'object', None)
        if company:
            result = result.filter(company=company)
        if not result.exists():
            result = self.top_viewed_packages_last_m()
        return result[:1]

    # It is used in index.html
    def top_shared_packages_last_m(self):
        result = self._get_packages().filter(
            last_mailed__gte=(timezone.now() - timezone.timedelta(days=30)),
        ).order_by('-shares')
        company = getattr(self, 'object', None)
        if company:
            result = result.filter(company=company)
        return result[:3]

    def get_context_data(self, **kwargs):
        context = super(Mixin, self).get_context_data(**kwargs)
        context.update({
            'VBOOSTLIVE_URL': settings.VBOOSTLIVE_URL,
            'happy_customer': self.happy_customer(),
            'top_viewed_packages_this_month':
                self.top_viewed_packages_this_m(),
            'top_viewed_packages_last_week':
                self.top_viewed_packages(days=7)[:1],
            'top_viewed_packages_last_year':
                self.top_viewed_packages(days=365)[:1],
            'top_viewed_packages':
                self.top_viewed_packages(filter_by_company=False)[:3],

            'top_viewed': {
                'month': self.top_viewed_packages(
                    days=30, prefetch_thumbnails=False).first(),
            }
        })
        return context


class IndexView(Mixin, generic.TemplateView):
    template_name = 'live/index.html'

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)

        thirty_days_past = timezone.now() - timezone.timedelta(days=30)
        sixty_dats_past = timezone.now() - timezone.timedelta(days=60)

        feeds = {
            category: models.Package.objects.exclude(
                company__is_test=True,
            ).filter(
                campaign__type__category=category,
                last_mailed__gte=thirty_days_past,
                recipient_permission=True,
                status='sent',
            ).select_related(
                'contact',
                'company',
            ).prefetch_related(
                Prefetch(
                    'images',
                    queryset=models.PackageImage.objects.filter(
                        is_thumbnail=True),
                    to_attr='prefetch_thumbnails',
                ),
            )[:4] for category in [
                # 'mylead', 'myride',
                'mycustomer', 'myshow',
            ]
        }

        if feeds['mycustomer']:
            context.update({
                'mycustomer': feeds['mycustomer'][0],
                'mycustomers': feeds['mycustomer'][1:5],
            })

        context.update({
            'montage_video': MontageVideo.objects.filter(
                is_visible=True,
            ).select_related(
                'company',
            ).order_by('-date')[:4],

            'feeds': feeds,
            'packages': self._get_packages().select_related('company')
                            .order_by('-last_mailed')[:9],

            'top_viewed_package_previous': self._get_packages(
                prefetch_thumbnails=False).filter(
                    last_mailed__gte=sixty_dats_past,
                    last_mailed__lte=thirty_days_past,
            ).order_by('-video_views').first(),
        })

        return context


class CompanyView(Mixin, generic.DetailView):
    model = models.Company
    template_name = 'live/company.html'

    def get_avatar(self):
        return getattr(models.Campaign.objects.filter(
            company=self.object,
            is_active=True,
        ).exclude(
            about_image='',
        ).first(), 'about_image', None) or \
            getattr(models.CampaignImage.objects.filter(
                campaign__company=self.object,
                campaign__is_active=True,
            ).first(), 'image', None) or self.object.logo

    def top_shared_packages_last7(self):
        result = models.Package.objects.filter(
            last_mailed__gte=(timezone.now() - timezone.timedelta(days=7)),
            shares__gt=0,
            company=self.object,
        ).order_by('-shares')
        return result

    def get_context_data(self, **kwargs):
        context = super(CompanyView, self).get_context_data(**kwargs)

        packages = self.object.packages.filter(
            campaign__is_active=True,
            recipient_permission=True,
            status='sent',
        ).select_related(
            'contact',
        ).prefetch_related(
            Prefetch(
                'images',
                queryset=models.PackageImage.objects.filter(is_thumbnail=True),
                to_attr='prefetch_thumbnails',
            ),
        ).order_by('-last_mailed')

        the_packages = packages

        top_shared_packages = packages.filter(
            shares__gt=0,
        ).order_by('-shares')

        paginator = Paginator(packages, 9)
        page = self.request.GET.get('page')

        try:
            packages = paginator.page(page)
        except PageNotAnInteger:
            packages = paginator.page(1)
        except EmptyPage:
            packages = paginator.page(paginator.num_pages)

        context.update({
            'embed': bool(self.request.GET.get('embed')),
            'cover_image': models.CompanyImage.objects.filter(
                company=self.object,
                type='live_cover',
            ).first(),
            'page': page,
            'prepreend_page': str(paginator.num_pages-2),
            'montage_video': MontageVideo.objects.filter(
                is_visible=True,
                company=self.object,
                date__isnull=False,
            ).order_by('-date')[:4],
            'packages': packages,
            'paginator': paginator,

            # 'mycustomer_montage': MontageVideo.objects.filter(
            #     company=self.object,
            #     date__isnull=False,
            # ).order_by('-date').first() or MontageVideo.objects.filter(
            #     company=self.object,
            # ).order_by('-id').first(),

            'top_shared_packages_last_7': self.top_shared_packages_last7()[:3],
            'top_shared_packages': top_shared_packages[:3],
            'top_shared_package': top_shared_packages.first(),
            'mycustomer_package': the_packages.filter(
                campaign__type__category='mycustomer',
            ).order_by('-last_mailed').first()
        })

        return context


class EmbedPreviewView(generic.DetailView):
    model = models.Company
    template_name = 'live/test_company.html'

    def get_context_data(self, **kwargs):
        context = super(EmbedPreviewView, self).get_context_data(**kwargs)

        context.update({
            'embed_code': embed_code(self.object),
        })

        return context


class CustomLogin(Mixin, LoginView):
    template_name = 'live/login.html'
    success_url = '/'

    def get_context_data(self, **kwargs):
        context = super(CustomLogin, self).get_context_data(**kwargs)
        context.update({
        })

        return context

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super(LoginView, self).dispatch(*args, **kwargs)


class WidgetScriptView(generic.DetailView):
    model = models.Company
    slug_field = 'token'
    slug_url_kwarg = 'slug'

    template_name = 'live/widget.js'

    def get_context_data(self, **kwargs):
        context = super(WidgetScriptView, self).get_context_data(**kwargs)

        context.update({
            'cover_image': models.CompanyImage.objects.filter(
                company=self.object, type='live_cover').first(),
            'widget_script': os.path.join(
                settings.VBOOSTLIVE_URL, 'widget/'
            ) + 'widget-' + str(self.object.token) + '.js',
            'static_path':   os.path.join(
                settings.HOST_URL,
                'static/live/widget/'),
            'media_path':    os.path.join(settings.HOST_URL, 'media/'),
            'widget_api_root_url': os.path.join(
                settings.HOST_URL,
                'api/v1/live/'),
            'widget_host': settings.HOST_URL,
        })

        return context
