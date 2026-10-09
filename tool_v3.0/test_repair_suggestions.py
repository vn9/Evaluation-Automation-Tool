"""Self-check for the repair suggestion rules in gui_v3."""

from gui_v3 import App


def suggest(label, comment):
    return App.suggest_repairs_for_note(None, label, comment)

cases = [
    ("Cap", "peeling at the edge", ["Cosmetic: Cap"]),
    ("Cable", "yellow stains", ["Cosmetic: Cable"]),
    ("Lens", "scratches on the surface", ["Cosmetic: Lens"]),
    ("Array", "discolored", ["Cosmetic: Array"]),
    ("Cable", "leaking gel", ["Repair: Leak"]),
    ("Airscan", "bubbles present", ["Repair: Leak"]),
    ("Housing Strain Relief", "torn", ["Replacement: Housing Strain Relief"]),
    ("Array", "delaminated", ["Replacement: Array"]),
    ("Cap", "hole in cap", ["Replacement: Cap"]),
    ("Array", "many paint scratches", ["Replacement: Array"]),
    ("Shaft Housing", "cut on housing", ["Replacement: Shaft Housing"]),
    ("3D/4D", "error on startup", ["Repair: 3D/4D", "Replacement: Array Housing"]),
    ("3D/4D", "can't find home", ["Repair: 3D/4D", "Replacement: Array Housing"]),
    ("Image", "broken driving wire", ["Repair: 3D/4D", "Replacement: Array Housing"]),
    ("Cable", "outer jacket damaged", ["Replacement: Cable"]),
    ("Cable", "leaking, use as is", []),
    ("Array", "torn but used as it is", []),
    ("3D/4D", "error, use as is", []),
    ("Array", "torn and leaking", ["Repair: Leak"]),
    ("FirstCall", "fine", []),
]

for label, comment, expected in cases:
    got = suggest(label, comment)
    assert got == expected, f"{label!r} / {comment!r}: got {got}, want {expected}"

print(f"{len(cases)} cases passed.")
