from django import forms

from config.forms import GlassFormMixin

from .models import ImpactRecord


class ImpactRecordForm(GlassFormMixin, forms.ModelForm):
    class Meta:
        model = ImpactRecord
        fields = ["amount_value", "notes"]
        labels = {"amount_value": "Value"}
