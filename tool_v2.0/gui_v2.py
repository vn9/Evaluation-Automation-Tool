"""Tkinter front end: paste Helpdesk rows, OCR evaluation images, fill PDFs."""

import os
import re
import tempfile
import tkinter as tk
from datetime import datetime
from difflib import SequenceMatcher
from tkinter import filedialog, messagebox, ttk

import win32api

import utils_v2

# Repair descriptions the search box can offer, grouped by category and kept in
# the priority order used by the Selected Repairs list.
descriptions_by_category = {
    "Replacement": [
        "Lens", "Cap", "Array", "Shaft Housing", "Housing Strain Relief",
        "Cable", "Connector Strain Relief", "Connector Housing",
        "Connector Housing Label", "Connector Knob", "Connector Housing Frame",
    ],
    "Repair": [
        "Lens", "Lens Gap", "Cap", "Array", "Shaft Housing Halves Splits",
        "Housing Strain Relief", "Cable Jacket", "Connector Strain Relief",
        "Leak", "3D/4D", "Electrical",
    ],
    "Cosmetic": [
        "Shaft Housing", "Housing Strain Relief", "Connector Strain Relief",
        "Connector Housing", "Cable",
    ],
}

other_category = "Other"
repair_categories = tuple(descriptions_by_category) + (other_category,)

form_evaluation = "Evaluation"
form_final = "Final"

answer_yes = "yes"
answer_no = "no"

output_option_folder_and_pdf = "Folder and PDF"
output_option_folders_only = "Folders Only"
output_option_pdf_only = "PDF Only"
output_options = (
    output_option_folder_and_pdf,
    output_option_folders_only,
    output_option_pdf_only,
)

# Every Helpdesk row is trimmed/padded to exactly this many columns.
helpdesk_column_count = 4

# The Helpdesk columns this app reads, in the order it reads them.
helpdesk_field_names = ("Job", "Customer", "Model", "Serial")

# The file types the image list, the upload dialog and the file hint all share.
image_extensions = (".png", ".jpg", ".jpeg", ".bmp", ".pdf")
evaluation_glob = " ".join(f"*{ext}" for ext in image_extensions)
image_only_glob = " ".join(f"*{ext}" for ext in image_extensions if ext != ".pdf")


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Fillable PDF Forms")
        self.geometry("1280x650")
        self.minsize(1050, 600)

        try:
            self.iconbitmap(utils_v2.resource_path("processing_v2.ico"))
        except Exception as error:
            print(f"Could not load icon: {error}")

        self.image_paths = []
        self.temporary_image_paths = set()
        self.selected_repairs = []

        self.extracted_notes_text = ""
        self.info_text = ""
        self.repairs_text = ""
        self.notes_text = ""

        # Every (category, description) pair the search box can offer.
        self.repair_options = [
            (category, description)
            for category, descriptions in descriptions_by_category.items()
            for description in descriptions
        ]

        # OCR field name, and the label it shows in Extracted Output.
        self.comment_fields = [
            ("Lens", "Lens"),
            ("Cap", "Cap"),
            ("Array", "Array"),
            ("Shaft Housing", "Shaft Housing"),
            ("Housing Strain Relief", "Housing Strain Relief"),
            ("Cable", "Cable"),
            ("Connector Strain Relief", "Connector Strain Relief"),
            ("Connector Housing", "Connector Housing"),
            ("Connector", "Connector"),
            ("Airscan", "Airscan"),
            ("Color Artifacts", "Color Artifacts"),
            ("Image", "Image"),
            ("FirstCall", "FirstCall"),
            ("3D/4D Function", "3D/4D"),
        ]

        # Exact matching is still used first. Longest fields are checked first
        # so "Connector" does not steal "Connector Strain Relief".
        self.comment_field_patterns = [
            re.compile(rf"^{re.escape(field)}(?:\s|$)", flags=re.IGNORECASE)
            for field, _label in sorted(
                self.comment_fields, key=lambda entry: len(entry[0]), reverse=True
            )
        ]

        self.build_window()

        self.default_background = self.output_textbox.cget("background")

        self.refresh_repair_matches()
        self.update_form_state()

        self.bind_all("<Control-v>", self.handle_control_v, add="+")
        self.protocol("WM_DELETE_WINDOW", self.close_app)

    # ================================================================
    # Widget helpers
    # ================================================================

    def add_weighted_columns(self, frame, *weights, uniform=None):
        """Split a frame's extra width between columns, optionally in step."""
        for column, weight in enumerate(weights):
            frame.columnconfigure(column, weight=weight, uniform=uniform)

    def add_button(self, parent, text, command, width, pady):
        button = ttk.Button(parent, text=text, command=command, width=width)
        button.pack(fill="x", pady=pady)
        return button

    def add_radio_buttons(
        self, parent, variable, choices, command=None, start_column=0, padx=8
    ):
        buttons = []

        for offset, choice in enumerate(choices):
            button = ttk.Radiobutton(
                parent, text=choice, value=choice, variable=variable, command=command
            )
            button.grid(row=0, column=start_column + offset, sticky="w", padx=padx)
            buttons.append(button)

        return buttons

    def add_scrolling_frame(self, parent, frame_options=None, canvas_options=None):
        """Build the canvas + scrollbar + inner frame trio used by both scroll areas.

        Returns (container, canvas, scrollbar, inner_frame). The caller places
        the three widgets, because one caller packs and the other grids.
        """
        container = ttk.Frame(parent)
        canvas = tk.Canvas(
            container, highlightthickness=0, **(canvas_options or {})
        )
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas, **(frame_options or {}))

        inner.bind(
            "<Configure>",
            lambda event: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        window = canvas.create_window((0, 0), window=inner, anchor="nw")

        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(window, width=event.width),
        )

        canvas.configure(yscrollcommand=scrollbar.set)

        return container, canvas, scrollbar, inner

    def set_widgets_enabled(self, widgets, enabled):
        state = "!disabled" if enabled else "disabled"

        for widget in widgets:
            widget.state([state])

    def set_textbox_enabled(self, widget, enabled):
        if enabled:
            widget.configure(state="normal", background=self.default_background)
        else:
            widget.configure(state="disabled", background="#f0f0f0")

    # ================================================================
    # Window layout
    # ================================================================

    def build_window(self):
        outer, canvas, scrollbar, self.main_frame = self.add_scrolling_frame(
            self, frame_options={"padding": 10}
        )

        outer.pack(fill="both", expand=True)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.add_weighted_columns(self.main_frame, 1)

        self.build_form_section()
        self.build_workflow_row()
        self.build_repairs_section()
        self.build_bottom_section()

    def build_form_section(self):
        frame = ttk.LabelFrame(self.main_frame, text="Form", padding=10)
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(
            frame, text="Which form would you like to work with?", font=("Arial", 11)
        ).grid(row=0, column=0, sticky="w")

        self.form_var = tk.StringVar(value=form_evaluation)

        self.add_radio_buttons(
            frame,
            self.form_var,
            (form_evaluation, form_final),
            self.update_form_state,
            start_column=1,
        )

    def build_workflow_row(self):
        row = ttk.Frame(self.main_frame)
        row.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        self.add_weighted_columns(row, 5, 3, 5, uniform="workflow")

        self.build_helpdesk_panel(row)
        self.build_image_panel(row)
        self.build_output_panel(row)

    def build_helpdesk_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Helpdesk Data", padding=10)
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.add_weighted_columns(frame, 1)

        ttk.Label(
            frame,
            text="Paste your data copied from Helpdesk here:",
            font=("Arial", 10),
        ).grid(row=0, column=0, sticky="w", pady=(0, 5))

        self.input_textbox = tk.Text(frame, height=6, wrap="none")
        self.input_textbox.grid(row=1, column=0, sticky="nsew")
        self.input_textbox.bind("<<Paste>>", self.on_helpdesk_paste)

    def build_image_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Evaluation Images", padding=10)
        frame.grid(row=0, column=1, sticky="nsew", padx=5)
        self.image_panel = frame
        self.add_weighted_columns(frame, 3, 2)

        ttk.Label(
            frame,
            text="Add or paste evaluation screenshots:",
            font=("Arial", 10),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))

        self.image_listbox = tk.Listbox(frame, height=5, exportselection=False)
        self.image_listbox.grid(row=1, column=0, sticky="nsew", padx=(0, 8))

        buttons = ttk.Frame(frame)
        buttons.grid(row=1, column=1, sticky="ns")

        self.add_images_button = self.add_button(
            buttons, "Upload Images...", self.add_images, 18, (0, 5)
        )
        self.paste_image_button = self.add_button(
            buttons, "Paste Image", self.paste_image_from_clipboard, 18, 5
        )
        self.extract_evaluation_button = self.add_button(
            buttons, "Extract Evaluation", self.extract_evaluation, 18, 5
        )

        # The hint lists the same file types the upload dialog and the
        # clipboard filter accept.
        ttk.Label(
            frame, text=", ".join(ext[1:].upper() for ext in image_extensions)
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))

    def build_output_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Extracted Output", padding=10)
        frame.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
        self.output_panel = frame
        self.add_weighted_columns(frame, 1)

        ttk.Label(
            frame,
            text="Evaluation notes appear here. You can edit them before processing.",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))

        self.output_textbox = tk.Text(frame, height=6, wrap="word")
        self.output_textbox.grid(row=1, column=0, sticky="nsew")

    def build_repairs_section(self):
        frame = ttk.LabelFrame(self.main_frame, text="Repairs", padding="0 10")
        frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self.repairs_panel = frame
        self.add_weighted_columns(frame, 5, 3, 5, uniform="repair")

        question = ttk.Frame(frame)
        question.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        ttk.Label(
            question, text="Do you need to fill in the repair part?"
        ).grid(row=0, column=0, sticky="w")

        self.rep_var = tk.StringVar(value=answer_no)

        self.repair_answer_buttons = self.add_radio_buttons(
            question,
            self.rep_var,
            (answer_yes, answer_no),
            self.update_repair_state,
            start_column=1,
        )

        self.build_find_repairs_panel(frame)
        self.build_custom_repair_panel(frame)
        self.build_selected_repairs_panel(frame)

    def build_find_repairs_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Find Repairs", padding=8)
        frame.grid(row=1, column=0, sticky="nsew", padx=(0, 5))
        self.add_weighted_columns(frame, 1)

        self.repair_search_var = tk.StringVar()
        self.repair_search_var.trace_add("write", self.on_repair_search_changed)

        self.repair_search_hint = ttk.Label(
            frame, text="Search repairs below", foreground="#555555"
        )
        self.repair_search_hint.grid(row=0, column=0, sticky="w", pady=(0, 3))
        self.repair_search_hint.grid_remove()

        search_row = ttk.Frame(frame)
        search_row.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        self.add_weighted_columns(search_row, 1)

        self.repair_search_well = tk.Frame(
            search_row, bd=0, highlightthickness=2, highlightbackground="#bdbdbd"
        )
        self.repair_search_well.grid(row=0, column=0, sticky="ew")
        self.add_weighted_columns(self.repair_search_well, 1)

        self.repair_search_entry = ttk.Entry(
            self.repair_search_well, textvariable=self.repair_search_var
        )
        self.repair_search_entry.grid(row=0, column=0, sticky="ew", padx=2, pady=2)

        self.clear_search_button = ttk.Button(
            search_row, text="X", width=2, command=self.clear_repair_search
        )
        self.clear_search_button.place(
            in_=self.repair_search_entry, relx=1.0, rely=0.5, anchor="e", x=-4
        )

        (
            self.repair_results_container,
            self.repair_results_canvas,
            self.repair_results_scrollbar,
            self.repair_results_frame,
        ) = self.add_scrolling_frame(frame, canvas_options={"height": 120})

        self.repair_results_container.grid(row=2, column=0, sticky="nsew")
        self.add_weighted_columns(self.repair_results_container, 1)
        self.repair_results_container.rowconfigure(0, weight=1)

        self.repair_results_canvas.grid(row=0, column=0, sticky="nsew")
        self.repair_results_scrollbar.grid(row=0, column=1, sticky="ns")

        for scroll_target in (
            self.repair_results_canvas,
            self.repair_results_frame,
            self.repair_results_container,
        ):
            scroll_target.bind("<MouseWheel>", self.on_results_mousewheel)

        self.repair_check_vars = {}
        self.repair_checkbuttons = {}

        self.repair_no_match_label = ttk.Label(frame, text="No matching repairs")
        self.repair_no_match_label.grid(row=2, column=0, sticky="w")
        self.repair_no_match_label.grid_remove()

        self.repair_results_container.grid_remove()

    def build_custom_repair_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Custom Repair", padding=8)
        frame.grid(row=1, column=1, sticky="nsew", padx=5)
        self.add_weighted_columns(frame, 1)

        self.custom_toggle_var = tk.BooleanVar(value=False)
        self.custom_toggle = ttk.Checkbutton(
            frame,
            text="Add Custom Repair",
            variable=self.custom_toggle_var,
            command=self.on_custom_repair_toggled,
        )
        self.custom_toggle.grid(row=0, column=0, sticky="w")

        self.custom_fields = ttk.Frame(frame)
        self.custom_fields.grid(row=1, column=0, sticky="nsew")
        self.add_weighted_columns(self.custom_fields, 1)

        ttk.Label(self.custom_fields, text="Category").grid(
            row=0, column=0, sticky="w", pady=(6, 2)
        )

        self.custom_category_var = tk.StringVar(value=repair_categories[0])
        self.custom_category_combo = ttk.Combobox(
            self.custom_fields,
            textvariable=self.custom_category_var,
            values=list(repair_categories),
            state="readonly",
        )
        self.custom_category_combo.grid(row=1, column=0, sticky="ew", pady=(2, 6))

        ttk.Label(self.custom_fields, text="Description").grid(
            row=2, column=0, sticky="w"
        )

        self.custom_description_var = tk.StringVar()
        self.custom_description_entry = ttk.Entry(
            self.custom_fields, textvariable=self.custom_description_var
        )
        self.custom_description_entry.grid(row=3, column=0, sticky="ew", pady=(2, 6))
        self.custom_description_entry.bind(
            "<Return>", lambda event: self.add_custom_repair()
        )

        self.add_custom_button = ttk.Button(
            self.custom_fields,
            text="Add Custom Repair",
            command=self.add_custom_repair,
        )
        self.add_custom_button.grid(row=4, column=0, sticky="w")

        self.custom_fields.grid_remove()

    def build_selected_repairs_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Selected Repairs", padding=8)
        frame.grid(row=1, column=2, sticky="nsew", padx=(5, 0))
        self.add_weighted_columns(frame, 1)

        self.selected_repairs_listbox = tk.Listbox(
            frame, height=5, exportselection=False
        )
        self.selected_repairs_listbox.grid(
            row=1, column=0, sticky="nsew", padx=(0, 10)
        )

        buttons = ttk.Frame(frame)
        buttons.grid(row=1, column=1, sticky="ns")

        self.remove_repair_button = self.add_button(
            buttons, "Remove", self.remove_selected_repair, 14, 6
        )

        self.listbox_repair_by_index = {}

    def build_bottom_section(self):
        frame = ttk.Frame(self.main_frame)
        frame.grid(row=3, column=0, sticky="ew")
        self.add_weighted_columns(frame, 1)

        options = ttk.LabelFrame(frame, text="Output Options", padding=9)
        options.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self.var_option = tk.StringVar(value=output_option_folder_and_pdf)
        self.output_option_buttons = self.add_radio_buttons(
            options,
            self.var_option,
            output_options,
            self.update_print_option_state,
            padx=(0, 24),
        )

        ttk.Separator(options, orient="vertical").grid(
            row=0, column=3, sticky="ns", padx=(0, 30)
        )

        ttk.Label(options, text="Print File:").grid(
            row=0, column=4, sticky="w", padx=(0, 8)
        )

        self.print_var = tk.StringVar(value=answer_no)
        self.print_buttons = self.add_radio_buttons(
            options, self.print_var, (answer_yes, answer_no), start_column=5
        )

        actions = ttk.Frame(frame)
        actions.grid(row=0, column=1, sticky="e")

        self.clear_all_button = ttk.Button(
            actions, text="Clear All", command=self.clear_all, width=24
        )
        self.clear_all_button.pack(fill="x", pady=(0, 5))

        self.process_button = ttk.Button(
            actions, text="Process", command=self.process_data, width=24
        )
        self.process_button.pack(fill="x", ipady=8)

        self.status = tk.StringVar(value="Ready")

        ttk.Label(
            self.main_frame, textvariable=self.status, relief="sunken", anchor="w"
        ).grid(row=4, column=0, sticky="ew", pady=(8, 0))

        self.update_print_option_state()

    # ================================================================
    # Enable/disable rules
    # ================================================================

    def update_print_option_state(self):
        folders_only = self.var_option.get() == output_option_folders_only

        if folders_only:
            self.print_var.set(answer_no)

        self.set_widgets_enabled(self.print_buttons, not folders_only)

    def update_form_state(self):
        evaluation_enabled = self.form_var.get() == form_evaluation

        self.set_textbox_enabled(self.image_listbox, evaluation_enabled)
        self.set_textbox_enabled(self.output_textbox, evaluation_enabled)

        self.set_widgets_enabled(
            (
                self.add_images_button,
                self.paste_image_button,
                self.extract_evaluation_button,
                *self.repair_answer_buttons,
            ),
            evaluation_enabled,
        )

        self.update_repair_state()

    # ================================================================
    # Helpdesk parsing
    # ================================================================

    def clean_helpdesk_cell(self, value):
        value = value.strip()

        link_match = re.fullmatch(r"\[(.*?)\]\((.*?)\)", value)

        if link_match:
            value = link_match.group(1)

        value = value.replace("**", "")
        value = re.sub(r"<br\s*/?>", "", value, flags=re.IGNORECASE)

        return value.strip()

    def split_helpdesk_row(self, columns):
        if len(columns) == 9:
            return [columns[0], columns[4], columns[6], columns[8]]

        if len(columns) == helpdesk_column_count:
            return columns

        if len(columns) == 3:
            if not columns[0].isnumeric():
                return ["", *columns]

            return [*columns, ""]

        return None

    def extract_data(self):
        text_content = self.input_textbox.get("1.0", tk.END)

        if not text_content.strip():
            messagebox.showwarning("Empty Text", "Please paste Helpdesk data first.")
            return []

        extracted_rows = []
        errors = []
        row_number = 0

        for line in text_content.splitlines():
            stripped_line = line.strip()

            if not stripped_line:
                continue

            # A markdown table separator such as "|---|---|" is not a data row.
            if stripped_line.startswith("|") and re.fullmatch(
                r"[\s|:\-]+", stripped_line
            ):
                continue

            row_number += 1

            if "\t" in line:
                raw_columns = line.split("\t")

            elif stripped_line.startswith("|") and stripped_line.endswith("|"):
                raw_columns = stripped_line.strip("|").split("|")

            else:
                errors.append(f"Row {row_number} could not be recognized.")
                continue

            columns = [
                self.clean_helpdesk_cell(value) for value in raw_columns
            ]

            row = self.split_helpdesk_row(columns)

            if row is None:
                errors.append(f"Row {row_number} has the wrong number of columns.")
                continue

            row = (row + [""] * helpdesk_column_count)[:helpdesk_column_count]
            extracted_rows.append(row)

            for _index, field_name in self.find_missing_fields([row]):
                errors.append(f"Row {row_number} is missing {field_name}.")

        if errors:
            messagebox.showwarning("Helpdesk Data Error", "\n".join(errors))
            return []

        return extracted_rows

    def format_pdf_info(self, row):
        return (
            f"Job#: {row[0]}\n"
            f"Model: {row[2]}\n"
            f"S/N: {row[3]}\n"
            f"Customer: {row[1]}"
        )

    def make_copy_text(self, rows):
        return "\n".join("\t".join(row) for row in rows)

    def on_helpdesk_paste(self, event=None):
        self.after_idle(self.auto_extract_helpdesk)

    def auto_extract_helpdesk(self):
        text = self.input_textbox.get("1.0", tk.END)

        if not text.strip():
            return

        rows = self.extract_data()

        if not rows:
            return

        self.input_textbox.delete("1.0", "end")
        self.input_textbox.insert("1.0", self.make_copy_text(rows))
        self.status.set(f"Extracted {len(rows)} Helpdesk row(s).")

    def find_missing_fields(self, rows):
        missing_fields = []

        for index, row in enumerate(rows, start=1):
            for field_index, field_name in enumerate(helpdesk_field_names):
                if field_index >= len(row) or not row[field_index].strip():
                    missing_fields.append((index, field_name))

        return missing_fields

    # ================================================================
    # Clipboard image paste
    # ================================================================

    def handle_control_v(self, event=None):
        focused_widget = self.focus_get()

        if focused_widget is None:
            self.paste_image_from_clipboard()
            return "break"

        text_classes = {"Text", "Entry", "TEntry", "TCombobox", "Spinbox", "TSpinbox"}

        if focused_widget.winfo_class() in text_classes:
            return None

        self.paste_image_from_clipboard()
        return "break"

    def paste_image_from_clipboard(self):
        try:
            from PIL import ImageGrab
        except ImportError:
            messagebox.showerror(
                "Missing Pillow",
                "Pillow is required to paste screenshots.\n\n"
                "Run:\n"
                "python -m pip install Pillow",
            )
            return

        clipboard_content = ImageGrab.grabclipboard()

        # A file copy arrives as a list of paths; an image copy as an object.
        if isinstance(clipboard_content, list):
            image_files = [
                path
                for path in clipboard_content
                if self.is_supported_image_file(path)
            ]

            if not image_files:
                messagebox.showwarning(
                    "No Image", "The clipboard does not contain a supported image."
                )
                return

            for path in image_files:
                self.add_image_path(path)

            self.status.set(f"Added {len(image_files)} image(s) from clipboard.")
            return

        if clipboard_content is None or not hasattr(clipboard_content, "save"):
            messagebox.showwarning(
                "No Image", "The clipboard does not contain an image."
            )
            return

        temp_folder = os.path.join(tempfile.gettempdir(), "evaluation_automation_tool")
        os.makedirs(temp_folder, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        file_path = os.path.join(temp_folder, f"pasted_image_{timestamp}.png")

        clipboard_content.save(file_path, "PNG")

        self.temporary_image_paths.add(file_path)
        self.add_image_path(file_path)
        self.status.set("Pasted screenshot added.")

    # ================================================================
    # Evaluation image list
    # ================================================================

    def is_supported_image_file(self, path):
        return os.path.splitext(path)[1].lower() in image_extensions

    def add_image_path(self, path):
        if path in self.image_paths:
            return

        self.image_paths.append(path)
        self.image_listbox.insert("end", os.path.basename(path))

    def add_images(self):
        paths = filedialog.askopenfilenames(
            title="Select Evaluation Images",
            filetypes=[
                ("Evaluation files", evaluation_glob),
                ("Image files", image_only_glob),
                ("PDF files", "*.pdf"),
                ("All files", "*.*"),
            ],
        )

        for path in paths:
            self.add_image_path(path)

    def clear_images(self):
        for path in list(self.image_paths):
            self.delete_temporary_image(path)

        self.image_paths.clear()
        self.image_listbox.delete(0, "end")

    def delete_temporary_image(self, path):
        if path not in self.temporary_image_paths:
            return

        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

        self.temporary_image_paths.discard(path)

    # ================================================================
    # Evaluation OCR
    # ================================================================

    def extract_evaluation(self):
        if not self.image_paths:
            messagebox.showwarning(
                "No Images", "Add or paste at least one evaluation image first."
            )
            return

        try:
            combined_text = "\n".join(
                self.read_evaluation_file(path) for path in self.image_paths
            )

            notes = self.parse_comment_fields(combined_text)

            if not notes:
                self.clear_output()

                messagebox.showwarning(
                    "No Comments Found",
                    "No populated Comment(s) fields were detected.\n\n"
                    "Only fields with actual comment text are extracted.",
                )

                return

            self.extracted_notes_text = notes
            self.render_output()
            self.status.set("Evaluation comments extracted.")

        except Exception as error:
            messagebox.showerror(
                "Evaluation Extraction Error",
                f"Could not read the evaluation image(s).\n\n{error}",
            )

    def read_evaluation_file(self, path):
        if os.path.splitext(path)[1].lower() == ".pdf":
            return self.read_pdf_with_ocr(path)

        return self.read_image_with_ocr(path)

    def set_tesseract_path(self, pytesseract):
        """Prefer the bundled Tesseract, then a standard install."""
        bundled_path = utils_v2.resource_path(
            os.path.join("Tesseract-OCR", "tesseract.exe")
        )
        bundled_tessdata = utils_v2.resource_path(
            os.path.join("Tesseract-OCR", "tessdata")
        )
        common_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]

        if os.path.exists(bundled_path):
            pytesseract.pytesseract.tesseract_cmd = bundled_path

            if os.path.isdir(bundled_tessdata):
                os.environ["TESSDATA_PREFIX"] = bundled_tessdata

            return

        for common_path in common_paths:
            if os.path.exists(common_path):
                pytesseract.pytesseract.tesseract_cmd = common_path
                return

        raise FileNotFoundError(
            "Tesseract OCR could not be found.\n\n"
            "Make sure the Tesseract-OCR folder is included with the application."
        )

    def load_ocr_libraries(self, need_pdf=False):
        """Import the OCR libraries on demand and return them ready to use."""
        try:
            import pytesseract

            from PIL import Image, ImageOps

            fitz = None

            if need_pdf:
                import fitz

        except ImportError as error:
            if need_pdf:
                title = "PDF OCR packages are missing."
                packages = "PyMuPDF Pillow pytesseract"
            else:
                title = "OCR packages are missing."
                packages = "Pillow pytesseract"

            raise RuntimeError(
                f"{title}\n\nRun:\npython -m pip install {packages}"
            ) from error

        self.set_tesseract_path(pytesseract)

        return pytesseract, Image, ImageOps, fitz

    def ocr_text_from_image(self, image, pytesseract, imageops):
        gray = imageops.grayscale(image)
        gray = imageops.autocontrast(gray)

        return pytesseract.image_to_string(gray, config="--psm 6")

    def read_image_with_ocr(self, path):
        pytesseract, image_module, image_ops, _ = self.load_ocr_libraries()

        with image_module.open(path) as image:
            return self.ocr_text_from_image(image, pytesseract, image_ops)

    def read_pdf_with_ocr(self, path):
        pytesseract, image_module, image_ops, fitz = self.load_ocr_libraries(
            need_pdf=True
        )

        document = fitz.open(path)
        text_parts = []

        try:
            for page in document:
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image = image_module.frombytes(
                    "RGB", [pixmap.width, pixmap.height], pixmap.samples
                )
                text_parts.append(
                    self.ocr_text_from_image(image, pytesseract, image_ops)
                )
        finally:
            document.close()

        return "\n".join(text_parts)

    # ================================================================
    # Comment extraction
    # ================================================================

    def parse_comment_fields(self, text):
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        results = []

        for field, label in self.comment_fields:
            comment_lines = self.find_comment_value(field, lines)

            if not comment_lines:
                continue

            results.append(f"{label}: {', '.join(comment_lines)}")

        return "\n".join(results)

    def normalize_ocr_field_text(self, text):
        """Normalize a form-field label so OCR spacing/punctuation cannot block a match.

        Only labels such as "3D/4D Function", "FirstCall" or
        "Connector Strain Relief" pass through here. Technician comment
        content is never changed.
        """
        # OCR sometimes inserts an apostrophe, quote or similar character first.
        text = text.strip().lstrip("'\"`‘’|:;,. ")

        # Drop spaces and punctuation so formatting differences do not matter.
        return re.sub(r"[^a-z0-9]+", "", text.lower())

    def match_ocr_field_name(self, text, threshold=0.75):
        """Match OCR-read text against a known evaluation field name.

        OCR may read "3D/4D Function" as "80/40 Function" or "8D/4D Function".
        Instead of hard-coding every possible OCR typo, compare the OCR label
        with the known field names and accept a close enough match.
        """
        normalized_text = self.normalize_ocr_field_text(text)

        if not normalized_text:
            return None

        best_field = None
        best_score = 0.0

        for field, _label in self.comment_fields:
            normalized_field = self.normalize_ocr_field_text(field)

            # Exact normalized match wins immediately.
            if normalized_text == normalized_field:
                return field

            score = SequenceMatcher(None, normalized_text, normalized_field).ratio()

            if score > best_score:
                best_score = score
                best_field = field

        return best_field if best_score >= threshold else None

    def split_ocr_comment_line(self, line):
        """Split a "Comment(s)" line into (canonical field, comment value).

        Only the field label is fuzzy matched; the comment itself is not modified.
        """
        match = re.match(
            r"^(.*?)\s+comment\s*(?:\(\s*s\s*\)|s)?\s*:?\s*(.*)$",
            line.strip(),
            flags=re.IGNORECASE,
        )

        if not match:
            return None, ""

        field_text = match.group(1).strip()
        comment_text = match.group(2).strip()
        matched_field = self.match_ocr_field_name(field_text)

        return matched_field, comment_text

    def get_ocr_field_candidate(self, line):
        """Return only the field-label portion of a line that looks like a form row.

        This prevents normal technician comments from being fuzzy matched
        as field names.
        """
        stripped_line = line.strip()

        # Comment row, e.g. "3D/4D Function Comment(s) Can't find home".
        comment_match = re.match(
            r"^(.*?)\s+comment\s*(?:\(\s*s\s*\)|s)?\b",
            stripped_line,
            flags=re.IGNORECASE,
        )

        if comment_match:
            return comment_match.group(1).strip()

        # Status row, e.g. "3D/4D Function Fail" or "Cable Pass".
        status_match = re.match(
            r"^(.*?)\s+(?:pass|fail|ok|n/?a)\b",
            stripped_line,
            flags=re.IGNORECASE,
        )

        if status_match:
            return status_match.group(1).strip()

        return None

    def find_comment_value(self, field, lines):
        """Find the comment for one canonical field.

        If OCR slightly changes the next field name, fuzzy field matching still
        detects it as a new form row so it does not get appended to the
        previous comment.
        """
        for index, line in enumerate(lines):
            matched_field, same_line_value = self.split_ocr_comment_line(line)

            if matched_field != field:
                continue

            comment_lines = []

            if self.is_valid_comment_text(same_line_value):
                comment_lines.append(same_line_value)

            for next_line in lines[index + 1:]:
                if self.is_form_field_line(next_line):
                    break

                if self.is_valid_comment_text(next_line):
                    comment_lines.append(next_line)

            return comment_lines

        return []

    def is_valid_comment_text(self, value):
        ignored_values = {"(s)", "s", ":", "n/a", "pass", "fail"}

        if not value or value.lower() in ignored_values:
            return False

        return re.fullmatch(r"\d+", value) is None

    def is_form_field_line(self, line):
        stripped_line = line.strip()

        # Use exact matching first.
        if any(
            pattern.match(stripped_line) for pattern in self.comment_field_patterns
        ):
            return True

        # Only use fuzzy matching when the line looks like a real form row.
        candidate = self.get_ocr_field_candidate(stripped_line)

        if not candidate:
            return False

        return self.match_ocr_field_name(candidate) is not None

    # ================================================================
    # Extracted Output
    # ================================================================

    def render_output(self):
        self.output_textbox.delete("1.0", "end")

        if self.extracted_notes_text:
            self.output_textbox.insert("1.0", "Notes:\n" + self.extracted_notes_text)

    def clear_output(self):
        self.extracted_notes_text = ""
        self.render_output()

    def get_notes_from_output(self):
        text = self.output_textbox.get("1.0", "end").strip()

        if not text:
            return ""

        marker = "Notes:"

        if text.startswith(marker):
            return text[len(marker):].strip()

        return text

    # ================================================================
    # Repair search
    # ================================================================

    def repairs_enabled(self):
        """True when the Evaluation form is active and repairs were requested."""
        return (
            self.form_var.get() == form_evaluation
            and self.rep_var.get() == answer_yes
        )

    def on_repair_search_changed(self, *args):
        self.refresh_repair_matches()

    def find_matching_repairs(self, query):
        words = query.split()

        matches = []

        for category, description in self.repair_options:
            searchable_text = f"{category} {description}".lower()

            if all(word in searchable_text for word in words):
                matches.append(f"{category}: {description}")

        return matches

    def clear_repair_checkboxes(self):
        for child in self.repair_results_frame.winfo_children():
            child.destroy()

        self.repair_check_vars = {}
        self.repair_checkbuttons = {}

    def refresh_repair_matches(self):
        if not hasattr(self, "repair_results_frame"):
            return

        query = self.repair_search_var.get().strip().lower()

        self.clear_repair_checkboxes()

        if not query:
            self.repair_results_container.grid_remove()
            self.repair_no_match_label.grid_remove()
            return

        matches = self.find_matching_repairs(query)
        enabled = self.repairs_enabled()

        for repair_text in matches:
            check_variable = tk.BooleanVar(value=repair_text in self.selected_repairs)
            command = lambda text=repair_text: self.on_repair_check_toggled(text)

            checkbutton = ttk.Checkbutton(
                self.repair_results_frame,
                text=repair_text,
                variable=check_variable,
                command=command,
            )

            checkbutton.pack(anchor="w")
            checkbutton.bind("<MouseWheel>", self.on_results_mousewheel)

            if not enabled:
                checkbutton.state(["disabled"])

            self.repair_check_vars[repair_text] = check_variable
            self.repair_checkbuttons[repair_text] = checkbutton

        if matches:
            self.repair_no_match_label.grid_remove()
            self.repair_results_container.grid()
        else:
            self.repair_results_container.grid_remove()
            self.repair_no_match_label.grid()

    def on_results_mousewheel(self, event):
        self.repair_results_canvas.yview_scroll(int(-event.delta / 120), "units")

    def on_repair_check_toggled(self, repair_text):
        if self.repair_check_vars[repair_text].get():
            category, description = repair_text.split(": ", 1)
            self.add_repair(category, description)
        else:
            self.remove_repair(repair_text)

    def add_repair(self, category, description):
        repair_text = f"{category}: {description}"

        if repair_text in self.selected_repairs:
            return False

        self.selected_repairs.append(repair_text)
        self.refresh_selected_repairs()

        return True

    def remove_repair(self, repair_text):
        if repair_text not in self.selected_repairs:
            return

        self.selected_repairs.remove(repair_text)
        self.refresh_selected_repairs()

    def clear_repair_search(self):
        self.repair_search_var.set("")
        self.repair_search_entry.focus_set()

    def on_custom_repair_toggled(self):
        if self.custom_toggle_var.get():
            self.custom_fields.grid()
        else:
            self.custom_fields.grid_remove()

    def add_custom_repair(self):
        description = self.custom_description_var.get().strip()

        if not description:
            messagebox.showwarning(
                "Missing Description", "Enter a custom repair description."
            )
            return

        category = self.custom_category_var.get().strip() or other_category

        self.add_repair(category, description)

        self.custom_description_var.set("")
        self.custom_description_entry.focus_set()

    def remove_selected_repair(self):
        selected = self.selected_repairs_listbox.curselection()

        if not selected:
            return

        repair_text = self.listbox_repair_by_index.get(selected[0])

        if repair_text is None:
            return

        self.remove_repair(repair_text)

    def clear_repairs(self):
        self.selected_repairs.clear()
        self.refresh_selected_repairs()

        self.repair_search_var.set("")
        self.refresh_repair_matches()

    def refresh_selected_repairs(self):
        self.selected_repairs_listbox.delete(0, "end")
        self.listbox_repair_by_index = {}
        lines = []

        for category in repair_categories:
            for repair_text in self.selected_repairs:
                if not repair_text.startswith(f"{category}: "):
                    continue

                index = len(lines)
                self.listbox_repair_by_index[index] = repair_text
                lines.append(f"{index + 1}. {repair_text}")

        for line in lines:
            self.selected_repairs_listbox.insert("end", line)

        self.repairs_text = "\n".join(lines)

        for repair_text, check_variable in self.repair_check_vars.items():
            check_variable.set(repair_text in self.selected_repairs)

    def update_repair_state(self):
        if not hasattr(self, "repair_search_entry"):
            return

        enabled = self.repairs_enabled()
        entry_state = "normal" if enabled else "disabled"

        for widget in (self.repair_search_entry, self.custom_description_entry):
            widget.configure(state=entry_state)

        self.custom_category_combo.configure(
            state="readonly" if enabled else "disabled"
        )

        self.set_textbox_enabled(self.selected_repairs_listbox, enabled)

        self.repair_search_well.configure(
            highlightbackground="#4a90d9" if enabled else "#bdbdbd"
        )

        if enabled:
            self.repair_search_hint.grid()
        else:
            self.repair_search_hint.grid_remove()

        self.set_widgets_enabled(self.repair_checkbuttons.values(), enabled)

        self.set_widgets_enabled(
            (
                self.custom_toggle,
                self.add_custom_button,
                self.remove_repair_button,
                self.clear_search_button,
            ),
            enabled,
        )

    # ================================================================
    # Folder creation
    # ================================================================

    def get_folder_suffix(self):
        return "F" if self.form_var.get() == form_final else "E"

    def make_folder_name(self, row):
        job, customer, model, serial = row
        suffix = self.get_folder_suffix()

        return f"{job}-{model} {serial} (#{job}{suffix}-{customer})"

    def choose_output_folder(self, title):
        rows = self.extract_data()

        if not rows:
            return None, []

        output_path = filedialog.askdirectory(title=title)

        if not output_path:
            return None, []

        return output_path, rows

    def create_folders_for_all_rows(self):
        output_path, rows = self.choose_output_folder(
            "Select Folder to Save New Folders"
        )

        if not output_path:
            return []

        created_folders = []

        try:
            for row in rows:
                full_path = os.path.join(output_path, self.make_folder_name(row))
                os.makedirs(full_path, exist_ok=True)
                created_folders.append(full_path)

            self.status.set(f"Created {len(created_folders)} folder(s).")

            messagebox.showinfo(
                "Folders Created",
                f"Created {len(created_folders)} folder(s) successfully.",
            )

            return created_folders

        except Exception as error:
            messagebox.showerror(
                "Folder Error", f"Could not create the folders.\n\n{error}"
            )
            return []

    def create_first_folder(self):
        output_path, rows = self.choose_output_folder(
            "Select Folder to Save New Folder"
        )

        if not output_path:
            return ""

        folder_name = self.make_folder_name(rows[0])
        full_path = os.path.join(output_path, folder_name)

        try:
            os.makedirs(full_path, exist_ok=True)

            self.status.set(f"Folder created: {full_path}")

            messagebox.showinfo(
                "Folder Created", f"Folder created successfully:\n{folder_name}"
            )

            return full_path

        except Exception as error:
            messagebox.showerror(
                "Folder Error", f"Could not create the folder.\n\n{error}"
            )
            return ""

    # ================================================================
    # PDF creation
    # ================================================================

    def confirm_empty_repairs(self, is_final):
        if is_final or self.rep_var.get() != answer_yes or self.repairs_text.strip():
            return True

        return messagebox.askyesno(
            "No Repairs Selected",
            "You chose Yes for repairs, but no repairs are selected.\n\n"
            "Continue with an empty Required Repairs field?",
        )

    def build_pdf_field_values(self, row, is_final):
        self.info_text = self.format_pdf_info(row)
        self.notes_text = "" if is_final else self.get_notes_from_output()
        repairs_text = self.repairs_text if self.rep_var.get() == answer_yes else ""

        return {
            utils_v2.pdf_info_field: self.info_text,
            utils_v2.pdf_repairs_field: "" if is_final else repairs_text,
            utils_v2.pdf_notes_field: self.notes_text,
        }

    def prepare_pdf(self):
        is_final = self.form_var.get() == form_final
        original_file = "preship5.pdf" if is_final else "ev7.pdf"
        source_pdf = utils_v2.resource_path(original_file)

        if not os.path.exists(source_pdf):
            messagebox.showerror("Missing File", f"Input PDF not found:\n{source_pdf}")
            return ""

        rows = self.extract_data()

        if not rows:
            return ""

        data = self.build_pdf_field_values(rows[0], is_final)

        if not self.confirm_empty_repairs(is_final):
            return ""

        try:
            writer = utils_v2.fill_pdf_fields(source_pdf, data)
            output_folder = filedialog.askdirectory(title="Select Folder to Save PDF")

            if not output_folder:
                return ""

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"{original_file[:-4]}_filled_{timestamp}.pdf"
            destination_pdf = os.path.join(output_folder, file_name)

            with open(destination_pdf, "wb") as pdf_file:
                writer.write(pdf_file)

            self.status.set(f"PDF saved at: {destination_pdf}")

            messagebox.showinfo("Done", f"New PDF saved:\n{destination_pdf}")

            return destination_pdf

        except Exception as error:
            messagebox.showerror("PDF Error", f"Could not fill the PDF.\n\n{error}")
            return ""

    # ================================================================
    # Processing
    # ================================================================

    def process_data(self):
        option = self.var_option.get()

        if option == output_option_folders_only:
            self.create_folders_for_all_rows()
            return

        if option == output_option_pdf_only:
            self.print_pdf_if_requested(self.prepare_pdf())
            return

        folder_path = self.create_first_folder()

        if not folder_path:
            return

        self.print_pdf_if_requested(self.prepare_pdf())

    def print_pdf_if_requested(self, pdf_path):
        if pdf_path and self.print_var.get() == answer_yes:
            self.print_pdf(pdf_path)

    def clear_all(self):
        self.form_var.set(form_evaluation)
        self.rep_var.set(answer_yes)
        self.update_form_state()

        self.input_textbox.delete("1.0", tk.END)

        self.clear_images()
        self.clear_output()
        self.clear_repairs()

        self.custom_category_var.set(repair_categories[0])
        self.custom_description_var.set("")
        self.custom_toggle_var.set(False)
        self.on_custom_repair_toggled()

        self.var_option.set(output_option_folder_and_pdf)
        self.print_var.set(answer_no)
        self.rep_var.set(answer_no)

        self.info_text = ""
        self.notes_text = ""
        self.repairs_text = ""

        self.update_print_option_state()
        self.update_form_state()
        self.status.set("Ready")

    # ================================================================
    # Printing
    # ================================================================

    def print_pdf(self, pdf_path):
        if not pdf_path or not os.path.exists(pdf_path):
            messagebox.showwarning(
                "No PDF", "The generated PDF could not be found."
            )
            return

        try:
            win32api.ShellExecute(0, "print", pdf_path, None, ".", 0)

            self.status.set(f"PDF saved and sent to printer: {pdf_path}")

        except Exception as error:
            messagebox.showerror(
                "Print Error",
                f"The PDF was saved, but it could not be printed.\n\n{error}",
            )

    # ================================================================
    # Cleanup
    # ================================================================

    def close_app(self):
        for path in list(self.temporary_image_paths):
            self.delete_temporary_image(path)

        self.destroy()
