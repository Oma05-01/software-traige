from django.contrib import admin

from .models import KnowledgeDocument, KnowledgeChunk


class KnowledgeChunkInline(admin.TabularInline):
    model = KnowledgeChunk
    extra = 0
    readonly_fields = (
        "id",
        "chunk_index",
        "content",
        "created_at",
    )

    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "source_type",
        "is_active",
        "created_at",
    )

    list_filter = (
        "source_type",
        "is_active",
        "created_at",
    )

    search_fields = (
        "title",
        "content",
        "source_reference",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )

    inlines = [KnowledgeChunkInline]


@admin.register(KnowledgeChunk)
class KnowledgeChunkAdmin(admin.ModelAdmin):

    list_display = (
        "document",
        "chunk_index",
        "created_at",
    )

    search_fields = (
        "content",
        "document__title",
    )

    list_filter = ("document__source_type",)

    readonly_fields = (
        "id",
        "document",
        "chunk_index",
        "content",
        "metadata",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False