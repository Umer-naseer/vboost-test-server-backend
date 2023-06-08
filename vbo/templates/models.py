from sorl.thumbnail import get_thumbnail
from django.db import models
import jinja2


class DatabaseTemplateLoader(jinja2.BaseLoader):
    """Load template from database by key."""

    def __init__(self, model_class):
        """Store the table to get data from."""

        self.model_class = model_class

    def get_source(self, environment, key):
        """Get the desired template by key."""

        try:
            instance = self.model_class.objects.get(
                key=key
            )
        except self.model_class.DoesNotExist:
            raise jinja2.TemplateNotFound(key)

        last_modified = instance.last_modified

        return \
            instance.template, \
            key,\
            lambda: last_modified == \
                    self.model_class.objects.get(key=key).last_modified


class BaseTemplate(models.Model):
    """An abstract template model."""

    name = models.CharField(
        max_length=255, unique=True, help_text='Human-readable template name.')
    key = models.SlugField(
        max_length=255, unique=True,
        help_text='Unique key to reference a template.')
    template = models.TextField(help_text='Template text.')
    last_modified = models.DateTimeField(auto_now=True)

    def render(self, context=None):
        """Jinja2 template render"""

        if context is None:
            context = {}

        context.update({
            'get_thumbnail': get_thumbnail
        })

        env = jinja2.Environment(
            loader=DatabaseTemplateLoader(self.__class__),
            extensions=['jinja2.ext.with_']
        )

        # Now it is very ugly... but cannot figure out another way.
        template = env.get_template(self.key)

        return template.render(context)

    def __str__(self):
        return self.name

    class Meta:
        abstract = True


class Template(BaseTemplate):
    """Generic template."""

    TYPES = (
        ('landing', 'Landing page'),
        ('offer-email', 'Email (redeem offer)'),
        ('offer-notification-email', 'Email (notify about offer)'),
        ('package-notification-email', 'Email (package notification)'),
        ('offer', 'Offer'),
        ('offer-redeem', 'Offer redeem page'),
        ('snippet', 'Snippet'),
        ('help', 'Help Text'),
    )

    type = models.CharField(max_length=32, choices=TYPES)

    def related(self):
        """List of campaigns using this template."""

        return {
            'package-notification-email': self.using_email_notification,
            'offer-redeem': self.using_offer_redeem,
        }.get(self.type)


class VideoTemplate(BaseTemplate):
    pass


class LandingTemplate(BaseTemplate):
    pass


class EmailTemplate(BaseTemplate):
    pass
