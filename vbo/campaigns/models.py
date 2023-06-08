from django_enumfield import enum
from adminsortable.models import Sortable, SortableForeignKey

from django.db import models
from django.template.loader import get_template


class LandingTemplate(enum.Enum):
    DEFAULT = 0

    labels = {
        DEFAULT: 'Default Landing Template',
    }


class SMSTemplate(enum.Enum):
    DEFAULT = 0

    labels = {
        DEFAULT: 'Default SMS Template',
    }


class EmailTemplate(enum.Enum):
    DEFAULT = 0
    BLANK = 1

    labels = {
        DEFAULT: 'Default Email Template',
        BLANK: 'Blank Email Template',
    }


VIDEO_TEMPLATE_CHOICES = (
    (
        'Stupeflix',
        (
            ('default', 'Stupeflix Default'),
            ('mylead', 'Stupeflix MyLead'),
        )
    ),
    (
        'Idomoo',
        (
            ('idomoo_mylead1', 'Idomoo My Lead 1'),
            ('idomoo_myride1', 'Idomoo My Ride 1'),
        )
    )
)


class CampaignType(Sortable):
    CATEGORY_CHOICES = (
        ('myride', 'My Ride'),
        ('mylead', 'My Lead'),
        ('mycustomer', 'My Customer'),
        ('myshow', 'My Showroom'),
    )

    COLOR_CHOICES = [
        ('FF0000', 'Red'),
        ('FFAA00', 'Orange'),
        ('FFFF00', 'Yellow'),
        ('91C43B', 'Green'),
        ('0000FF', 'Blue'),
        ('00FFFF', 'Purple'),
    ]

    # Basic
    name = models.CharField(max_length=64, unique=True)
    category = models.CharField(
        max_length=64,
        choices=CATEGORY_CHOICES,
        null=True,
        blank=True,
        db_index=True,
    )

    mask = models.ForeignKey('gallery.Mask', null=True, blank=True)

    # Templates
    landing_template = enum.EnumField(
        LandingTemplate,
        default=LandingTemplate.DEFAULT,
    )
    sms_template = enum.EnumField(SMSTemplate, default=SMSTemplate.DEFAULT)
    email_template = enum.EnumField(
        EmailTemplate,
        default=EmailTemplate.DEFAULT,
    )

    video_template = models.CharField(
        max_length=128,
        default='default',
        choices=VIDEO_TEMPLATE_CHOICES,
    )

    # Photo taking parameters in the mobile application
    min_count = models.PositiveSmallIntegerField(default=0)
    max_count = models.PositiveSmallIntegerField(default=6)
    default_count = models.PositiveSmallIntegerField(default=4)

    color = models.CharField(
        max_length=16, choices=COLOR_CHOICES,
        blank=True, null=True
    )

    class Meta:
        verbose_name = 'campaign type'
        verbose_name_plural = 'campaign types'

    def __str__(self):
        return self.name

    @property
    def landing_template_name(self):
        return LandingTemplate.name(self.landing_template).lower()

    def render(self, prefix, context={}):
        fields = {
            'sms': 'sms_template',
            'email': 'email_template',
            'landing': 'landing_template',
        }
        if prefix not in fields:
            raise ValueError('Prefix {} is not allowed'.format(prefix))
        field_name = fields[prefix]
        template_name = self._meta.get_field(field_name)\
            .enum.name(getattr(self, field_name)).lower()
        template = get_template('{}/{}.jinja'.format(prefix, template_name))
        return template.render(context)


class CampaignTypeImage(Sortable):
    type = SortableForeignKey('campaigns.CampaignType', related_name='images')
    name = models.SlugField(max_length=24, help_text='Internal name.')
    title = models.CharField(max_length=24, help_text='Human-readable name.')

    class Meta(Sortable.Meta):
        unique_together = [
            ('type', 'name'),
            ('type', 'title'),
        ]

    def __str__(self):
        return self.title
