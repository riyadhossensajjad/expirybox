from django import forms
from django.utils import timezone

from config.forms import DateInput, GlassFormMixin, PhotoFieldMixin

from .models import Item


class ItemForm(PhotoFieldMixin, GlassFormMixin, forms.ModelForm):
    class Meta:
        model = Item
        fields = [
            "item_name", "category", "price", "expiry_date", "purchase_date",
            "provider", "reference_number", "description", "image",
        ]
        widgets = {"expiry_date": DateInput(), "purchase_date": DateInput()}
        labels = {"item_name": "Name", "reference_number": "Batch or receipt no."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].empty_label = "Choose a category"
        self.fields["item_name"].widget.attrs["placeholder"] = "e.g. Greek yogurt, 500 g"
        price = self.fields["price"]
        price.required = True
        price.min_value = 0
        price.help_text = "What you paid. Used as the original price when you sell it, and for your impact totals."
        price.widget.attrs.update({"step": "0.01", "min": "0", "inputmode": "decimal", "placeholder": "0"})
        if not self.instance.pk:
            self.initial.setdefault("price", None)

    def clean(self):
        data = super().clean()
        bought, expires = data.get("purchase_date"), data.get("expiry_date")
        if bought and expires and bought > expires:
            self.add_error("purchase_date", "Purchase date can't be after the expiry date.")
        if data.get("price") is not None and data["price"] < 0:
            self.add_error("price", "Price can't be negative.")
        if bought and bought > timezone.localdate():
            self.add_error("purchase_date", "Purchase date can't be in the future.")
        return data


class MarkUsedForm(GlassFormMixin, forms.Form):
    amount_value = forms.DecimalField(
        label="What was it worth?", min_value=0, max_digits=10, decimal_places=2, required=False,
        help_text="Optional. Counts toward the money you saved this year.",
    )
