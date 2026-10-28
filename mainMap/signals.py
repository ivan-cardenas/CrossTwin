"""
Journal changes that other apps make on behalf of a map edit, so the
backup restore (core.editing.restore_backup) reverts them with the edit itself.
"""
from django.dispatch import receiver

from physicalEnv.landcover import landcover_created, landcover_rewriting
from physicalEnv.dsm_patches import dsm_patch_created, dsm_patch_rewriting

from core.editing import journal


def _key(model):
    return f"{model._meta.app_label}.{model.__name__}"


@receiver(landcover_rewriting, dispatch_uid="mainMap_landcover_rewriting")
def journal_rewritten_landcover(sender, pks, **kwargs):
    """Pre-images of the rows an urban-fabric ring (or its release) changes or deletes:
    LandCoverVector polygons and the UrbanFabricCut pieces kept to undo the ring."""
    for pk in pks:
        journal(_key(sender), sender, pk)


@receiver(landcover_created, dispatch_uid="mainMap_landcover_created")
def journal_created_landcover(sender, pks, **kwargs):
    """Rows the ring inserted (the ring itself, its cuts, recreated polygons): restore deletes them."""
    for pk in pks:
        journal(_key(sender), sender, pk, created=True)


@receiver(dsm_patch_rewriting, dispatch_uid="mainMap_dsm_patch_rewriting")
def journal_rewritten_dsm_patch(sender, pks, **kwargs):
    """Pre-image of a DSMBuildingPatch an editor building change rewrites (Buildings -> DSM)."""
    for pk in pks:
        journal(_key(sender), sender, pk)


@receiver(dsm_patch_created, dispatch_uid="mainMap_dsm_patch_created")
def journal_created_dsm_patch(sender, pks, **kwargs):
    """A DSMBuildingPatch created by an editor change: restore deletes it."""
    for pk in pks:
        journal(_key(sender), sender, pk, created=True)
