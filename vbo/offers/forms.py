from .models import Submission

from django import forms


class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = '__all__'
