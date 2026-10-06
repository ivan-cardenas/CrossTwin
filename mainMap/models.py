from django.conf import settings
from django.db import models


class EditBackup(models.Model):
    """
    Restore point for what-if edits made with the map editor
    (mainMap/editing.py, docs/MAP_EDITING.md). Creating one copies nothing:
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
