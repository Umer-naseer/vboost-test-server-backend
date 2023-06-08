import os
import logging
import jinja2
from io import StringIO, BytesIO
from .content import Content as content
import datetime
import xhtml2pdf.pisa as pisa

from celery.contrib.methods import task
from dateutil import rrule
from django_fsm import FSMField
from feincms.models import create_base_model, Base
from mailer.utils import send_email
from mailer.utils import validate_email_list
from jinja2 import Environment, PackageLoader
from premailer import transform
from recurrent import RecurringEvent
from .utils import period

from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import models
from django.utils.safestring import mark_safe

from clients.models import Contact
from campaigns.models import CampaignType

from generic.decorators import allow_tags
from generic.models import LoggingModel
from generic.tasks import LoggingTask
from django.contrib.admin.models import CHANGE

from .content import CONTENT_TYPES


logger = logging.getLogger(__name__)


class ReportForm(Base):
    name = models.CharField(max_length=255, default='New Report', unique=True)
    title = models.CharField(max_length=255)

    def __str__(self):
        return self.name


# Attach content types to Report
report = ReportForm()
report.register_regions(
    ('main', 'Main content'),
)
for content_type in CONTENT_TYPES:
    report.create_content_type(content_type)


class ContactMixin(models.Model):
    """Contact list management."""

    contacts = models.ManyToManyField(
        'clients.Contact', blank=True,  # null=True,
        help_text='Whom to send the report?'
    )

    more_contacts = models.CharField(
        max_length=512, blank=True,
        help_text='Additional contacts: comma-separated email addresses.'
    )

    message = models.TextField(
        blank=True,
        help_text='Custom message for report recipients. Displayed in HTML '
                  'email only (is not included in PDF version). You can '
                  'use variables, such as {{ contact_name }} or {{ company }}.'
    )

    def contact_list(self, raise_exception=True):
        """Ensure that contacts are valid."""

        def get_linked_contacts():
            return self.contacts.filter(
                company_id=self.company_id,
                is_active=True,
                type='manager',
            ).exclude(
                email=''
            )

        linked_contacts = getattr(
            self, 'prefetch_contacts', get_linked_contacts()
        )

        additional_contacts = validate_email_list(self.more_contacts)

        return list(linked_contacts) + additional_contacts

    class Meta:
        abstract = True


class Schedule(ContactMixin, models.Model):
    """Report generation schedule."""

    PERIODS = (
        ('Relative periods', (
            ('yesterday', 'Yesterday'),
            ('week', 'Last 7 days'),
            ('biweek', 'Last 14 days'),
            ('month', 'Last 30 days'),
            ('prev_month', 'Previous 30 days (60-30 from now)'),
            ('quarter', 'Last 90 days'),
            ('prev_quarter', 'Previous 90 days (180-90 from now)'),
            ('year', 'Last 365 days'),
            ('prev_year', 'Previous 365 days (730-365 from now)'),
        )),

        ('Calendar periods', (
            ('cal_this_week', 'Current calendar week'),
            ('cal_week', 'Last calendar week'),
            ('cal_prev_week', 'Previous calendar week'),
            ('cal_biweek', 'Last 2 calendar weeks'),
            ('cal_this_month', 'Current calendar month'),
            ('cal_month', 'Last calendar month'),
            ('cal_this_quarter', 'Current calendar quarter'),
            ('cal_quarter', 'Last calendar quarter'),
            (
                'cal_this_quarter_last_year',
                'Current calendar quarter of the last year'
            ),
            (
                'cal_quarter_last_year',
                'Last calendar quarter of the last year'
            ),
            ('cal_this_year', 'Current calendar year'),
            ('cal_year', 'Last calendar year'),
        )),
    )

    form = models.ForeignKey(ReportForm)
    company = models.ForeignKey('clients.Company')
    campaigns = models.CharField(
        max_length=64, choices=CampaignType.CATEGORY_CHOICES, blank=True, null=True,
        help_text='Use these campaigns only'
    )

    period = models.CharField(
        max_length=64, choices=PERIODS,
        default='yesterday',
        help_text='Time range',
    )

    pattern = models.CharField(
        max_length=512, blank=True,
        help_text=mark_safe(
            'Ex.: daily; every tuesday. See <a href="/wiki/Report_'
            'schedules">documentation</a> for more details.'
        )
    )

    is_active = models.BooleanField(
        'Enable delivery', default=True, blank=True
    )
    send = models.BooleanField(
        'Send instantly', blank=True, default=False,
        help_text='Send the reports on generation or leave for manual review?'
    )

    def is_time(self, today):
        """Is this time to instantiate this report?"""

        today = datetime.datetime(
            year=today.year,
            month=today.month,
            day=today.day
        )

        if not self.is_active or not self.pattern:
            return False

        event = RecurringEvent(now_date=today)

        rfc_string = event.parse(self.pattern)
        if type(rfc_string) != str:
            return False

        rr = rrule.rrulestr(
            rfc_string,
            dtstart=today
        )

        return today in rr

    def attempt(self, today, force=False):
        """Try generating the report for the specified date, if appropriate."""

        # Do we actually need to execute this?
        if not self.is_time(today) and not force:
            return  # No conditions met, retiring

        date_from, date_to = period(today, self.period)

        report = self.reports.create(
            form=self.form,
            company=self.company,
            campaigns=self.campaigns,
            more_contacts=self.more_contacts,
            date_created=today,
            date_from=date_from,
            date_to=date_to,
            message=self.message,
        )

        try:
            Report.generate(report)

            for contact in self.contacts.all():
                report.contacts.add(contact)

            if self.send:
                report.send()

        except Exception as exc:
            report.state = 'error'
            report.error = str(exc)
            report.save()

            logger.error(str(exc), exc_info=True, extra={
                'instance': report,
            })

        return report

    def __str__(self):
        return '%s of %s for %s' % (
            self.form,
            self.company,
            ', '.join(map(str, self.contact_list(raise_exception=False)))
            or '(No contacts)'
        )


class Report(ContactMixin, LoggingModel):
    """Individual report."""

    STATES = (
        ('new', 'Newly created'),
        ('generation', 'In generation'),
        ('generated', 'Generated'),
        ('delivery', 'In delivery'),
        ('delivered', 'Delivered'),
        ('error', 'Error'),
    )

    schedule = models.ForeignKey(
        Schedule, blank=True, null=True, related_name='reports'
    )
    form = models.ForeignKey(ReportForm)
    company = models.ForeignKey(
        'clients.Company',
        help_text='When changing the company, hit "Save and continue editing" '
                  'to update the contact list.'
    )
    campaigns = models.CharField(
        max_length=64, choices=CampaignType.CATEGORY_CHOICES, blank=True,
        null=True, help_text='Use campaigns of this type only'
    )

    state = FSMField(default='new', choices=STATES)

    date_from = models.DateField(help_text='Start date')
    date_to = models.DateField(help_text='End date')

    date_created = models.DateTimeField(
        null=True, blank=True, auto_now_add=True
    )
    is_mailed = models.BooleanField(default=False, blank=True)

    title = models.CharField(max_length=512, blank=True)
    body = models.TextField(blank=True)

    # Where to send reports from?
    FROM_EMAIL = 'Vboost Reporting <reports@vbresp.com>'
    REPLY_TO = 'Vboost Reporting <reports@vboost.com>'

    def is_available(self):
        """Is this report available for change?"""
        return self.state not in ('generation', 'delivery')

    def context(self):
        campaigns = self.company.campaign_set.filter(is_active=True)

        if self.campaigns:
            campaigns = campaigns.filter(type__category=self.campaigns)

        date_created = self.date_created
        if type(date_created) != datetime.date:
            date_created = date_created.date()

        return {
            'report': self,
            'company': self.company,

            'campaigns': campaigns,
            'campaign_type': self.campaigns,

            'form': self.form,
            'date': date_created,
            'date_from': self.date_from,
            'date_to': self.date_to,
        }

    def render_body(self, context):
        env = Environment(
            loader=PackageLoader('reporting', 'templates/reporting')
        )
        template = env.get_template('report.html')

        context['content'] = [block.render(**context)
                              for block in self.form.content.main]

        return transform(template.render(context))

    def render_title(self, context):
        return jinja2.Template(self.form.title).render(context)

    def render(self, render_pdf=True):
        """Render title, body, and (if necessary) PDF file."""

        context = self.context()

        # Render title
        title = self.render_title(context)
        context['title'] = title

        # And now body
        body = self.render_body(context)

        # And PDF, if requested
        pdf = self.render_pdf(body) if render_pdf else None

        return (title, body, pdf)

    @task(base=LoggingTask, name='reporting.generate')
    def generate(self):
        if not self.is_available():
            raise Exception('Cannot generate report "%s" because it is '
                            'already in processing.' % self)

        self.log_action('Generation started.', CHANGE)
        self.__class__.objects.filter(id=self.id).update(state='generation')

        self.title, self.body, pdf = self.render()

        if pdf:
            # Write PDF file
            with open(self.pdf_filename(), 'wb+') as f:
                f.write(pdf)

            self.state = 'generated'

        else:
            self.state = 'error'

        self.save()

        self.log_action('Generation complete.', CHANGE)

    @task(base=LoggingTask, name='reporting.deliver')
    def send(self):
        """Send this report to the contacts in the list."""

        if not self.is_available():
            raise Exception('Cannot deliver report "%s" because it is '
                            'already in processing.' % self)

        self.log_action('Delivery started.', CHANGE)
        self.__class__.objects.filter(id=self.id).update(state='delivery')

        # Whom to send to?
        to = self.contact_list()
        if not to:
            raise Exception('Cannot mail: no contacts defined.')

        # PDF report
        try:
            pdf = open(self.pdf_filename(), 'rb').read()
        except IOError:
            self.generate()
            pdf = open(self.pdf_filename(), 'rb').read()

        # Context to render the custom text message with
        context = self.context()

        message_template = jinja2.Template(self.message)

        for contact in to:

            # Send separate email to each contact.
            context['contact_name'] = contact.name \
                if isinstance(contact, Contact) else contact.split('@')[0]

            message = message_template.render(**context)

            send_email(
                content=self.body.replace(
                    '<!--MESSAGE-->',
                    message
                ),
                subject=self.title,
                to=str(contact),
                from_email=self.FROM_EMAIL,
                bcc=[self.REPLY_TO],
                headers={
                    'Reply-To': self.REPLY_TO,
                },
                attachments=[(
                    '%s.pdf' % self.title.replace(' ', '_'),
                    pdf,
                    'application/pdf'
                )]
            )

        self.state = 'delivered'
        self.save()

        self.log_action('Delivery complete.', CHANGE)

    @staticmethod
    def pdf_fetch_resources(uri, rel):
        """
        Callback to allow pisa/reportlab to retrieve Images,Stylesheets, etc.
        `uri` is the href attribute from the html link element.
        `rel` gives a relative path, but it's not used here.
        """

        # And media files
        if settings.MEDIA_URL in uri:
            url = os.path.join(
                settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, '')
            )

        # Fallback: external files
        else:
            url = uri.replace(' ', '+')

        return url

    def pdf_filename(self):
        return os.path.join(settings.MEDIA_ROOT, 'reports', '%s.pdf' % self.id)

    def render_pdf(self, content=None):
        """Make a PDF file, store it in the filesystem and return contents."""

        # Stored content
        if not content:
            content = self.body

        # Where to save?
        output = BytesIO()

        pdf = pisa.pisaDocument(
            src=StringIO(content),
            dest=output,
            link_callback=self.pdf_fetch_resources,
            encoding='utf-8',
            raise_exception=False
        )

        if pdf.err:
            return
        else:
            return output.getvalue()

    def save(self, *args, **kwargs):
        """Generate report on saving."""

        if not self.date_created:
            self.date_created = datetime.datetime.now()

        super(Report, self).save(*args, **kwargs)

    @allow_tags
    def preview_link(self):
        if self and self.id:
            if self.state == 'generation':
                return '<em>Generating a new report, please wait...</em>'

            else:
                return '<a onclick="%(onclick)s" href="%(html)s">HTML</a> | <a onclick="%(onclick)s" href="%(pdf)s">PDF</a>' % {
                    'html': reverse('admin:report-preview-html', args=(self.id, )),
                    'pdf': reverse('admin:report-preview-pdf', args=(self.id, )),
                    'onclick': 'return !window.open(this.href)'
                }

    def __str__(self):
        return '%s - %s' % (
            self.company,
            self.form
        )
