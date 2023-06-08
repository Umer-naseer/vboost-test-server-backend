from clients.models import Company
from django.forms import ModelForm
from django.forms.util import ErrorList
from mailer.fields import EmailListField, validate_email_list
from .utils import contacts_for_company
from recurrent import RecurringEvent


class ContactForm(ModelForm):
    more_contacts = EmailListField(
        max_length=512, required=False,
        help_text='One email per line. Commas and semicolons are okay as well.'
    )

    def __init__(self, *args, **kwargs):
        """Limit contact list to the company selected."""

        super(ContactForm, self).__init__(*args, **kwargs)

        data = args[0] if args else None

        self._send = '_send' in args[0] if args else False

        # What company are we reporting for?
        # Maybe it is in the form.
        try:
            company = Company.objects.get(id=data['company'])
        except Exception as exc:

            # Okay, looking in instance.
            try:
                company = kwargs['instance'].company
            except (KeyError, AttributeError, Company.DoesNotExist):
                company = None

        self.fields['contacts'].queryset = contacts_for_company(company)

        self.fields['company'].queryset = \
            Company.objects.all().order_by('name')

    def clean(self):
        cleaned_data = super(ContactForm, self).clean()

        # End date must be not less than start date
        date_to = cleaned_data.get('date_to', None)
        date_from = cleaned_data.get('date_from', None)
        if date_from and date_to and date_from > date_to:
            self.errors['date_from'] = self.errors['date_to'] = ErrorList([
                'End date must be not less than start date.'
            ])

        # What if the same email appears twice?
        try:
            repeated_contacts = \
                set(c.email for c in cleaned_data['contacts']) \
                & set(validate_email_list(cleaned_data['more_contacts']))

            if repeated_contacts:
                self.errors['__all__'] = ErrorList([
                    '%s will receive the report twice as it is listed both '
                    'in contact list and in "More contacts" field.'
                    % ', '.join(repeated_contacts)
                ])
        except (KeyError, TypeError):
            pass

        if self._send and not cleaned_data.get('contacts', None) \
                and not cleaned_data.get('more_contacts', None):
            self.errors['__all__'] = ErrorList([
                'Please define at least one email address where to send '
                'the report.'
            ])

        return cleaned_data


class ScheduleForm(ContactForm):
    def clean(self):
        cleaned_data = super(ScheduleForm, self).clean()

        if 'pattern' in cleaned_data:
            if RecurringEvent().parse(cleaned_data['pattern']) is None:
                self.errors['pattern'] = ErrorList([
                    'The pattern cannot be parsed. Please see '
                    'the documentation.'
                ])

        return cleaned_data
