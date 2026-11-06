from django.http import FileResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import NotFound
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import AuditLog, Document
from .permissions import DocumentPermission, IsAdministrator
from .serializers import (AuditLogSerializer, DocumentSerializer, LoginResponseSerializer,
                          LoginSerializer, UserSerializer)


@extend_schema(tags=["auth"], responses=LoginResponseSerializer)
class LoginView(TokenObtainPairView):
    """Exchange username and password for JWT access and refresh tokens."""
    serializer_class = LoginSerializer


@extend_schema(tags=["auth"], responses=UserSerializer)
@api_view(["GET"])
def me(request):
    """The currently signed-in user."""
    return Response(UserSerializer(request.user).data)


def record(user, action_name, doc_ref):
    AuditLog.objects.create(user=user, action=action_name, doc_ref=doc_ref)


@extend_schema(tags=["documents"])
class DocumentViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin,
                      mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Archive records. Upload with multipart/form-data."""

    queryset = Document.objects.select_related("uploaded_by")
    serializer_class = DocumentSerializer
    permission_classes = [DocumentPermission]
    parser_classes = [MultiPartParser, FormParser]
    filterset_fields = ["status", "category", "department", "level"]
    search_fields = ["title", "ref", "description"]
    ordering_fields = ["created_at", "title", "ref"]

    def perform_create(self, serializer):
        doc = serializer.save(uploaded_by=self.request.user)
        record(self.request.user, "Uploaded", doc.ref)

    def perform_destroy(self, instance):
        ref = instance.ref
        instance.file.delete(save=False)
        instance.delete()
        record(self.request.user, "Deleted", ref)

    def _set_status(self, request, status, label):
        doc = self.get_object()
        doc.status = status
        doc.save(update_fields=["status"])
        record(request.user, label, doc.ref)
        return Response(self.get_serializer(doc).data)

    @extend_schema(request=None, responses=DocumentSerializer)
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        """Move a record to the archive (Records Officer or Administrator)."""
        return self._set_status(request, Document.Status.ARCHIVED, "Archived")

    @extend_schema(request=None, responses=DocumentSerializer)
    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        """Restore an archived record (Records Officer or Administrator)."""
        return self._set_status(request, Document.Status.ACTIVE, "Restored")

    @extend_schema(responses={(200, "application/octet-stream"): OpenApiTypes.BINARY})
    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        """Download the stored file."""
        doc = self.get_object()
        if not doc.file:
            raise NotFound("No file stored for this record.")
        record(request.user, "Downloaded", doc.ref)
        return FileResponse(doc.file.open("rb"), as_attachment=True, filename=doc.file_name or None)


@extend_schema(tags=["audit"])
class AuditLogViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Activity log (Administrator only). Latest 200 entries."""

    queryset = AuditLog.objects.select_related("user")
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdministrator]
    filter_backends = []

    def get_queryset(self):
        return super().get_queryset()[:200]