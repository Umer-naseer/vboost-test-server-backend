import os
import uuid
import json
import random
import urllib.parse  # was import urllib
import re
import logging
import datetime
import time
import subprocess
import shlex
import re
from PIL import Image

from django.db.models import QuerySet
from rest_framework.authtoken.models import Token
from sorl.thumbnail.fields import ImageField
from sorl.thumbnail import get_thumbnail
from concurrency.fields import AutoIncVersionField
from django_localflavor_us.models import PhoneNumberField

from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template import loader
from django.forms.models import model_to_dict
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.core.exceptions import ValidationError

from generic.utils import user_ip
from generic.decorators import allow_tags
from generic.models import Geospatial, ConcurrentModel
from campaigns.models import VIDEO_TEMPLATE_CHOICES
from live.tasks import embed_code, embed_preview_url
from inline_ordering.models import Orderable
# from validators import keyword_list

from os import path  # Do not remove!

logger = logging.getLogger(__name__)

pattern = re.compile(r"^(\w+)(,\s*\w+)*$")

def check_valid_text(input_string):
    if pattern.match(input_string) == None:
        return ValidationError('Invalid text')
    else:
        pass


def urlsafe(url):
    return urllib.parse.quote(url, '/:')

def find_video_duration(pathToInputVideo):
    """function to find the resolution of the input video file"""
  
    cmd = "ffprobe -v quiet -print_format json -show_streams"
    args = shlex.split(cmd)
    args.append(pathToInputVideo)
    # run the ffprobe process, decode stdout into utf-8 & convert to JSON
    ffprobeOutput = subprocess.check_output(args).decode('utf-8')
    ffprobeOutput = json.loads(ffprobeOutput)

    return ffprobeOutput['streams'][0]['duration']


COMPANY_STATUS_VALUES = (
    ('active', 'Active'),
    ('inactive', 'Inactive'),
    ('setup', 'Setup'),
    ('onhold', 'On hold'),
)


class Company(Geospatial):
    """A client company. It is always geolocated."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=64, unique=True, null=True)
    # token is the field to secure of the widget
    token = models.UUIDField(default=uuid.uuid4, null=True, db_index=True)
    website = models.URLField(blank=True)
    use_cdk = models.BooleanField('Use CDK', default=False)
    key = models.CharField(max_length=64, unique=True, blank=True, null=True,
                           help_text='Unique identification key.')
    status = models.CharField(
        max_length=255, default='active', choices=COMPANY_STATUS_VALUES
    )
    bio = models.TextField(blank=True)

    keywords1 = models.CharField(
        'Product Keywords', max_length=512, default='',
        help_text='Comma-separated keywords: product description',
        validators=[check_valid_text]
    )
    keywords2 = models.CharField(
        'Geo Keywords', max_length=512, default='',
        help_text='Comma-separated keywords: geography description',
        validators=[check_valid_text]
    )

    logo = models.ImageField(
        'Logo', upload_to='companies/logo', blank=True, null=True
    )

    mobile_logo = models.ImageField(
        'Mobile Logo',
        upload_to='companies/mobile_logo', blank=True, null=True,
        help_text='If the regular logo (see above) does not fit for mobile '
                  'devices, you can upload a mobile-friendly version here.'
    )

    watermark_logo = models.ImageField(
        'Watermark Logo',
        upload_to='companies/watermark_logo', blank=True, null=True,
        help_text='If the regular logo (see above) does not fit as a '
                  'watermark, you can upload a transparent PNG for this '
                  'purpose here.'
    )

    about_image = models.ImageField(
        'About image',
        upload_to='companies/about_image', blank=True, null=True,
        help_text='Large high quality picture for VboostLive company page.'
    )

    # Names to display
    default_company_name = models.CharField(
        max_length=100, blank=True, null=True
    )
    default_display_name = models.CharField(
        max_length=100, blank=True, null=True
    )
    default_email = models.EmailField(
        'Forwarding email', max_length=255, blank=True, null=True
    )
    company_email = models.EmailField(max_length=255, blank=True, null=True)
    default_phone = models.CharField(max_length=20, blank=True, null=True)
    crm_account_id = models.CharField(max_length=64, blank=True, null=True)
    forward_to_contacts = models.BooleanField(
        default=False, blank=True,
        help_text='Forward package emails to corresponding contacts.'
    )

    device_username = models.CharField(max_length=255, blank=True, null=True)
    device_password = models.CharField(max_length=25, blank=True, null=True)
    device_name = models.CharField(max_length=25, blank=True, null=True)
    device_serial_number = models.TextField(
        max_length=250, blank=True, null=True
    )
    device_phone_number = models.CharField(
        max_length=255, blank=True, null=True
    )

    logo_received = models.BooleanField(default=False)
    guided_access_password = models.CharField(
        max_length=25, blank=True, null=True
    )
    meid = models.TextField(max_length=250, blank=True, null=True)

    terms = models.TextField('Terms & Conditions', blank=True)
    filter_contacts = models.BooleanField(
        blank=True, default=False,
        help_text='Exclude Manager contacts in mobile application.'
    )
    is_test = models.BooleanField(default=False, db_index=True)

    def get_stamp_path(self):
        if self.watermark_logo:
            return self.watermark_logo.path

        elif self.logo:
            return self.logo.path

    def get_bio_display(self):
        return re.sub('^\s+|\n|\s+$', '</p><p>', self.bio)

    def __str__(self):
        return self.name

    def shares_by_service(self, start_date, end_date):
        shares = ServiceShare.objects.filter(
            campaign__in=self.campaign_set.filter(is_active=True),
            date__gte=start_date,
            date__lte=end_date
        ).values('service', 'count') \
            .annotate(total=models.Sum('count')) \
            .values('service', 'total')
        return dict((s['service'], s['total']) for s in shares)

    def default_from(self):
        """The email address handled by SES to send correspondence from."""
        return '%s <%s@%s>' % (
            self.name,
            self.slug,
            settings.OUTBOUND_EMAIL_HOST
        )

    def dealer_widget_embed_code(self):
        if self.pk:
            return format_html(
                """<code id="embed-code">{}</code><br>
                <button type="button" onclick="copyToClipboard('embed-code')">Copy code to clipboard</button>""",
                embed_code(self, cdk=True),
            )
        return 'Will be showed after company saving'

    @allow_tags
    def dealer_widget_embed_preview(self):
        if self.pk:
            return '<a target="_blank" href=' \
                   + embed_preview_url(self) \
                   + '>' + embed_preview_url(self) \
                   + '</a>'
        else:
            return 'Video not available'

    def get_absolute_url(self):
        from django.core.urlresolvers import reverse
        return reverse('live:company', args=[self.slug])

    class Meta:
        ordering = ['name']
        verbose_name = 'company'
        verbose_name_plural = 'companies'


class CompanyImage(models.Model):
    TYPE_CHOICES = [
        ('live_cover', 'VboostLive Cover image'),
    ]
    company = models.ForeignKey('Company')
    type = models.CharField(max_length=16, choices=TYPE_CHOICES, db_index=True)
    image = models.ForeignKey('gallery.Image')

    class Meta:
        unique_together = ('company', 'type')


class CompanyBoundModel(models.Model):
    """Most of the following models are linked to a Company.
    Anyway, this link is mostly not required."""
    company = models.ForeignKey(Company, blank=True, null=True)

    class Meta:
        abstract = True


class UserProfile(models.Model):
    # This field is required.
    user = models.OneToOneField(User, related_name='profile')

    title = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    company = models.ForeignKey('Company', blank=True, null=True)


# Create user profiles automatically


def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


post_save.connect(create_user_profile, sender=User)


def campaign_asset_path(name):
    def path(instance, filename):
        return 'campaigns/%s/%s/%s' % (
            name,
            instance.id,
            filename.replace(' ', '_')
        )

    return path


class Campaign(CompanyBoundModel):
    """Marketing campaign"""

    default_contact = models.ForeignKey(
        'clients.Contact', null=True, blank=True
    )

    vin_solutions_email = models.EmailField('VIN Solutions Email', blank=True)

    name = models.CharField(max_length=100, db_index=True)
    details = models.TextField(blank=True)

    type = models.ForeignKey(
        'campaigns.CampaignType', verbose_name='Campaign Type'
    )

    is_active = models.BooleanField(default=True, db_index=True)
    key = models.CharField(
        max_length=64, unique=True,
        help_text='Unique identification key.'
    )

    logo = models.ImageField('Upload logo', upload_to='companies/logo/')

    # Landing page settings
    landing_title = models.CharField(max_length=255, blank=True)
    photo_title = models.CharField(
        max_length=255, default='Save My Photo', blank=True
    )

    about_title = models.CharField(max_length=255, blank=True)
    about_subtitle = models.CharField(max_length=255, blank=True)
    about_image = models.ImageField(
        upload_to='companies/about_image/',
        blank=True, null=True,
        help_text='Campaign logo is used if empty.'
    )
    about_text = models.TextField(blank=True)

    sharing_title = models.CharField(
        max_length=255,
        help_text='Title for social networks. Company name is used if empty.',
        default='Watch This!',
    )

    sharing_description = models.TextField(
        max_length=255,
        help_text='Text for social networks.',
    )

    video_template = models.CharField(
        max_length=128,
        choices=VIDEO_TEMPLATE_CHOICES,
        blank=True,
    )

    # Workflow
    approval_instructions = models.TextField(blank=True, null=True)

    # Email settings
    use_contact_info = models.BooleanField(
        default=True,
        help_text="If checked, the package will be sent with source address "
                  "and name entered below. Otherwise, the system will attempt "
                  "to use sales rep address and name."
    )
    default_email = models.EmailField()

    default_from = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Company name is used if blank.',
    )

    default_subject = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text='"Your Photos from CompanyName" is used if blank.'
    )
    email_greeting = models.CharField(
        max_length=255, blank=True, null=True,
        help_text='Email greeting.'
    )
    default_name = models.CharField(max_length=100, blank=True, null=True)
    default_phone = models.CharField(max_length=20, blank=True, null=True)
    notification_email = models.EmailField(
        blank=True,
        help_text='Notify about every new package.'
    )
    notification_email_template = models.ForeignKey(
        'templates.Template',
        related_name='using_email_notification',
        blank=True, null=True
    )
    email_managers = models.TextField(
        blank=True,
        help_text='Contacts to BCC the email to: '
                  'comma-separated email addresses.'
    )

    tracking_username = models.CharField(max_length=50, blank=True, null=True)
    tracking_password = models.CharField(max_length=50, blank=True, null=True)
    tracking_link = models.CharField(max_length=255, blank=True, null=True)
    google_analytics = models.CharField(max_length=255, blank=True, null=True)

    def get_tracking_id(self):
        return re.match('.+(ra-.+)', self.tracking_link).group(1)

    custom_download_link = models.CharField(
        max_length=255, blank=True, null=True
    )
    custom_email_account = models.EmailField(blank=True, null=True)
    custom_email_password = models.CharField(
        max_length=25, blank=True, null=True
    )

    streaming_enable = models.BooleanField(
        'Enable streaming via JWPlatform', default=True, blank=True
    )
    streaming_username = models.CharField(
        max_length=255, blank=True, null=True
    )
    streaming_password = models.CharField(max_length=25, blank=True, null=True)
    streaming_key = models.CharField(max_length=25, blank=True, null=True)
    streaming_secret = models.CharField(max_length=255, blank=True, null=True)

    email_provider_username = models.CharField(
        max_length=255, blank=True, null=True
    )
    email_provider_password = models.CharField(
        max_length=255, blank=True, null=True
    )
    email_provider_reply_email = models.EmailField(blank=True, null=True)
    address_bar_sharing = models.BooleanField(default=False)
    template_version = models.CharField(max_length=25, blank=True, default='0')

    def attachments(self, manager):
        """Gather attachments.

        Recurse through the object's ancestors to gather attachments of
        each of them.

        FIXME: does not work for unsaved objects"""

        return dict((item.name, item) for item in manager.all())

    def context(self):
        """Campaign-wide template context"""

        # All model fields
        context = model_to_dict(self)

        context['images'] = self.attachments(self.images)
        context['media'] = self.attachments(self.media)
        context['text'] = self.attachments(self.text)
        context['offers'] = self.offers.all()

        return context

    def botr(self):
        """BoTR client connection."""
        from botr.api import API

        key = self.streaming_key or settings.BOTR_KEY
        secret = self.streaming_secret or settings.BOTR_SECRET

        return API(key, secret)

    def shares_by_service(self, start_date, end_date):
        shares = self.shares.filter(
            date__gte=start_date,
            date__lte=end_date
        ).values('service', 'count') \
            .annotate(total=models.Sum('count')).values('service', 'total')
        return dict((s['service'], s['total']) for s in shares)

    def get_video_template(self):
        return self.video_template or self.type.video_template

    @property
    def is_idomoo_backend(self):
        template = self.get_video_template()
        return template.startswith('idomoo')

    class Meta:
        unique_together = ('name', 'company')
        ordering = ['name']

    def __str__(self):
        return self.name


class CampaignImage(models.Model):
    """Campaign-bound image."""

    NAMES = (
        ('dealer_image', 'Dealer Image'),
        ('dealer_image_2', 'Dealer Image 2'),
        ('dealer_storefront', 'Dealer Storefront'),
    )
    campaign = models.ForeignKey(Campaign, related_name='images')
    name = models.SlugField(max_length=64, choices=NAMES)
    image = models.ImageField(upload_to='campaigns/images')

    def __str__(self):
        return urlsafe(settings.LIVE_MEDIA_URL + str(self.image))

    class Meta:
        unique_together = ('campaign', 'name')


class CampaignMedia(models.Model):
    """Campaign-bound media file."""

    NAMES = (
        ('background', 'Background'),
        ('intro_video', 'Intro Video'),
        ('final_video', 'Final Video'),
        ('soundtrack', 'Soundtrack'),
    )
    campaign = models.ForeignKey(Campaign, related_name='media')
    name = models.SlugField(max_length=64, choices=NAMES)
    file = models.FileField(upload_to='campaigns/media')
    duration = models.FloatField(blank=True, null=True, editable=False)

    class Meta:
        unique_together = ('campaign', 'name')
        verbose_name_plural = _('Compaign media files')

    def __str__(self):
        return urlsafe(settings.LIVE_MEDIA_URL + str(self.file))

    def clean(self):
        if self.name in ('intro_video', 'final_video'):
            try:
                temp_path = getattr(
                    self.file.file, 'temporary_file_path', None
                )
                filepath = temp_path and temp_path() or self.file.path
                self.duration = find_video_duration(filepath)
            except Exception as e:
                raise ValidationError(
                    {'file': 'Wrong video file: {}'.format(e)}
                )
        else:
            self.duration = None


class CampaignText(models.Model):
    """Campaign-bound text string."""

    NAMES = (
        ('welcome', 'Welcome'),
        ('slogan', 'Slogan'),
        ('closing', 'Closing'),
    )

    campaign = models.ForeignKey(Campaign, related_name='text')
    name = models.SlugField(max_length=64, choices=NAMES)
    value = models.CharField(max_length=512)

    def __str__(self):
        return self.value

    class Meta:
        unique_together = ('campaign', 'name')
        verbose_name_plural = _('Compaign text strings')


class Contact(CompanyBoundModel):
    """A sales contact"""

    TYPES = (
        ('staff', 'Staff'),
        ('manager', 'Manager'),
    )

    name = models.CharField(max_length=100, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    title = models.CharField(max_length=100, blank=True)
    type = models.CharField(
        max_length=100, default='staff', choices=TYPES, db_index=True
    )
    email = models.EmailField(blank=True, db_index=True)
    # phone = models.CharField(max_length=20, blank=True)
    phone = PhoneNumberField(blank=True)
    businesscard_photo = models.ImageField(
        'Business card photo',
        blank=True, null=True,
        upload_to='businesscards'
    )
    photo = models.ImageField(
        'Personal photo', blank=True, upload_to='contacts/photo/'
    )

    def __str__(self):
        if not self.email:
            return self.name
        else:
            return '%s <%s>' % (
                self.name,
                self.email
            )

    class Meta:
        unique_together = ('name', 'company')


# Possible statuses of a package
PACKAGE_STATUS_VALUES = (
    ('starting', 'Starting'),
    ('preparation', 'Preparation'),
    ('pending', 'Incoming'),
    ('skipped', 'Skipped'),
    ('void', 'Void'),
    ('approved', 'Approved'),
    ('ready', 'Ready for production'),
    ('erroneus', 'Error'),
    ('production', 'In production'),
    ('storage', 'Saving to cloud'),
    ('produced', 'Produced'),
    ('sending', 'Sending'),
    ('sent', 'Sent'),
    ('archived', 'Archived'),
    ('suppressed', 'Suppressed'),
    ('bounced', 'Bounced'),
    ('duplicate', 'Sent'),
)

# Package events
(
    ADDITION, CHANGE, DELETION,
    RESERVED,  # For backward compatibility
    ERROR, SKIP, VOID,
    APPROVE, MASK,
    PRODUCE, STORE, PUBLISH,
    SEND, BOUNCE, VIEW_EMAIL, VIEW_LANDING
) = range(1, 17)


def get_uuid():
    return str(uuid.uuid4())


def hex_uuid4():
    return uuid.uuid4().hex


def remove_file_when_delete_object(file_path):
    logger.info('delete related files to Package: %s' % file_path)
    if file_path in [None, '', 'None', 'none']:
        return
    if os.path.isfile(file_path) and os.path.exists(file_path):
        os.remove(file_path)
        try:
            img_directory = '/'.join(file_path.split('/')[:-1])
            os.rmdir(img_directory)
            img_directory = '/'.join(file_path.split('/')[:-2])
            os.rmdir(img_directory)
        except:
            pass


class ImageQuerySet(QuerySet):
    def delete(self, *args, **kwargs):
        for obj in self:
            obj.delete()
        super(ImageQuerySet, self).delete(*args, **kwargs)


class Package(ConcurrentModel):
    """Data Package submitted from client app"""
    objects = ImageQuerySet.as_manager()

    company = models.ForeignKey(Company, related_name='packages')

    contact = models.ForeignKey(
        Contact, related_name='packages',
        blank=True, null=True,
        on_delete=models.SET_NULL
    )

    campaign = models.ForeignKey(
        Campaign, blank=True, null=True, related_name='packages'
    )

    product_keywords = models.CharField(
        'Product Keywords', max_length=512, default='',
        help_text='Comma-separated keywords: product description'
    )

    geo_keywords = models.CharField(
        'Geo Keywords', max_length=512, default='',
        help_text='Comma-separated keywords: geography description'
    )

    status = models.CharField(
        default='pending', max_length=100, choices=PACKAGE_STATUS_VALUES,
        db_index=True
    )
    queued_until = models.DateTimeField(blank=True, null=True)

    recipient_name = models.CharField(
        'Recipient name', max_length=100, blank=True, db_index=True
    )
    recipient_email = models.EmailField(
        'Recipient email', blank=True, db_index=True
    )
    recipient_phone = models.CharField(
        max_length=20, blank=True, db_index=True
    )
    recipient_permission = models.BooleanField(default=False, db_index=True)
    recipient_signature = ImageField(
        upload_to='packages/signatures', blank=True, null=True
    )
    copy_email = models.EmailField('Email #2', blank=True)

    # recipient_review = models.OneToOneField(
    # 'PackageReview', related_name='package', blank=True, null=True)

    landing_page_key = models.CharField(
        max_length=32, unique=True, null=True,
        help_text='Unique landing page URL key.'
    )
    landing_page_url = models.CharField(max_length=512, blank=True)

    asset = models.URLField(blank=True)
    asset_tracking_link = models.URLField(blank=True)

    stupeflix_key = models.CharField(
        'Stupeflix task key', max_length=255, blank=True
    )
    video_key = models.CharField('Video key', max_length=10, blank=True)

    created_time = models.DateTimeField(blank=True, null=True, db_index=True)
    submitted_time = models.DateTimeField(auto_now_add=True, db_index=True)
    last_mailed = models.DateTimeField(blank=True, null=True, db_index=True)

    # Debug fields
    company_key = models.CharField(max_length=255, blank=True, null=True)
    company_name = models.CharField(max_length=255, blank=True, null=True)
    campaign_key = models.CharField(max_length=255, blank=True, null=True)

    # Stats
    visitors = models.PositiveIntegerField(
        default=0, help_text='Unique visitors (from Google Analytics)',
        db_index=True
    )
    email_views = models.PositiveIntegerField(
        'Email', default=0, db_index=True
    )
    landing_views = models.PositiveIntegerField(
        'Landing', default=0, db_index=True
    )
    photo_downloads = models.PositiveIntegerField(
        'Photos', default=0, db_index=True
    )
    page_views = models.PositiveIntegerField(
        'Page', default=0, help_text='Total count of video player embeds',
        db_index=True
    )
    video_views = models.PositiveIntegerField(
        'Video', default=0, help_text='Total video downloads and streams',
        db_index=True
    )
    viewed_time = models.PositiveIntegerField(
        default=0, help_text='Total watching time in seconds', db_index=True
    )
    shares = models.PositiveIntegerField(
        default=0, help_text='Total shares count', db_index=True
    )

    website_views = models.PositiveIntegerField(
        'Website clicks', default=0, db_index=True
    )
    review_site_views = models.PositiveIntegerField(
        'Review site clicks', default=0, db_index=True
    )
    social_site_views = models.PositiveIntegerField(
        'Social site clicks', default=0, db_index=True
    )
    offer_recipient_views = models.PositiveIntegerField(
        'Recipient offer clicks', default=0, db_index=True
    )
    offer_others_views = models.PositiveIntegerField(
        'Others offer clicks', default=0, db_index=True
    )

    version = AutoIncVersionField()
    session = models.CharField(max_length=24, blank=True, null=True)

    user_agent = models.CharField(max_length=512, blank=True, db_index=True)

    def delete(self, using=None):
        logger.info('---image package delete method caled--------')
        links = [rel.get_accessor_name() for rel in self._meta.get_all_related_objects()]
        for link in links:
            for related_obj in getattr(self, link).all():
                related_obj.delete()
        # Remove package files
        img_path = self.absolute_recipient_signature_path()
        remove_file_when_delete_object(img_path)
        cropped_thumbnails = self.cropped_thumbnail_absolute_path()
        remove_file_when_delete_object(cropped_thumbnails)
        video_path = self.video_path()
        remove_file_when_delete_object(video_path)
        if self.thumbnail():
            try:
                photo_thumbnail_path = self.photo_thumbnail_path()
                remove_file_when_delete_object(photo_thumbnail_path)
            except:
                pass

        super(ConcurrentModel, self).delete(using)

    def true_recipient_signature_image_path(self):
        stored_path = str(self.recipient_signature)
        true_path = stored_path
        if stored_path.startswith('/package') or stored_path.startswith('package'):
            true_path = '/'.join(stored_path.split('/')[1:])
        return true_path

    def absolute_recipient_signature_path(self):
        return os.path.join(
            settings.MEDIA_ROOT,
            self.true_recipient_signature_image_path()
        )

    def get_landing_page_url(self):

        return os.path.join(
            settings.VBOOSTLIVE_URL,
            self.landing_page_url.lstrip('/')
        )

    def is_duplicate(self):
        """
        The buggy mobile app sometimes throws in duplicate packages.
        We must find them.
        """
        candidates = Package.objects.filter(
            contact=self.contact,
            company=self.company,
            campaign=self.campaign,

            recipient_email=self.recipient_email,
            recipient_phone=self.recipient_phone,
            id__lt=self.id,
        ).exclude(
            status='duplicate'
        )

        try:
            if candidates:
                first_photo_size = self.images.first().image.size
                for candidate in candidates:
                    try:
                        if candidate.images.first().image.size \
                                == first_photo_size:
                            return True
                    except OSError:
                        pass

        except AttributeError:
            pass

        return False

    def viewed_duration(self):
        return str(datetime.timedelta(seconds=self.viewed_time))

    viewed_duration.short_description = 'Watched'
    viewed_duration.admin_order_field = 'viewed_time'

    @allow_tags
    def current_status(self):
        obj = self

        status = obj.status

        now = datetime.datetime.now()

        if status == 'erroneus':
            return '<span class="errornote">%s</span>' % obj.last_error()

        elif status == 'storage' \
                and obj.queued_until \
                and obj.queued_until > now:
            return '%s (queued for %s sec)' % (
                dict(PACKAGE_STATUS_VALUES).get(status, status),
                (obj.queued_until - now).seconds
            )

        else:
            return dict(PACKAGE_STATUS_VALUES).get(status, status)

    def last_error(self):
        return getattr(
            self.events.filter(type='error').last(), 'message', None
        )

    def context(self):
        """Package context."""

        context = model_to_dict(self)

        # Package images
        context['images'] = self.images.filter(
            is_skipped=False,
            image__isnull=False,
        ).exclude(image='').order_by('inline_ordering_position')

        # Campaign images
        context['campaign_images'] = self.images.filter(
            is_skipped=False,
            campaign__isnull=False,
            image__isnull=False,
        ).exclude(image='').order_by('inline_ordering_position')

        # Thumbnail image
        try:
            context['thumb'] = self.thumbnail()
            context['cropped_thumb'] = self.cropped_thumbnail()
            context['photo_thumb'] = self.photo_thumbnail()
        except PackageImage.DoesNotExist:
            context['thumb'] = None
            context['cropped_thumb'] = None

        # Plain images
        context['plain_images'] = list(self.images.filter(
            is_skipped=False,
            campaign__isnull=True,
            is_thumbnail=False,
            image__isnull=False,
        ).exclude(image='').order_by('inline_ordering_position'))

        # Linked data
        context['campaign'] = self.campaign.context()
        context['company'] = self.company

        context['contact'] = self.contact
        context['MEDIA'] = 'https://vboostoffice.com/media'

        context['landing_page_url'] = self.get_landing_page_url()
        context['tracking_pixel'] = self.tracking_pixel()

        context['unsubscribe_url'] = self.unsubscribe_url()

        context['get_thumbnail'] = get_thumbnail
        context['video'] = self.video_url()

        return context

    def render_video_template(self):
        template_name = 'video/{}.xml'.format(
            self.campaign.get_video_template()
        )

        template = loader.get_template(template_name)
        return template.render(self.context())

    def unsubscribe_url(self):
        return 'https://vboostlive.com/unsubscribe/%s/' % self.landing_page_key

    def generate_keywords(self):
        """We generate some product and geo keywords."""

        def select(keywords, n):
            keyword_list = [keyword.strip() for keyword in keywords.split(',')]

            if n > len(keyword_list):
                # Avoid "sample larger than population" error
                return keyword_list
            else:
                indices = random.sample(range(len(keyword_list)), n)
                return [keyword_list[i] for i in sorted(indices)]

        return (
            ','.join(select(self.company.keywords1, 3)),  # Product
            ','.join(select(self.company.keywords2, 2))  # Geo
        )

    def geo_keywords_list(self):
        return [kw.strip() for kw in self.geo_keywords.split(',')]

    def get_product_keywords_display(self):
        keywords = [kw.strip() for kw in self.product_keywords.split(',')]

        return ', '.join(keywords[:-1]) \
               + (', ' if len(keywords) > 2 else '') \
               + ' and ' + keywords[-1]

    def generate_landing_page_url(self):
        """URL of the landing page."""

        prerequisites = {
            'landing page key': self.landing_page_key,
            'company slug': self.company.slug,
            'first company keywords': self.product_keywords,
            'second company keywords': self.geo_keywords,
        }

        if not all(prerequisites.values()):
            raise Exception(
                'Cannot generate landing page URL. Please check %s.'
                % ', '.join(
                    [key for key, value in prerequisites.items() if not value]
                ))

        return '{slug}/{geo_keywords}/{product_keywords}/{key}/'.format(
            slug=self.company.slug.lower().replace(' ', '-'),
            geo_keywords=self.geo_keywords.lower().replace(' ', '-')
                .replace(',', '-'),
            product_keywords=self.product_keywords.lower().replace(' ', '-')
                .replace(',', '/'),
            key=self.landing_page_key
        )

    def thumbnail(self):
        prefetch_thumbnails = getattr(self, 'prefetch_thumbnails', None)
        if prefetch_thumbnails:
            return next(iter(prefetch_thumbnails))
        return self.images.filter(is_thumbnail=True).first()

    cover = property(thumbnail)

    def cropped_thumbnail(self):
        return urlsafe(settings.LIVE_MEDIA_URL + '/'.join((
            'thumbnails',
            str(self.company.id),
            str(self.campaign.id),
            '%s.jpg' % self.id,
        )))

    def cropped_thumbnail_absolute_path(self):
        return os.path.join(
            settings.MEDIA_ROOT,
            'thumbnails',
            str(self.company.id),
            str(self.campaign.id),
            '%s.jpg' % self.id,
        )

    def video_path(self):
        if self.stupeflix_key:
            return os.path.join(
                settings.MEDIA_ROOT,
                'videos',
                self.stupeflix_key[:2],
                self.stupeflix_key[2:4],
                '{}.mp4'.format(self.stupeflix_key)
            )

    def video_url(self):
        if self.stupeflix_key:
            # here should be MEDIA_URL instead LIVE_MEDIA_URL
            return urlsafe(settings.MEDIA_URL + '/'.join([
                'videos',
                self.stupeflix_key[:2],
                self.stupeflix_key[2:4],
                '{}.mp4'.format(self.stupeflix_key)
            ]))

    def photo_thumbnail_path(self):
        return self.thumbnail().masked_thumbnail_path()

    def photo_thumbnail(self):
        thumb = self.thumbnail()
        if thumb:
            return thumb.masked_thumbnail_url()

        else:
            pass

    def __init__(self, *args, **kwargs):
        super(Package, self).__init__(*args, **kwargs)
        self._initial_campaign_id = self.campaign_id
        self._initial_status = self.status

    def error(self, exception=None):
        """Package is erroneus."""

        # Adding a history record
        self.create_event('error', str(exception))

        Package.objects.filter(
            id=self.id
        ).update(
            status='erroneus'
        )

    def tracking_pixel(self):
        return mark_safe(
            '<img src="https://vboostlive.com/tracking/%s/" alt="" />') \
               % self.landing_page_key

    def create_event(self, type, description=None, user=None, ip=None,
                     date=None):
        """Add an event."""

        if not date:
            date = datetime.datetime.now()

        return self.events.create(
            type=type,
            user=user,
            description=description,
            ip=ip,
            time=date
        )

    def can_produce(self):
        return self.status not in (
            'preparation', 'pending',
            'approved', 'ready', 'production', 'storage'
        )

    @property
    def viral_lift(self):
        if self.landing_views:
            return float(self.video_views) / self.landing_views * 100

    def set_status(self, status):
        self.status = status
        self.__class__.objects.filter(
            id=self.id
        ).update(
            status=status
        )

    class Meta:
        get_latest_by = 'submitted_time'

    def __str__(self):
        try:
            return u'Package #%s by %s at %s' % (
                self.id, self.contact, self.campaign
            )
        except:
            return 'Package %s' % self.id


def get_image_path(instance, filename):
    """Package image path"""

    package_id = instance.package.id
    company_id = instance.package.company.id

    path = time.strftime('images/{0}/{1}/%y/%m/%d/{2}') \
        .format(company_id, package_id, filename)

    return path


class PackageImage(Orderable, ConcurrentModel):
    """Customer image"""

    IMAGE_ANGLE_VALUES = (
        (0, 'No rotation'),
        (-90, 'Rotate Counter-clockwise'),
        (90, 'Rotate Clockwise'),
        (180, 'Upside Down'),
    )

    campaign = models.ForeignKey(Campaign, blank=True, null=True)

    package = models.ForeignKey(Package, related_name='images')
    name = models.CharField(blank=True, max_length=512)

    image = models.ImageField(
        upload_to=get_image_path, blank=True, null=True, db_index=True
    )
    original = models.ImageField(blank=True)

    is_skipped = models.BooleanField('Skip', default=False, db_index=True)
    is_thumbnail = models.BooleanField('Thumb', default=False, db_index=True)

    # Mask coordinates
    x1 = models.IntegerField(null=True, blank=True)
    y1 = models.IntegerField(null=True, blank=True)
    x2 = models.IntegerField(null=True, blank=True)
    y2 = models.IntegerField(null=True, blank=True)

    # Rotation
    angle = models.IntegerField(default=0, choices=IMAGE_ANGLE_VALUES)

    created = models.DateTimeField(auto_now_add=True)

    version = AutoIncVersionField()

    def get_masked_thumbnail(self):
        mask_image = self.package.campaign.type.mask.image

        if mask_image:
            size = '{im.width}x{im.height}'.format(im=mask_image)
            return get_thumbnail(
                self.image.path, size,
                crop='faces',
                overlay=mask_image.path,
                overlay_mode='mask'
            )

    def delete(self, using=None):
        img_path = self.absolute_path()
        remove_file_when_delete_object(img_path)

        thumbnail_path = self.masked_thumbnail_path()
        remove_file_when_delete_object(thumbnail_path)

        facebook_thumbnail_path = self.facebook_thumbnail_path()
        remove_file_when_delete_object(facebook_thumbnail_path)
        super(PackageImage, self).delete(using)

    @property
    def is_cover(self):
        return self.is_thumbnail

    def path(self):
        return str(self.image)

    def absolute_path(self):
        return os.path.join(
            settings.MEDIA_ROOT,
            self.path()
        )

    def __init__(self, *args, **kwargs):
        super(PackageImage, self).__init__(*args, **kwargs)
        self._initial_angle = self.angle

    def save(self, *args, **kwargs):
        """Rotating image."""

        if self.angle != self._initial_angle:
            filename_only, filename_ext = os.path.splitext(self.image.name)
            if not self.original:
                self.original = filename_only + '_orig' + filename_ext
                orig = Image.open(self.image.file)
                orig.save(self.original.path)

            if self.angle:
                image = Image.open(self.original.file) \
                    .rotate(-self.angle, expand=1)
                new_path = self.original.path
                new_path = new_path.replace('_orig', str(self.angle), 1)
                image.save(new_path)
                self.image = os.path.relpath(new_path, settings.MEDIA_ROOT)
            else:
                self.image = self.original.name.split('_')[0] + filename_ext

            # To prevent recurring rotation on consecutive save() invocations
            self._initial_angle = self.angle

        super(PackageImage, self).save(*args, **kwargs)

    def width(self):
        return self.image.width

    def height(self):
        return self.image.height

    def masked_thumbnail_path(self):
        return self.absolute_path().replace('images', 'photo-thumbnails')

    def masked_thumbnail_url(self):
        return settings.LIVE_MEDIA_URL + self.path() \
            .replace('images', 'photo-thumbnails')

    def facebook_thumbnail_path(self):
        return self.absolute_path().replace('images', 'facebook-thumbnails')

    def facebook_thumbnail_url(self):
        return settings.LIVE_MEDIA_URL + self.path() \
            .replace('images', 'facebook-thumbnails')

    def __str__(self):
        # return urlsafe(settings.LIVE_MEDIA_URL + self.path())
        return urlsafe(settings.MEDIA_URL + self.path())

    class Meta:
        get_latest_by = 'created'
        ordering = ['package', 'inline_ordering_position']


class EventManager(models.Manager):
    def _is_bot(self, request):
        BOTS = [
            'Googlebot', 'Slurp', 'Twiceler', 'msnbot', 'KaloogaBot',
            'YodaoBot', 'Baiduspider', 'googlebot', 'Speedy Spider', 'DotBot',
            'spider', 'crawler', 'yandex', 'bingbot', 'MJ12bot',
            'MegaIndex.ru', 'ia_archiver',

            # Social share agents
            'facebookexternalhit', 'vkShare', 'AddThis',
            'Slackbot', 'SkypeUriPreview'
        ]

        user_agent = request.META.get('HTTP_USER_AGENT', '')

        return any(bot.lower() in user_agent.lower() for bot in BOTS)

    def try_create_event(self, **kwargs):
        request = kwargs.pop('request')

        if not self._is_bot(request):
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            kwargs.update({
                'ip': user_ip(request),
                'user_agent': user_agent
            })

            if 'bot' in user_agent.lower() or 'crawler' in user_agent.lower():
                logger.info('Possible bot or crawler: %s', user_agent)

            return self.create(**kwargs)


class Event(models.Model):
    """Package-related event."""

    TYPES = (
        ('publish', 'Package is produced successfully'),
        ('error', 'Error'),
        ('email', 'Email is sent out'),

        ('open_email', 'Email is opened'),
        ('open_landing', 'Landing page is opened'),

        ('video', 'Video is played'),
        ('share', 'Landing page is shared'),

        ('suppress_email', 'Email is not sended because of unsubscribe lists'),
        ('unsubscribe', 'Unsubscribe from futher communications'),

        ('bounce', 'Bounce notification'),
        ('info', 'Misc info'),

        ('visit', 'Visit a linked site')
    )

    COUNTERS = {
        'share': 'shares',
        'open_email': 'email_views',
        'open_landing': 'landing_views',
    }

    package = models.ForeignKey(Package, related_name='events')
    user = models.ForeignKey(
        User, related_name='events', blank=True, null=True
    )
    type = models.CharField(max_length=255, choices=TYPES, db_index=True)
    description = models.TextField(blank=True, null=True)
    time = models.DateTimeField(blank=True, null=True)

    duration = models.PositiveSmallIntegerField(blank=True, null=True)
    service = models.CharField(max_length=128, blank=True)

    user_agent = models.TextField(blank=True)
    ip = models.GenericIPAddressField(blank=True, null=True)

    objects = EventManager()

    @property
    def type_code(self):
        return self.type.capitalize().replace('_', ' ')

    @property
    def type_name(self):
        return dict(self.TYPES).get(self.type, None)

    @property
    def message(self):
        return self.description or self.type_name

    def delete(self, using=None):
        return super(Event, self).delete();

    def save(self, *args, **kwargs):
        """Time by default"""

        # Pre save
        if not self.time:
            self.time = datetime.datetime.now()

        super(Event, self).save(*args, **kwargs)

        # Post save triggers
        if self.type == 'video':
            video_events = Event.objects.filter(
                package_id=self.package_id, type='video'
            )
            Package.objects.filter(id=self.package_id).update(
                video_views=max(
                    video_events.count(),
                    self.package.video_views
                ),
                viewed_time=max(
                    video_events.filter(
                        duration__isnull=False
                    ).aggregate(total=models.Sum('duration'))['total'] or 0,
                    self.package.viewed_time
                )
            )

        elif self.type == 'visit':
            counter_field = '{}_views'.format(self.service)
            Package.objects.filter(id=self.package_id).update(**{
                counter_field: Event.objects.filter(
                    package_id=self.package_id,
                    type=self.type,
                    service=self.service
                ).count()
            })

        elif self.type in self.COUNTERS:
            counter_field = self.COUNTERS[self.type]
            Package.objects.filter(id=self.package_id).update(**{
                counter_field: Event.objects.filter(
                    package_id=self.package_id,
                    type=self.type
                ).count()
            })

    def __str__(self):
        return '<Event %s: %s>' % (
            self.type,
            self.message
        )

    class Meta:
        ordering = ('time',)


class ServiceShare(models.Model):
    date = models.DateField()
    campaign = models.ForeignKey(Campaign)
    service = models.CharField(max_length=64)
    count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('date', 'campaign', 'service')


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)

