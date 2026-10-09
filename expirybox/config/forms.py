from django import forms


class GlassFormMixin:
    """Gives every widget the shared input styling and sensible autocomplete hints."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect)):
                continue
            css = "select" if isinstance(widget, forms.Select) else "input"
            if isinstance(widget, forms.Textarea):
                css = "input textarea"
                widget.attrs.setdefault("rows", 3)
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        kwargs.setdefault("format", "%Y-%m-%d")
        super().__init__(**kwargs)


def prepare_image(upload, max_side=1400):
    """Check an uploaded photo and shrink it so phone pictures don't fill the disk.

    Returns a JPEG ContentFile ready to assign to an ImageField.
    """
    from io import BytesIO
    from pathlib import Path

    from django.conf import settings
    from django.core.files.base import ContentFile
    from PIL import Image, ImageOps, UnidentifiedImageError

    limit = settings.MAX_UPLOAD_MB
    if upload.size > limit * 1024 * 1024:
        raise forms.ValidationError(f"Choose a photo under {limit} MB.")
    try:
        img = Image.open(upload)
        img = ImageOps.exif_transpose(img)
    except (UnidentifiedImageError, OSError):
        raise forms.ValidationError("That file isn't a photo we can read. Use JPG, PNG or WebP.")
    img.thumbnail((max_side, max_side))
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")
    buf = BytesIO()
    img.save(buf, "JPEG", quality=85, optimize=True)
    return ContentFile(buf.getvalue(), name=f"{Path(upload.name).stem[:40]}.jpg")


class PhotoFieldMixin:
    """Adds a photo upload with a 'remove photo' checkbox to a ModelForm.

    Set `photo_field` to the model's ImageField name.
    """

    photo_field = "image"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        f = self.fields[self.photo_field]
        f.widget = forms.FileInput(attrs={"accept": "image/*", "data-upload": ""})
        f.required = False
        self.fields["remove_photo"] = forms.BooleanField(required=False)

    def clean(self):
        data = super().clean()
        upload = self.files.get(self.add_prefix(self.photo_field))
        if upload:
            try:
                data[self.photo_field] = prepare_image(upload)
            except forms.ValidationError as e:
                self.add_error(self.photo_field, e)
        return data

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.cleaned_data.get("remove_photo") and not self.files.get(self.add_prefix(self.photo_field)):
            # Only clear the reference; the file may be shared with a buyer's copy of the item.
            setattr(obj, self.photo_field, "")
        if commit:
            obj.save()
        return obj
