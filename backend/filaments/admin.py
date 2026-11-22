from django.contrib import admin

from filaments.models import Filament, Tag


class DeletedFilter(admin.SimpleListFilter):
    title = "deleted"
    parameter_name = "deleted"

    def lookups(self, request, model_admin):
        return [("no", "Not deleted"), ("yes", "Deleted")]

    def queryset(self, request, queryset):
        if self.value() == "no":
            return queryset.filter(deleted_at__isnull=True)
        if self.value() == "yes":
            return queryset.filter(deleted_at__isnull=False)
        return queryset


@admin.register(Filament)
class FilamentAdmin(admin.ModelAdmin):
    list_display = ["title", "source", "created_at", "deleted_at"]
    list_filter = [DeletedFilter, "source"]
    search_fields = ["title", "body"]
    filter_horizontal = ["tags"]
    readonly_fields = ["id", "created_at", "updated_at"]
    fields = ["id", "title", "body", "source", "tags", "created_at", "updated_at", "deleted_at"]

    def get_queryset(self, request):
        # Show soft-deleted filaments too; the default manager hides them.
        return Filament.all_objects.all()


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
