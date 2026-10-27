from django.conf import settings
from django.db import models


class EditBackup(models.Model):
    """
    Restore point for what-if edits made with the map editor
    (core/editing.py, docs/MAP_EDITING.md). Creating one copies nothing:
    from then on every edit, create or delete made through the editor first
    stores the object's original row as an EditBackupRow, once per object.
    At most one backup exists at a time.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"Edit backup {self.created_at:%Y-%m-%d %H:%M}"

    class Meta:
        verbose_name = "Edit backup"
        verbose_name_plural = "Edit backups"


class EditBackupRow(models.Model):
    """
    The state of one object when the backup was made. `original` holds the
    row as Django's serializer writes it (geometry in its stored CRS);
    null means the object did not exist yet, so restoring deletes it.
    """
    # CASCADE: bookkeeping, not spatial reference data
    backup = models.ForeignKey(EditBackup, on_delete=models.CASCADE, related_name="rows")
    layer_key = models.CharField(max_length=100, help_text="Registry key, e.g. 'builtup.Building'")
    # Text, so it holds BAG BigInteger ids and auto ids alike
    object_pk = models.CharField(max_length=64)
    original = models.JSONField(null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.layer_key} {self.object_pk}"

    class Meta:
        verbose_name = "Edit backup row"
        verbose_name_plural = "Edit backup rows"
        constraints = [
            models.UniqueConstraint(fields=["backup", "layer_key", "object_pk"], name="unique_edit_backup_object"),
        ]


class EditableLayer(models.Model):
    """
    A vector layer staff may edit on the map, switched on in the map's settings
    panel (mainMap/settings_views.py). A row = editable. Which fields the form
    leaves out is not stored here: that stays in core/editable_layers.toml
    (core.editing.FIELD_RULES), because it follows from each model's save().
    """
    key = models.CharField(max_length=100, unique=True, help_text="Registry key, e.g. 'builtup.Building'")
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.key

    class Meta:
        verbose_name = "Editable layer"
        verbose_name_plural = "Editable layers"


class LayerStyleOverride(models.Model):
    """
    A map style set in the settings panel, on top of the default in
    mainMap/styles/ (mainMap/styles/overrides.py). Deleting the row restores
    the default.

    kind 'vector': key = registry key; data = {"color": "#rrggbb",
        "paint": {"<style layer index>": {"<paint property>": value}},
        "categories": {"<match value>": "#rrggbb"}}
    kind 'raster': key = raster style key (rasterStyles.raster_style_key);
        data = {"colormap": "<rio-tiler name>", "rescale": [min, max] | null}
    """
    VECTOR, RASTER = "vector", "raster"
    KIND_CHOICES = [(VECTOR, "Vector layer"), (RASTER, "Raster")]

    key = models.CharField(max_length=100)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    data = models.JSONField(default=dict)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.kind} style {self.key}"

    class Meta:
        verbose_name = "Layer style override"
        verbose_name_plural = "Layer style overrides"
        constraints = [
            models.UniqueConstraint(fields=["key", "kind"], name="unique_layer_style_override"),
        ]
