from django.contrib.gis.db import models
from django.conf import settings

COORDINATE_SYSTEM = settings.COORDINATE_SYSTEM
from django.utils import timezone

# Create your models here.
class ProtectedArea(models.Model):
    class ProtectionType(models.TextChoices):
        NATURA2000 = 'N2K', 'Natura 2000'
        NNN = 'NNN', 'Natuurnetwerk Nederland'
        RAMSAR = 'RAM', 'Ramsar'
        OTHER = 'OTH', 'Other'
        

    id = models.AutoField(primary_key=True)
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
    geom = models.MultiPolygonField(srid=COORDINATE_SYSTEM)
    last_updated = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.name}"

    class Meta:
        verbose_name = "Forest"
        verbose_name_plural = "Forests"