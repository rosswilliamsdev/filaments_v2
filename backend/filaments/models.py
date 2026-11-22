import uuid

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class Tag(models.Model):
    """A tag name. Normalization (see `schemas.tags.normalize_tag`) happens in the schemas
    package before writes; the constraints here are only a backstop."""

    name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(name=Lower("name")),
                name="tag_name_lowercase",
            ),
            models.CheckConstraint(
                condition=models.Q(name__regex=r"^\S+$"),
                name="tag_name_no_whitespace",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class ActiveFilamentManager(models.Manager):
    """Default manager: hides soft-deleted filaments, including via `tag.filaments`."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class Filament(models.Model):
    class Source(models.TextChoices):
        CLAUDE = "claude", "Claude"
        WEB = "web", "Web"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    body = models.TextField()
    # No default: every write path must say where the filament came from.
    source = models.CharField(max_length=10, choices=Source)
    tags = models.ManyToManyField(Tag, related_name="filaments", blank=True)

    # Computed by Postgres on every write. Tags are deliberately not included:
    # a generated column can only read its own row (keyword-to-tag matching is step 5).
    search_vector = models.GeneratedField(
        expression=SearchVector("title", weight="A", config="english")
        + SearchVector("body", weight="B", config="english"),
        output_field=SearchVectorField(),
        db_persist=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = ActiveFilamentManager()  # declared first, so it's the default manager
    all_objects = models.Manager()  # noqa: DJ012 - a second manager, not a field

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            GinIndex(fields=["search_vector"], name="filament_search_vector_gin"),
            models.Index(fields=["created_at"], name="filament_created_at_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(title__regex=r"\S"),
                name="filament_title_not_blank",
            ),
            models.CheckConstraint(
                condition=models.Q(body__regex=r"\S"),
                name="filament_body_not_blank",
            ),
            models.CheckConstraint(
                condition=models.Q(source__in=["claude", "web"]),
                name="filament_source_valid",
            ),
        ]

    def __str__(self) -> str:
        return self.title

    def soft_delete(self) -> None:
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])
