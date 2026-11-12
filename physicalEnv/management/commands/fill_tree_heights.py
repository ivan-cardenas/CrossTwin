"""Measure the height of stored trees that have none from the DSM (physicalEnv/calculations/tree_heights.py)."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Fill nature.Tree.height_m from the DSM for trees without a height (scales the map's 3D tree models)."

    def add_arguments(self, parser):
        parser.add_argument("--city", help="Only trees in this city's neighborhoods (City name)")

    def handle(self, *args, **options):
        from core.cache import bump_layer_version
        from nature.models import Tree
        from physicalEnv.calculations.tree_heights import fill_from_dsm

        trees = Tree.objects.all()
        if options["city"]:
            trees = trees.filter(neighborhood__district__city__cityName__iexact=options["city"])
        missing = trees.filter(height_m__isnull=True).count()
        filled = fill_from_dsm(trees)
        if filled:
            bump_layer_version(Tree)
        self.stdout.write(self.style.SUCCESS(f"{filled} of {missing} trees without a height measured from the DSM."))
