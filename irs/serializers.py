from django.conf import settings
from django.core.validators import FileExtensionValidator
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import AuditLog, Document, User


class UserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="display_name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "name", "role"]


class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data


class LoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()


class DocumentSerializer(serializers.ModelSerializer):
    """Field names are camelCase where the React app expects them."""

    docDate = serializers.DateField(source="doc_date", required=False, allow_null=True)
    addedAt = serializers.DateTimeField(source="created_at", read_only=True)
    by = serializers.IntegerField(source="uploaded_by_id", read_only=True)
    by_name = serializers.CharField(source="uploaded_by.display_name", read_only=True)
    fileName = serializers.CharField(source="file_name", read_only=True)
    hasFile = serializers.SerializerMethodField()
    file = serializers.FileField(
        write_only=True,
        validators=[FileExtensionValidator(["pdf", "doc", "docx", "png", "jpg", "jpeg"])],
    )

    class Meta:
        model = Document
        fields = [
            "id", "ref", "title", "category", "department", "level", "docDate",
            "description", "status", "by", "by_name", "addedAt", "fileName", "hasFile", "file",
        ]
        read_only_fields = ["id", "ref", "status"]

    def get_hasFile(self, obj) -> bool:
        return bool(obj.file)

    def validate_title(self, v):
        v = v.strip()
        if not v:
            raise serializers.ValidationError("Enter a document title.")
        return v

    def validate_file(self, f):
        if f.size > settings.MAX_UPLOAD_BYTES:
            raise serializers.ValidationError("File is larger than 10 MB.")
        return f

    def create(self, validated_data):
        validated_data["file_name"] = validated_data["file"].name[:255]
        return super().create(validated_data)


class AuditLogSerializer(serializers.ModelSerializer):
    at = serializers.DateTimeField(source="created_at", read_only=True)
    doc = serializers.CharField(source="doc_ref", read_only=True)
    by_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = ["id", "action", "doc", "at", "by_name"]

    def get_by_name(self, obj) -> str:
        return obj.user.display_name if obj.user else "Unknown"