from django.db import models


class StoredFile(models.Model):
    """An uploaded file (item photo, profile picture) kept inside the database.

    Used when the site runs on Vercel, whose servers don't keep files written to
    disk. Photos are already shrunk to small JPEGs when uploaded, so they fit
    comfortably in Postgres.
    """

    name = models.CharField(max_length=255, unique=True)
    content = models.BinaryField()
    content_type = models.CharField(max_length=100, default="application/octet-stream")
    size = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
