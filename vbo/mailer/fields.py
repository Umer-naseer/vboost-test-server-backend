from django.forms import CharField, Textarea
from .utils import validate_email_list


class EmailListField(CharField):
    """Multiple emails field.
    https://djangosnippets.org/snippets/1958/"""

    widget = Textarea

    def clean(self, value):
        validate_email_list(value, required=self.required)

        return super(EmailListField, self).clean(value)
