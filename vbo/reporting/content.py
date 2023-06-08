import GChartWrapper
import logging
import jinja2
import operator
import itertools

from jinja2 import Environment, PackageLoader
from generic.utils import daterange, last_minute
from feincms.content.raw.models import RawContent
from sorl.thumbnail import get_thumbnail

from django.db import models
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Sum, Count
from django.utils import timezone

from clients.models import Event, Package

from offers.models import Submission


logger = logging.getLogger(__name__)


env = Environment(
    loader=PackageLoader('reporting', 'templates/reporting'),
    extensions=['jinja2.ext.with_']
)

FORBIDDEN_STATUS_VALUES = ['void', 'skipped', 'preparation', 'duplicate']
AVAILABLE_STATUS_VALUES = ['sent', 'bounced']

def chart_prepare(chart):
    """Prepare a chart."""
    return str(chart).replace('.0,', ',')


class Content(models.Model):
    template = None

    def execute(self, **kwargs):
        raise ImproperlyConfigured('execute() is not defined.')

    def render(self, **kwargs):
        """Build the content."""

        data = self.execute(**kwargs)

        if data:
            template = env.get_template(self.template)
            return template.render(data)

        else:
            return ''

    class Meta:
        abstract = True


class PackagesList(Content):
    """List of packages."""
    SORT_BY = (
        ('contact__name', 'Sales rep'),
        ('video_views', 'Video views'),
        ('submitted_time', 'Submit date'),
    )

    template = 'package_list.html'

    show_approved_only = models.BooleanField(
        'Packages with Customer Permission only',
        default=False, blank=True, help_text='And display customer signatures'
    )
    show_bounced_only = models.BooleanField(
        'Show bounced packages only', default=False, blank=True
    )
    show_clicks = models.BooleanField(
        'Show verbose click statistics', default=False, blank=True
    )
    show_video_views = models.BooleanField(
        'Show video views column', default=True, blank=True
    )
    sort_by = models.CharField(
        max_length=128, choices=SORT_BY, default='contact__name'
    )
    sort_desc = models.BooleanField('Descending', default=False, blank=True)
    limit = models.PositiveSmallIntegerField(
        help_text='How many items to show? Empty or zero to show all.',
        null=True, blank=True
    )

    def get_signature(self, package):
        try:
            if package.recipient_signature:
                return {
                    'thumb': get_thumbnail(
                        package.recipient_signature.file, '200'
                    ).url,
                    'full': package.recipient_signature.url,
                }

        except IOError:
            pass

    def totals_by_events(self, events):
        visits = events.filter(type='visit')

        return {
            'views': events.filter(type='video').count(),

            'website':     visits.filter(service='website').count(),
            'review_site': visits.filter(service='review_site').count(),
            'social_site': visits.filter(service='social_site').count(),

            'offer_recipient_views':
                visits.filter(service='offer_recipient').count(),
            'offer_others_views':
                visits.filter(service='offer_others').count(),

            'photos':
                events.filter(type='share', service='download_photo').count(),
        }

    def execute(self, company, campaigns, date_from, date_to, **kwargs):
        # Packages mailed in the specified time period
        packages = Package.objects.filter(
            campaign__in=campaigns,
            status__in=AVAILABLE_STATUS_VALUES,
            submitted_time__gte=date_from,
            submitted_time__lte=last_minute(date_to)
        ).order_by(('-' if self.sort_desc else '') + self.sort_by)

        logger.info('_______excute called______ %s' % packages)
        if self.show_video_views:
            packages = packages.filter(video_views__gt=0)

        if self.show_approved_only:
            packages = packages.filter(recipient_permission=True)

        if not packages.exists():
            raise Exception('No data.')

        if self.limit:
            packages = packages[:self.limit]

        packages = list(packages)

        events = Event.objects.all()

        rows = [{
            'signature': self.get_signature(package),
            'target': package.recipient_email or package.recipient_phone,
            'rep': package.contact,
            'date':
                package.submitted_time.strftime('%m/%d/%Y')
                if package.submitted_time else '',
            'url': package.get_landing_page_url(),
            'views': {
                'email':
                    events.filter(package=package, type='open_email').count(),
                'landing':
                    events.filter(package=package, type='open_landing')
                    .count(),
                'video': events.filter(package=package, type='video').count(),
                'watched': str(timezone.timedelta(seconds=events.filter(
                    package=package, type='video'
                ).aggregate(duration=Sum('duration'))['duration'] or 0)),
            },
            'clicks': {
                'website':
                    events.filter(
                        package=package, type='visit', service='website'
                    ).count(),
                'review_site':
                    events.filter(
                        package=package, type='visit', service='review_site'
                    ).count(),
                'social_site':
                    events.filter(
                        package=package, type='visit', service='social_site'
                    ).count(),
                'photos':
                    events.filter(
                        package=package, type='share', service='download_photo'
                    ).count(),
            },
            'offers': {
                'recipient':
                    events.filter(
                        package=package, type='visit',
                        service='offer_recipient'
                    ).count(),
                'others': events.filter(
                    package=package, type='visit', service='offer_others'
                ).count(),
            },
            'shares': events.filter(package=package, type='share').count(),
            'viral_lift':
                events.filter(package=package, type='video').count() * 100,
        } for package in packages]

        return {
            'packages': rows,
            'totals': self.totals_by_events(events.filter(
                package__in=packages
            )),
            'show_clicks': self.show_clicks,
            'show_video_views': self.show_video_views,
            'show_approved_only': self.show_approved_only,
            'blocks_count': len(kwargs['form'].content.main)
        }

    class Meta:
        abstract = True


class VisitsToWebsites(Content):
    template = 'visits_to_websites.html'

    def execute(self, company, campaigns, date_from, date_to, **kwargs):
        visits = Event.objects.filter(
            package__in=Package.objects.filter(
                campaign__in=campaigns,
                submitted_time__gte=date_from,
                submitted_time__lte=last_minute(date_to)
            ).exclude(status__in=FORBIDDEN_STATUS_VALUES),
            time__gte=date_from,
            time__lte=last_minute(date_to),
            type='visit'
        )

        totals = visits.values_list(
            'service'
        ).order_by().annotate(Count('id'))

        return {
            'totals': dict(totals)
        }

    class Meta:
        abstract = True


class PackagesBySalesRep(Content):
    template = 'sales.html'

    show_clicks = models.BooleanField('Show verbose click statistics',
                                      default=False,
                                      blank=True)

    def execute(self, company, campaigns, date_from, date_to, **kwargs):
        # Contacts
        contacts = company.contact_set.all()

        # Data
        items = []
        for contact in contacts:
            item = contact.packages.filter(
                campaign__in=campaigns,
                submitted_time__gte=date_from,
                submitted_time__lte=last_minute(date_to),
            ).exclude(
                status__in=FORBIDDEN_STATUS_VALUES
            ).aggregate(
                sent=Count('id'),
                shares=Sum('shares'),
                views=Sum('video_views'),
                page_views=Sum('page_views'),

                website=Sum('website_views'),
                review_site=Sum('review_site_views'),
                social_site=Sum('social_site_views'),
                photos=Sum('photo_downloads'),
                offer_recipient=Sum('offer_recipient_views'),
                offer_others=Sum('offer_others_views'),
            )

            item.update({
                'name': contact.name,
                'opened': contact.packages.filter(
                    campaign__in=campaigns,
                    submitted_time__gte=date_from,
                    submitted_time__lt=last_minute(date_to),
                    landing_views__gt=0
                ).exclude(
                    status__in=FORBIDDEN_STATUS_VALUES
                ).count()
            })

            if item['opened']:
                item['viral_lift'] = \
                    item['views'] / float(item['opened']) * 100

            if item['sent'] or item['shares'] or item['views'] or \
               item['page_views'] or item['opened']:
                items.append(item)

        if not items:
            raise Exception('No data.')

        return {
            'items': items,
            'show_clicks': self.show_clicks,
            'totals': {
                'sent': sum(item['sent'] for item in items),
                'opened': sum(item['opened'] for item in items),
                'views': sum(item['views'] for item in items),
                'clicks': {
                    'website': sum(item['website'] for item in items),
                    'review_site': sum(item['review_site'] for item in items),
                    'social_site': sum(item['social_site'] for item in items),
                    'photos': sum(item['photos'] for item in items),
                    'offer_recipient':
                        sum(item['offer_recipient'] for item in items),
                    'offer_others':
                        sum(item['offer_others'] for item in items),
                }
            },
        }

    class Meta:
        abstract = True


class Activity(Content):
    """Activity summary block"""

    template = 'activity.html'

    show_clicks = models.BooleanField(
        'Show click statistics', default=False, blank=True
    )

    def execute(self, company, campaigns, date_from, date_to, **kwargs):
        # Video statistics data
        delivered_packages = Package.objects.filter(
            campaign__in=campaigns,
            submitted_time__gte=date_from,
            submitted_time__lte=last_minute(date_to),
        ).exclude(
            status__in=FORBIDDEN_STATUS_VALUES
        )

        events = Event.objects.filter(
            package__in=delivered_packages,
            time__gte=date_from,
            time__lte=last_minute(date_to)
        )

        # Let's calculate counts.
        clicks = events.filter(type='visit').count()

        page_views = events.filter(
            type='open_landing'
        ).values_list(
            'package', 'ip'
        ).order_by().distinct().count()

        video_views = events.filter(type='video').count()

        video_time_viewed = timezone.timedelta(seconds=events.filter(
            type='video'
        ).aggregate(
            duration=Sum('duration')
        )['duration'] or 0)
        shares = events.filter(type='share').count()

        opened = events.filter(
            type='open_landing'
        ).values_list(
            'package'
        ).order_by().distinct().count()

        totals = {
            'sent': delivered_packages.count(),
            'opened': opened,

            'page': page_views,
            'video': video_views,
            'viewed': video_time_viewed,
            'shares': shares,
            'clicks': clicks,
            'show_clicks': self.show_clicks,
            'viral_lift': (video_views / float(opened)) if opened else None
        }

        return totals

    class Meta:
        abstract = True


class DailyStatisticsChart(Content):
    """Video views and email views per day."""
    template = 'daily.html'

    def events_by_date(self, events):
        return dict(
            (date, len(list(items)))
            for date, items
            in itertools.groupby(events, operator.methodcaller('date'))
        )

    def execute(self, company, campaigns, date_from, date_to, **kwargs):
        packages = Package.objects.filter(
            campaign__in=campaigns,
            submitted_time__gte=date_from,
            submitted_time__lte=last_minute(date_to),
        ).exclude(
            status__in=FORBIDDEN_STATUS_VALUES
        )

        events = Event.objects.filter(
            package__in=packages,
            time__gte=date_from,
            time__lte=last_minute(date_to)
        ).values_list('time', flat=True).order_by()

        views_by_date = self.events_by_date(events.filter(type='video'))
        email_clicks_by_date = self.events_by_date(
            events.filter(type='open_email')
        )

        video_views = [
            views_by_date.get(date, 0)
            for date in daterange(date_from, date_to)
        ]
        email_clicks = [
            email_clicks_by_date.get(date, 0)
            for date in daterange(date_from, date_to)
        ]

        maximum = max((video_views + email_clicks) or [0])

        chart = GChartWrapper.Line([
            video_views,
            email_clicks
        ]).color(
            '538DD5',
            'D55953',
        ).size(600, 300).axes(['x', 'y', 'x']).marker(
            'B', 'CEDEF3', 0, 1, 0
        ).marker(
            'o', '538DD5', 0, -1, 5
        ).marker(
            'B', 'F3D0CE', 1, 1, 0
        ).marker(
            'o', 'D55953', 1, -1, 5
        ).legend(
            'Video views',
            'Photo Sets opened',
        ).legend_pos('b').scale(
            0, maximum
        ).fill('bg', 's', 'EFEFEF')

        if len(video_views) > 1 and maximum:
            chart.grid(
                100.0 / (len(video_views) - 1),
                100 / (maximum / 10.0),
                1, 0
            )

        chart.axes.range(1, 0, maximum, 10 if maximum > 20 else 1)  # Y

        days = list(daterange(date_from, date_to))

        interval = 5 if len(days) > 15 else 1
        chart.axes.label(0, *[day.day if not day.day % interval
                                         or day.day == 1
                              else '' for day in days
                              ]
                         )  # X

        # Months
        chart.axes.label(2, *[day.strftime('%b') if day.day == 1
                              else '' for day in daterange(date_from, date_to)
                              ]
                         )

        return {
            'chart': chart_prepare(chart),
        }

    class Meta:
        abstract = True


class SharingPerService(Content):
    template = 'shares.html'

    SERVICES = {
        'facebook': '3B5998',
        'print': 'CCCCCC',
        'addressbar': '53D559',
        'email': 'D553CF',
        'twitter': '37CCFF',
        'download_photo': '98593B'
    }

    SERVICE_NAMES = {
        'download_photo': 'Download Photo'
    }

    def execute(self, company, campaigns, date_from, date_to, **kwargs):
        events = Event.objects.filter(
            package__in=Package.objects.filter(
                campaign__in=campaigns,
                submitted_time__gte=date_from,
                submitted_time__lte=last_minute(date_to),
            ).exclude(
                status__in=FORBIDDEN_STATUS_VALUES
            ),
            time__gte=date_from,
            time__lte=last_minute(date_to),
            type='share'
        )

        # All services in question, ordered by event count desc
        events_by_service = list(
            events.values_list('service').order_by()
            .annotate(count=Count('id')).order_by('-count')
        )

        services = [service for service, total in events_by_service]

        # Lists of points for each service
        points = []
        for service in services:
            shares_by_date = dict(events.filter(
                service=service
            ).order_by('time').extra({'date': "date(time)"})
             .values_list('date').annotate(Count('id')))

            points.append(
                [shares_by_date.get(date, 0)
                    for date in daterange(date_from, date_to)]
            )

        # Max shares per day
        stacks = list(map(sum, zip(*points)))
        maximum = max(stacks or [0])

        if not maximum:
            return

        # Total value per service
        service_totals = dict(events_by_service)

        # Okay, let's draw it!
        chart = GChartWrapper.VerticalBarStack(points).scale(0, maximum)\
            .size(600, 300).color(
                *[self.SERVICES.get(service, 'D55953') for service in services]
        ).bar('a').legend(
            *('{name} ({count})'.format(
                name=self.SERVICE_NAMES.get(service, service.capitalize()),
                count=service_totals[service]
            ) for service in services)
        ).legend_pos('b').grid(
            0,
            100.0 / maximum,
            1, 0
        ).axes(['x', 'y', 'x']).fill('bg', 's', 'EFEFEF')

        # Axes
        dates = lambda: daterange(date_from, date_to)

        chart.axes.label(0, *[day.day if not day.day % 5 or day.day == 1
                              else '' for day in dates()])
        chart.axes.range(1, 0, maximum, 1)  # Y

        # Months
        chart.axes.label(2, *[day.strftime('%b') if day.day == 1
                              else '' for day in dates()])

        return {
            'total': sum(service_totals.values()),
            'chart': chart_prepare(chart),
        }

    class Meta:
        abstract = True


class TopVideos(Content):
    template = 'top.html'

    count = models.PositiveSmallIntegerField(
        default=5, help_text='How many videos to show?'
    )

    def execute(self, company, campaigns, date_from, date_to, **kwargs):
        packages = company.packages.filter(
            campaign__in=campaigns,
            submitted_time__gte=date_from,
            submitted_time__lte=last_minute(date_to),
            # status='sent',
        ).exclude(status__in=FORBIDDEN_STATUS_VALUES
                  ).order_by('-video_views')[:self.count]

        return {
            'packages': [{
                'thumb':
                    get_thumbnail(package.cropped_thumbnail(), 'x120').url,
                'target': package.recipient_email or package.recipient_phone,
                'contact': package.contact,
                'video_views': package.video_views,
                'link': package.get_landing_page_url(),
                'cover': package.cover,
            } for package in packages],
        }

    class Meta:
        abstract = True


class Template(models.Model):
    """Jinja2 template."""

    template = models.TextField(blank=True)

    def render(self, **kwargs):
        template = jinja2.Template(self.template)
        return template.render(**kwargs)

    class Meta:
        abstract = True


class SubmissionList(Content):
    template = 'submissions.html'

    def execute(self, company, campaigns, date_from, date_to, **kwargs):
        submissions = Submission.objects.filter(
            package__company=company,
            package__campaign__in=campaigns,
            created_time__gte=date_from,
            created_time__lte=last_minute(date_to),
        ).order_by('offer__id', 'created_time')

        return {
            'submissions': submissions
        }

    class Meta:
        abstract = True


from .map import Map


CONTENT_TYPES = (
    PackagesList,
    Activity,
    SharingPerService,
    DailyStatisticsChart,
    PackagesBySalesRep,
    TopVideos,
    Map,
    RawContent,
    SubmissionList,
    Template,
    VisitsToWebsites
)
