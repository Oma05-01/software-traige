import uuid

from django.db import models
from django.db.models import UniqueConstraint
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector


class KnowledgeDocument(models.Model):

    class SourceType(models.TextChoices):
        MANUAL = "manual", "Manual"
        URL = "url", "Website URL"
        GITHUB_ISSUE = "github_issue", "GitHub Issue"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    title = models.CharField(max_length=255)

    source_type = models.CharField(
        max_length=20,
        choices=SourceType.choices,
        default=SourceType.MANUAL,
    )

    source_reference = models.URLField(
        blank=True,
    )

    # Original document content.
    content = models.TextField()

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class KnowledgeChunk(models.Model):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    document = models.ForeignKey(
        KnowledgeDocument,
        on_delete=models.CASCADE,
        related_name="chunks",
    )

    chunk_index = models.PositiveIntegerField()

    content = models.TextField()

    section_title = models.CharField(
        max_length=255,
        blank=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["document_id", "chunk_index"]

        constraints = [
            UniqueConstraint(
                fields=["document", "chunk_index"],
                name="unique_document_chunk_index",
            ),
        ]

        indexes = [
            models.Index(
                fields=["document", "chunk_index"],
                name="knowledge_chunk_order_idx",
            ),
        ]

        # PostgreSQL GIN index for full-text search.
        indexes += [
            GinIndex(
                SearchVector(
                    "content",
                    config="english",
                ),
                name="knowledge_chunk_fts_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.document.title} - "
            f"Chunk {self.chunk_index}"
        )