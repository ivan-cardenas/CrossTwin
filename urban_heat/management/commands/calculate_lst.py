from datetime import date

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Compute Land Surface Temperature from a Landsat 9 (or 8) scene with the "
        "Statistical Mono-Window algorithm, using CrossTwin's NDVI layer for the "
        "emissivity, and store it as urban_heat.LandSurfaceTemperature."
    )

    def add_arguments(self, parser):
        parser.add_argument("--city", help="City name (cityName) or id whose latest NDVI layer to use")
        parser.add_argument("--ndvi-id", type=int, help="Use this physicalEnv.LandCoverRaster NDVI row")
        parser.add_argument("--from", dest="date_from", type=date.fromisoformat,
                            help="Scene search start, YYYY-MM-DD (default: NDVI date - 30 days)")
        parser.add_argument("--to", dest="date_to", type=date.fromisoformat,
                            help="Scene search end, exclusive (default: NDVI date + 30 days)")
        parser.add_argument("--scene", help="Landsat scene id, e.g. LC09_197024_20240712 (skips the search)")
        parser.add_argument("--sensor", choices=["L9", "L8"], default="L9")
        parser.add_argument("--resolution", type=float, default=30.0, help="Output cell size in m (default 30)")
        parser.add_argument("--max-cloud", type=float, help="Only scenes with CLOUD_COVER <= this %%")
        parser.add_argument("--aster-emissivity", action="store_true",
                            help="Emissivity from ASTER only (use_ndvi=false); NDVI layer only sets the grid")
        parser.add_argument("--list-scenes", action="store_true", help="List the matching scenes and stop")
        parser.add_argument("--dry-run", action="store_true", help="Compute and report, do not save")

    def handle(self, *args, **opts):
        from urban_heat.lst import gee
        from urban_heat.lst.pipeline import (
            LSTError, SENSOR_LABELS, calculate_lst, default_window, grid_for, ndvi_layer,
        )

        try:
            ndvi = ndvi_layer(city=self._city(opts["city"]), ndvi_id=opts["ndvi_id"])
            self.stdout.write(f"NDVI layer: #{ndvi.pk} {ndvi}")

            if opts["list_scenes"]:
                grid = grid_for(ndvi.raster, opts["resolution"])
                start, end = default_window(ndvi)
                start, end = opts["date_from"] or start, opts["date_to"] or end
                gee.initialize()
                scenes = gee.find_scenes(opts["sensor"], str(start), str(end), grid.wgs84_bbox(), opts["max_cloud"])
                self.stdout.write(f"{len(scenes)} {SENSOR_LABELS[opts['sensor']]} scene(s) {start} .. {end}:")
                for s in scenes:
                    clear = f"{s.view_clear:6.1%}" if s.view_clear is not None else "    ?"
                    self.stdout.write(
                        f"  {s.scene_id}  {s.acquired:%Y-%m-%d %H:%M} UTC  "
                        f"clear over layer {clear}  scene cloud {s.cloud_cover:5.1f} %"
                    )
                return

            result = calculate_lst(
                ndvi=ndvi,
                date_from=opts["date_from"],
                date_to=opts["date_to"],
                scene_id=opts["scene"],
                sensor=opts["sensor"],
                resolution=opts["resolution"],
                max_cloud=opts["max_cloud"],
                use_ndvi=not opts["aster_emissivity"],
                save=not opts["dry_run"],
            )
        except (LSTError, gee.GEEError) as e:
            raise CommandError(str(e)) from e

        s, g = result.scene, result.grid
        st = result.stats()
        self.stdout.write(
            f"Scene {s.scene_id} ({s.acquired:%Y-%m-%d %H:%M} UTC, scene cloud {s.cloud_cover:.0f} %), "
            f"grid {g.width}x{g.height} @ {g.resolution:g} m, {result.valid_fraction:.0%} clear"
        )
        self.stdout.write(f"LST °C: min {st['min']:.1f}  mean {st['mean']:.1f}  max {st['max']:.1f}  (water vapour: {result.tpw_source})")
        if result.record is not None:
            self.stdout.write(self.style.SUCCESS(f"Saved LandSurfaceTemperature id={result.record.pk}"))
        else:
            self.stdout.write("Dry run: nothing saved.")

    @staticmethod
    def _city(value):
        if not value:
            return None
        from administrative.models import City

        qs = City.objects.filter(pk=int(value)) if value.isdigit() else City.objects.filter(cityName__iexact=value)
        city = qs.first()
        if city is None:
            raise CommandError(f"City {value!r} not found.")
        return city
