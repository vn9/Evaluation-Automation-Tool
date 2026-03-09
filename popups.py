import tkinter as tk
from tkinter import ttk
from collections import defaultdict


class BasePopup(tk.Toplevel):
    def __init__(self, master, categories, colors, title, on_done,
                 columns_per_row=None, grouped_preview=False):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.grab_set()
        self.resizable(True, True)
        self.minsize(720, 520)

        self.categories = categories
        self.colors = colors
        self.vars = []
        self.columns_per_row = columns_per_row
        self.grouped_preview = grouped_preview

        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)

        # Build UI
        for idx, (cat, items) in enumerate(self.categories.items()):
            if self.columns_per_row and self.columns_per_row > 0:
                r = idx // self.columns_per_row
                c = idx % self.columns_per_row
            else:
                r, c = 0, idx

            frm = tk.Frame(outer, bg=self.colors[cat], bd=2, relief="groove")
            frm.grid(row=r, column=c, padx=5, pady=5, sticky="n")

            lbl = tk.Label(frm, text=cat, font=("Segoe UI", 10, "bold"), bg=self.colors[cat])
            lbl.pack(anchor="w", padx=6, pady=(4, 6))

            for item in items:
                var = tk.BooleanVar(value=False)
                cb = tk.Checkbutton(frm, text=item, variable=var, bg=self.colors[cat], anchor="w")
                cb.pack(anchor="w", padx=12, pady=2)
                self.vars.append((cat, item, var))

        self.preview = tk.Text(self, height=5, wrap="word", state="normal")
        self.preview.pack(fill="x", padx=12, pady=(8, 0))

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=12, pady=12)
        ttk.Button(btns, text="Preview", command=self.do_preview).pack(side="left")
        ttk.Button(btns, text="OK", command=lambda: self.finish(on_done)).pack(side="left", padx=8)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right")


    def get_selected_text(self) -> str:
        order = {"Replacement": 0, "Repair": 1, "Cosmetic": 2}
        chosen = [(cat, item) for (cat, item, v) in self.vars if v.get()]
        chosen.sort(key=lambda ci: (order.get(ci[0], 99), ci[1].lower()))

        if self.grouped_preview:
            grouped = defaultdict(list)
            for cat, item in chosen:
                grouped[cat].append(item)
            lines = []
            for cat in self.categories.keys():
                if cat in grouped:
                    lines.append(f"{cat}: {', '.join(grouped[cat])}")
            return "\n".join(lines)

        lines = []
        for idx, (cat, item) in enumerate(chosen, start=1):
            lines.append(f"{idx}. {cat}: {item}")
        return "\n".join(lines)

    def do_preview(self):
        txt = self.get_selected_text() or "(No items selected)"
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", txt)

    def finish(self, on_done):
        on_done(self.preview.get("1.0", "end").strip())
        self.destroy()


class RepairsPopup(BasePopup):
    def __init__(self, master, on_done):
        categories = {
            "Replacement": ["Lens", "Cap", "Array", "Shaft Housing", "Housing Strain Relief",
                            "Cable", "Connector Strain Relief", "Connector Housing",
                            "Connector Housing Label", "Connector Knob", "Connector Housing Frame"],
            "Repair": [
                "Lens", "Lens Gap", "Cap", "Array", "Shaft Housing Halves Splits",
                "Housing Strain Relief", "Cable Jacket", "Connector Strain Relief",
                "Leak", "3D/4D", "Electrical"
            ],
            "Cosmetic": ["Shaft Housing", "Housing Strain Relief", "Connector Strain Relief",
                         "Connector Housing", "Cable"]
        }
        colors = {
            "Replacement": "lightcoral",
            "Repair": "lightgreen",
            "Cosmetic": "yellow",
        }
        super().__init__(master, categories, colors, "Select Repairs", on_done)


class ItemsPopup(BasePopup):
    def __init__(self, master, on_done):
        categories = {
            "LENS": ["Cut", "Delaminated", "Missing", "Damaged", "Hole", "Worn out", "Others"],
            "CAP": ["Cut", "Missing", "Damaged", "Hole", "Dent marks", "Fell-off",
                    "Leak at seam", "Worn out", "Others"],
            "ARRAY (FirstCall)": ["Damaged", "Dead elements (used as it is)", "Weak elements",
                                  "Color noises", "No File", "Elements shortage to ground", "Others"],
            "OIL LEAK": ["Seam", "Inner", "Bubbles", "Others"],
            "ARRAY HOUSING": ["Damaged", "Scratches", "Broken", "Others"],
            "SHAFT HOUSING": ["Halves splits", "Scratches", "Broken", "Damaged", "Stains", "Others"],
            "CONNECTOR HOUSING": ["Paint scratches", "Scratched knob", "Knob fell-off",
                                  "Serial label damaged", "Others"],
            "HOUSING STRAIN RELIEF": ["Cut", "Tear", "Cracks", "Worn out", "Pulled out shaft",
                                      "Discolored", "Others"],
            "CONNECTOR STRAIN RELIEF": ["Cut", "Tear", "Cracks", "Worn out", "Detached from connector",
                                        "Discolored", "Others"],
            "CABLE JACKET": ["Cut", "Tear", "Cracks", "Abrasion", "Damaged", "Scratches", "Twisted",
                             "Bent", "Discolored", "Pulled out strain", "Stiff", "Others"],
            "CABLE (Functional Test)": ["Elements shortage to ground", "Liquid concentration",
                                        "Intermittent", "White noises", "Color noises",
                                        "Many dead elements", "No system", "Others"],
            "AIRSCAN": ["Dropouts", "Air bubbles", "Cloudy", "Uneven scanline", "Intermittent dropouts",
                        "White noises", "Color noises", "No system",
                        "3D/4D Error (Airscan cannot be captured)", "Others"],
            "IMAGE": ["Shadows", "Poor resolution", "Intermittent dropouts", "Mirrored/Multiple images",
                      "White noises", "No system", "3D/4D Error (Image cannot be captured)", "Others"],
            "3D/4D": ["Couldn't find home", "Vibrating", "Cracking noise", "Array ball collapsed",
                      "Driving wire broken", "Run then terminate", "No system", "Others"],
        }
        colors = {
            "LENS": "gainsboro", "CAP": "linen", "SHAFT HOUSING": "antique white",
            "ARRAY HOUSING": "papaya whip", "HOUSING STRAIN RELIEF": "blanched almond",
            "CABLE JACKET": "bisque", "CONNECTOR STRAIN RELIEF": "peach puff",
            "CONNECTOR HOUSING": "navajo white", "OIL LEAK": "mint cream", "ARRAY (FirstCall)": "azure",
            "AIRSCAN": "alice blue", "IMAGE": "light cyan", "3D/4D": "lavender blush",
            "CABLE (Functional Test)": "misty rose",
        }
        super().__init__(master, categories, colors, "Select Items",
                         on_done, columns_per_row=7, grouped_preview=True)
