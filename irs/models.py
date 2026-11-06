import os
import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
from django.utils import timezone

CATEGORIES = ["Tax Returns", "Assessments", "Receipts", "Correspondence", "Legal", "Audit Reports", "Human Resources"]
DEPARTMENTS = ["Assessment", "Collections", "Audit", "Legal", "Administration"]
LEVELS = ["Public", "Internal", "Confidential"]


def _choices(values):
    return [(v, v) for v in values]


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "Administrator", "Administrator"
        RECORDS = "Records Officer", "Records Officer"
        STAFF = "Staff", "Staff"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STAFF)

    @property
    def display_name(self):
        return self.get_full_name() or self.username


def upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"documents/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{ext}"


class Document(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    ref = models.CharField(max_length=32, unique=True, editable=False)
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=40, choices=_choices(CATEGORIES))
    department = models.CharField(max_length=40, choices=_choices(DEPARTMENTS))
    level = models.CharField(max_length=20, choices=_choices(LEVELS), default="Internal")
    doc_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to=upload_to, blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    uploaded_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="documents")
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.ref} {self.title}"

    @staticmethod
    def next_ref(year):
        prefix = f"IRS/GUS/{year}/"
        last = (Document.objects.filter(ref__startswith=prefix)
                .order_by("-ref").values_list("ref", flat=True).first())
        n = int(last.rsplit("/", 1)[1]) + 1 if last else 1
        return f"{prefix}{n:04d}"

    def save(self, *args, **kwargs):
        if not self.ref:
            with transaction.atomic():
                self.ref = self.next_ref(timezone.now().year)
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)


class AuditLog(models.Model):
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="audit_logs")
    action = models.CharField(max_length=30)
    doc_ref = models.CharField(max_length=32)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.action} {self.doc_ref}"