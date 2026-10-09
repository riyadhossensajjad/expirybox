"""A Django storage backend that saves uploaded files in the database (see models.StoredFile)."""
import mimetypes

from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.urls import reverse
from django.utils.deconstruct import deconstructible


@deconstructible
class DatabaseStorage(Storage):
    def _model(self):
        from .models import StoredFile
        return StoredFile

    def _open(self, name, mode="rb"):
        row = self._model().objects.get(name=name)
        f = ContentFile(bytes(row.content))
        f.name = name
        return f

    def _save(self, name, content):
        content.seek(0) if hasattr(content, "seek") else None
        data = content.read()
        ctype = getattr(content, "content_type", None) or mimetypes.guess_type(name)[0] or "application/octet-stream"
        self._model().objects.update_or_create(
            name=name, defaults={"content": data, "content_type": ctype, "size": len(data)}
        )
        return name

    def exists(self, name):
        return self._model().objects.filter(name=name).exists()

    def delete(self, name):
        self._model().objects.filter(name=name).delete()

    def size(self, name):
        return self._model().objects.values_list("size", flat=True).get(name=name)

    def url(self, name):
        return reverse("filestore:file", args=[name])
