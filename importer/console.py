"""
Console progress lines for the importers (upload wizard, external import),
so whoever runs the server can follow what an import is doing:

    [import] wfs     | Fetching WFS: https://service.pdok.nl/... layer=gemeentegebied
    [import] write   | 312 feature(s) -> administrative.City: 12 created, 300 updated

Warnings and errors are also sent to the module's `logger`; these lines are
only the human-readable trace next to them.
"""


def say(step, text):
    """
    One console line. Forced to ASCII: a character the Windows cp1252 console
    can't encode (a file or place name) would raise inside the request.
    """
    line = f"[import] {step:<7} | {text}"
    print(line.encode("ascii", "replace").decode("ascii"), flush=True)
