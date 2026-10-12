from django.http import Http404, HttpResponse
from django.views.decorators.http import require_GET

from .models import StoredFile


@require_GET
def serve(request, name):
    """Send an uploaded file. File names never change once saved, so browsers may keep them."""
    row = StoredFile.objects.filter(name=name).only("content", "content_type").first()
    if row is None:
        raise Http404("File not found")
    response = HttpResponse(bytes(row.content), content_type=row.content_type)
    response["Cache-Control"] = "public, max-age=31536000, immutable"
    return response
