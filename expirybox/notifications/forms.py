from django import forms
from django.utils import timezone

from config.forms import DateInput, GlassFormMixin

from .models import Reminder


class ReminderForm(GlassFormMixin, forms.ModelForm):
    class Meta:
        model = Reminder
        fields = ["reminder_date"]
        widgets = {"reminder_date": DateInput()}
        labels = {"reminder_date": "Remind me on"}

    def __init__(self, *args, item=None, **kwargs):
        self.item = item
        super().__init__(*args, **kwargs)

    def clean_reminder_date(self):
        d = self.cleaned_data["reminder_date"]
        if d < timezone.localdate():
            raise forms.ValidationError("Pick today or a later date.")
        if self.item and d > self.item.expiry_date:
            raise forms.ValidationError("Pick a date on or before the expiry date.")
        return d
