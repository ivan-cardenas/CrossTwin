"""
Journal changes that other apps make on behalf of a map edit, so the
backup restore (editing.restore_backup) reverts them with the edit itself.
"""
from django.dispatch import receiver

from physicalEnv.landcover import landcover_created, landcover_rewriting
from physicalEnv.models import LandCoverVector

from .editing import journal

LANDCOVER_KEY = "physicalEnv.LandCoverVector"


@receiver(landcover_rewriting, dispatch_uid="mainMap_landcover_rewriting")
def journal_rewritten_landcover(sender, pks, **kwargs):
    """Pre-images of the land-cover rows a new building's urban-fabric buffer clips or deletes."""
    for pk in pks:
        journal(LANDCOVER_KEY, LandCoverVector, pk)


@receiver(landcover_created, dispatch_uid="mainMap_landcover_created")
def journal_created_landcover(sender, pks, **kwargs):
    """The urban-fabric polygon itself: restore deletes it."""
    for pk in pks:
        journal(LANDCOVER_KEY, LandCoverVector, pk, created=True)
