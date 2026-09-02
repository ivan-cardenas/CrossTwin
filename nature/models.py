from django.contrib.gis.db import models
from django.conf import settings

COORDINATE_SYSTEM = settings.COORDINATE_SYSTEM
from django.utils import timezone
from django.apps import apps

# Create your models here.
class ProtectedArea(models.Model):
    class ProtectionType(models.TextChoices):
        NATURA2000 = 'N2K', 'Natura 2000'
        NNN = 'NNN', 'Natuurnetwerk Nederland'
        RAMSAR = 'RAM', 'Ramsar'
        OTHER = 'OTH', 'Other'
        

    id = models.AutoField(primary_key=True)
    inspireID = models.CharField(max_length=100, unique=True, help_text="Unique identifier for the protected area from INSPIRE dataset")
    name = models.CharField(max_length=200)
    protection_type = models.CharField(
        max_length=3, choices=ProtectionType.choices
    )
    geom = models.MultiPolygonField(srid=COORDINATE_SYSTEM)
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.name} ({self.get_protection_type_display()})"

    class Meta:
        verbose_name = "Protected Area"
        verbose_name_plural = "Protected Areas"
        
class WaterWays(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=100, help_text="Type of waterway (e.g., river, canal, etc.)", null=True, blank=True)
    geom = models.LineStringField(srid=COORDINATE_SYSTEM)
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.name}"

    class Meta:
        verbose_name = "Water Way"
        verbose_name_plural = "Water Ways"
        
class WaterBodies(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=100, help_text="Type of water body (e.g., lake, reservoir, stream, etc.)", null=True, blank=True)
    geom = models.MultiPolygonField(srid=COORDINATE_SYSTEM)
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.name}"

    class Meta:
        verbose_name = "Water Body"
        verbose_name_plural = "Water Bodies"
        
class Forests(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=100, help_text="Type of forest (e.g., deciduous, coniferous, mixed, etc.)", null=True, blank=True)
    geom = models.MultiPolygonField(srid=COORDINATE_SYSTEM)
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.name}"

    class Meta:
        verbose_name = "Forest"
        verbose_name_plural = "Forests"
        
class GreenSpaces(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=100, help_text="Type of green space (e.g., park, garden, etc.)", null=True, blank=True)
    city = models.ForeignKey(
        'common.City',
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        help_text="City this green space belongs to (resolved via centroid intersection)",
    )
    geom = models.MultiPolygonField(srid=COORDINATE_SYSTEM)
    last_updated = models.DateTimeField(default=timezone.now)
    area = models.FloatField(help_text="Area of the green space in square meters", null=True, blank=True)

    def __str__(self):
        return f"{self.name}"

    class Meta:
        verbose_name = "Green Space"
        verbose_name_plural = "Green Spaces"
        
    def save(self, *args, **kwargs):
        if self.geom:
            self.area = self.geom.area
        super().save(*args, **kwargs)
        
        