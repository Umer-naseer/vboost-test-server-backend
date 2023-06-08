from mailer.utils import validate_email_list

from django import forms


class CampaignForm(forms.ModelForm):
    def clean_email_managers(self):
        value = self.cleaned_data['email_managers']

        validate_email_list(value)

        return value
