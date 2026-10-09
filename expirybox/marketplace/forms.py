from django import forms
from django.core.validators import MaxValueValidator
from django.utils import timezone

from config.forms import DateInput, GlassFormMixin

from .models import Listing, Order, Payment, Review


class ListingForm(GlassFormMixin, forms.ModelForm):
    save_as_draft = forms.BooleanField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Listing
        fields = ["original_price", "sale_price", "quantity", "pickup_location", "available_until"]
        widgets = {"available_until": DateInput()}
        labels = {
            "original_price": "Original price",
            "sale_price": "Your price",
            "pickup_location": "Pickup area",
            "available_until": "Available until",
        }

    def __init__(self, *args, item=None, **kwargs):
        self.item = item
        super().__init__(*args, **kwargs)
        for f in ("original_price", "sale_price"):
            self.fields[f].widget.attrs.update({"step": "0.01", "inputmode": "decimal"})

    def clean(self):
        data = super().clean()
        orig, sale = data.get("original_price"), data.get("sale_price")
        if orig is not None and sale is not None and sale > orig:
            self.add_error("sale_price", "Set a price at or below the original price.")
        until = data.get("available_until")
        if until:
            if until < timezone.localdate():
                self.add_error("available_until", "Pick today or a later date.")
            if self.item and until > self.item.expiry_date:
                self.add_error("available_until", "Can't be later than the item's expiry date.")
        return data


class OrderForm(GlassFormMixin, forms.ModelForm):
    class Meta:
        model = Order
        fields = ["quantity", "delivery_method"]
        widgets = {"delivery_method": forms.RadioSelect}

    def __init__(self, *args, listing=None, **kwargs):
        super().__init__(*args, **kwargs)
        if listing:
            self.fields["quantity"].widget.attrs.update({"min": 1, "max": listing.quantity})
            self.fields["quantity"].max_value = listing.quantity
            self.fields["quantity"].validators.append(MaxValueValidator(listing.quantity))
            self.fields["quantity"].help_text = f"Up to {listing.quantity} available."


class PaymentForm(forms.Form):
    method = forms.ChoiceField(choices=Payment.Method.choices, widget=forms.RadioSelect, initial=Payment.Method.BKASH)


class ReviewForm(GlassFormMixin, forms.ModelForm):
    rating = forms.TypedChoiceField(
        choices=[(i, str(i)) for i in range(5, 0, -1)], coerce=int, widget=forms.RadioSelect
    )

    class Meta:
        model = Review
        fields = ["rating", "comment"]
        widgets = {"comment": forms.Textarea(attrs={"placeholder": "Was it as described? Easy pickup?"})}
