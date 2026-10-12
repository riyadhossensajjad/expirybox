from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm

from config.forms import GlassFormMixin, PhotoFieldMixin

from .models import User


class SignUpForm(PhotoFieldMixin, GlassFormMixin, UserCreationForm):
    photo_field = "avatar"

    class Meta:
        model = User
        fields = ["avatar", "name", "email", "phone", "address"]
        labels = {"name": "Full name", "address": "Area or address"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs["autocomplete"] = "name"
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["phone"].widget.attrs["autocomplete"] = "tel"


class LoginForm(GlassFormMixin, AuthenticationForm):
    username = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}))


class ProfileForm(PhotoFieldMixin, GlassFormMixin, forms.ModelForm):
    photo_field = "avatar"

    class Meta:
        model = User
        fields = ["avatar", "name", "email", "phone", "address"]
        labels = {"name": "Full name", "address": "Area or address"}


class GlassPasswordChangeForm(GlassFormMixin, PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # It shares a page with the profile form, so don't jump the page down to it.
        self.fields["old_password"].widget.attrs.pop("autofocus", None)
