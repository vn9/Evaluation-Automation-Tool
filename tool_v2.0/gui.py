import os
import re
import tempfile
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

import win32api

import utils


# Repair descriptions the search box can offer, grouped by category and kept in
# the priority order used by the Selected Repairs list.
descriptions_by_category = {
    "Replacement": [
        "Lens",
        "Cap",
        "Array",
        "Shaft Housing",
        "Housing Strain Relief",
        "Cable",
        "Connector Strain Relief",
        "Connector Housing",
        "Connector Housing Label",
        "Connector Knob",
        "Connector Housing Frame",
    ],
    "Repair": [
        "Lens",
        "Lens Gap",
        "Cap",
        "Array",
        "Shaft Housing Halves Splits",
        "Housing Strain Relief",
        "Cable Jacket",
        "Connector Strain Relief",
        "Leak",
        "3D/4D",
        "Electrical",
    ],
    "Cosmetic": [
        "Shaft Housing",
        "Housing Strain Relief",
        "Connector Strain Relief",
        "Connector Housing",
        "Cable",
    ],
}

# "Other" has no descriptions of its own. It only ever comes from the custom
# repair entry, but it still shows up in the dropdown and in the repair list.
other_category = "Other"

repair_categories = tuple(descriptions_by_category) + (other_category,)

# The two forms the user can work with.
form_evaluation = "Evaluation"
form_final = "Final"

# The Yes/No answers read back by the logic further down this file.
answer_yes = "yes"
answer_no = "no"

# The three ways Process can save the job.
output_option_folder_and_pdf = "Folder and PDF"
output_option_folders_only = "Folders Only"
output_option_pdf_only = "PDF Only"

output_options = (output_option_folder_and_pdf, output_option_folders_only, output_option_pdf_only)


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Fillable PDF Forms")
        self.geometry("1280x650")
        self.minsize(1050, 600)

        try:
            self.iconbitmap(utils.resource_path("processing.ico"))
        except Exception as error:
            print(f"Could not load icon: {error}")

        self.image_paths = []
        self.temporary_image_paths = set()
        self.selected_repairs = []
        self.extracted_notes_text = ""
        self.info_text = ""
        self.repairs_text = ""
        self.notes_text = ""

        # The search box needs one flat list of (category, description) pairs,
        # so walk the descriptions_by_category table above and add one pair for
        # every description.
        self.repair_options = []

        for category in descriptions_by_category:
            for description in descriptions_by_category[category]:
                self.repair_options.append((category, description))

        # (OCR field name, output label), in the same order the fields appear on
        # the evaluation form. The form name is matched against the OCR text,
        # the shorter label is used for the output.
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

        # Longest-first matching prevents "Connector" from stealing
        # "Connector Strain Relief". Precompiled and pre-sorted once.
        self.comment_field_patterns = [
            re.compile(rf"^{re.escape(field)}(?:\s|$)", flags=re.IGNORECASE)
            for field, _label in sorted(self.comment_fields, key=lambda entry: len(entry[0]), reverse=True)
        ]

        self.build_window()
        self.default_background = self.output_textbox.cget("background")
        self.refresh_repair_matches()
        self.update_form_state()

        # Ctrl+V pastes a screenshot when focus is not inside a text-entry control.
        self.bind_all("<Control-v>", self.handle_control_v, add="+")
        self.protocol("WM_DELETE_WINDOW", self.close_app)

    # ================================================================
    # Window layout
    # ================================================================

    def build_window(self):
        outer = ttk.Frame(self)
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)

        self.main_frame = ttk.Frame(canvas, padding=10)

        self.main_frame.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas_window = canvas.create_window((0, 0), window=self.main_frame, anchor="nw")

        def resize_inner_frame(event):
            canvas.itemconfigure(canvas_window, width=event.width)

        canvas.bind("<Configure>", resize_inner_frame)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.main_frame.columnconfigure(0, weight=1)

        self.build_form_section()
        self.build_workflow_row()
        self.build_repairs_section()
        self.build_bottom_section()

    def add_button(self, parent, text, command, width, pady):
        """Create a ttk button packed with fill="x" and the given padding."""
        button = ttk.Button(parent, text=text, command=command, width=width)
        button.pack(fill="x", pady=pady)
        return button

    def add_radio_buttons(self, parent, variable, choices, command=None, start_column=0, padx=8):
        """
        Create one radio button per choice, side by side, and return them in
        the same order. The shared variable holds the value of the picked one.
        """
        buttons = []

        for offset, choice in enumerate(choices):
            button = ttk.Radiobutton(parent, text=choice, value=choice, variable=variable, command=command)
            button.grid(row=0, column=start_column + offset, sticky="w", padx=padx)
            buttons.append(button)

        return buttons

    # ================================================================
    # Form section
    # ================================================================

    def build_form_section(self):
        frame = ttk.LabelFrame(self.main_frame, text="Form", padding=10)
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(frame, text="Which form would you like to work with?", font=("Arial", 11)).grid(
            row=0, column=0, sticky="w"
        )

        self.form_var = tk.StringVar(value=form_evaluation)

        self.add_radio_buttons(
            frame, self.form_var, (form_evaluation, form_final), self.update_form_state, start_column=1
        )

    # ================================================================
    # One-row workflow:
    # Helpdesk | Images | Extracted Output
    # ================================================================

    def build_workflow_row(self):
        row = ttk.Frame(self.main_frame)
        row.grid(row=1, column=0, sticky="nsew", pady=(0, 8))

        # The 5 / 3 / 5 split gives Helpdesk and output more width
        # than the image list.
        row.columnconfigure(0, weight=5, uniform="workflow")
        row.columnconfigure(1, weight=3, uniform="workflow")
        row.columnconfigure(2, weight=5, uniform="workflow")

        self.build_helpdesk_panel(row)
        self.build_image_panel(row)
        self.build_output_panel(row)

    def build_helpdesk_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Helpdesk Data", padding=10)
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="Paste your data copied from Helpdesk here:", font=("Arial", 10)).grid(
            row=0, column=0, sticky="w", pady=(0, 5)
        )

        self.input_textbox = tk.Text(frame, height=6, wrap="none")
        self.input_textbox.grid(row=1, column=0, sticky="nsew")

        # Run extraction automatically after the pasted text is inserted.
        self.input_textbox.bind("<<Paste>>", self.on_helpdesk_paste)

    def build_image_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Evaluation Images", padding=10)
        frame.grid(row=0, column=1, sticky="nsew", padx=5)
        self.image_panel = frame

        # Image list keeps most of the panel; the button column gets a firm share.
        frame.columnconfigure(0, weight=3)
        frame.columnconfigure(1, weight=2)

        ttk.Label(frame, text="Add or paste evaluation screenshots:", font=("Arial", 10)).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 5)
        )

        self.image_listbox = tk.Listbox(frame, height=5, exportselection=False)
        self.image_listbox.grid(row=1, column=0, sticky="nsew", padx=(0, 8))

        buttons = ttk.Frame(frame)
        buttons.grid(row=1, column=1, sticky="ns")

        self.add_images_button = self.add_button(buttons, "Upload Images...", self.add_images, 18, (0, 5))
        self.paste_image_button = self.add_button(buttons, "Paste Image", self.paste_image_from_clipboard, 18, 5)
        self.extract_evaluation_button = self.add_button(buttons, "Extract Evaluation", self.extract_evaluation, 18, 5)

        ttk.Label(frame, text="PNG, JPG, JPEG, BMP, PDF").grid(row=2, column=0, sticky="w", pady=(8, 0))

    def build_output_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Extracted Output", padding=10)
        frame.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
        self.output_panel = frame
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="Evaluation notes appear here. You can edit them before processing.").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 5)
        )

        self.output_textbox = tk.Text(frame, height=6, wrap="word")
        self.output_textbox.grid(row=1, column=0, sticky="nsew")

    # ================================================================
    # Repairs
    # ================================================================

    def build_repairs_section(self):
        # Side padding is 0 so the three sub-panels start and end on the same
        # x as the workflow row above; vertical padding matches the Form section.
        frame = ttk.LabelFrame(self.main_frame, text="Repairs", padding="0 10")
        frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self.repairs_panel = frame

        # Same 5 / 3 / 5 split as the workflow row above, so the three
        # panel dividers line up: Find Repairs | Custom | Selected Repairs.
        frame.columnconfigure(0, weight=5, uniform="repair")
        frame.columnconfigure(1, weight=3, uniform="repair")
        frame.columnconfigure(2, weight=5, uniform="repair")

        question = ttk.Frame(frame)
        question.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        ttk.Label(question, text="Do you need to fill in the repair part?").grid(row=0, column=0, sticky="w")

        self.rep_var = tk.StringVar(value=answer_no)

        self.repair_answer_buttons = self.add_radio_buttons(
            question, self.rep_var, (answer_yes, answer_no), self.update_repair_state, start_column=1
        )

        self.build_find_repairs_panel(frame)
        self.build_custom_repair_panel(frame)
        self.build_selected_repairs_panel(frame)

    def build_find_repairs_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Find Repairs", padding=8)
        frame.grid(row=1, column=0, sticky="nsew", padx=(0, 5))
        frame.columnconfigure(0, weight=1)

        self.repair_search_var = tk.StringVar()
        self.repair_search_var.trace_add("write", self.on_repair_search_changed)

        # Shown only while the repair part is enabled.
        self.repair_search_hint = ttk.Label(frame, text="Search repairs below", foreground="#555555")
        self.repair_search_hint.grid(row=0, column=0, sticky="w", pady=(0, 3))
        self.repair_search_hint.grid_remove()

        # The clear X sits inside the right edge of the search box.
        search_row = ttk.Frame(frame)
        search_row.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        search_row.columnconfigure(0, weight=1)

        # A soft border around the search control that lights up when enabled.
        self.repair_search_well = tk.Frame(search_row, bd=0, highlightthickness=2, highlightbackground="#bdbdbd")
        self.repair_search_well.grid(row=0, column=0, sticky="ew")
        self.repair_search_well.columnconfigure(0, weight=1)

        self.repair_search_entry = ttk.Entry(self.repair_search_well, textvariable=self.repair_search_var)
        self.repair_search_entry.grid(row=0, column=0, sticky="ew", padx=2, pady=2)

        self.clear_search_button = ttk.Button(search_row, text="X", width=2, command=self.clear_repair_search)
        self.clear_search_button.place(in_=self.repair_search_entry, relx=1.0, rely=0.5, anchor="e", x=-4)

        # Scrollable list of multiple-selectable repair results,
        # hidden until the user searches.
        self.repair_results_container = ttk.Frame(frame)
        self.repair_results_container.grid(row=2, column=0, sticky="nsew")
        self.repair_results_container.columnconfigure(0, weight=1)
        self.repair_results_container.rowconfigure(0, weight=1)

        self.repair_results_canvas = tk.Canvas(self.repair_results_container, height=120, highlightthickness=0)
        self.repair_results_scrollbar = ttk.Scrollbar(
            self.repair_results_container, orient="vertical", command=self.repair_results_canvas.yview
        )

        self.repair_results_frame = ttk.Frame(self.repair_results_canvas)

        self.repair_results_frame.bind(
            "<Configure>",
            lambda event: self.repair_results_canvas.configure(scrollregion=self.repair_results_canvas.bbox("all")),
        )

        self.repair_results_window = self.repair_results_canvas.create_window(
            (0, 0), window=self.repair_results_frame, anchor="nw"
        )

        def resize_results_inner(event):
            self.repair_results_canvas.itemconfigure(self.repair_results_window, width=event.width)

        self.repair_results_canvas.bind("<Configure>", resize_results_inner)
        self.repair_results_canvas.configure(yscrollcommand=self.repair_results_scrollbar.set)

        for scroll_target in (self.repair_results_canvas, self.repair_results_frame, self.repair_results_container):
            scroll_target.bind("<MouseWheel>", self.on_results_mousewheel)

        self.repair_results_canvas.grid(row=0, column=0, sticky="nsew")
        self.repair_results_scrollbar.grid(row=0, column=1, sticky="ns")

        self.repair_check_vars = {}
        self.repair_checkbuttons = {}

        # Shown when a search has no matches.
        self.repair_no_match_label = ttk.Label(frame, text="No matching repairs")
        self.repair_no_match_label.grid(row=2, column=0, sticky="w")
        self.repair_no_match_label.grid_remove()

        # Start with only the title and search bar visible.
        self.repair_results_container.grid_remove()

    def build_custom_repair_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Custom Repair", padding=8)
        frame.grid(row=1, column=1, sticky="nsew", padx=5)
        frame.columnconfigure(0, weight=1)

        # Collapsed by default so the column stays compact until requested.
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
        self.custom_fields.columnconfigure(0, weight=1)

        ttk.Label(self.custom_fields, text="Category").grid(row=0, column=0, sticky="w", pady=(6, 2))

        self.custom_category_var = tk.StringVar(value=repair_categories[0])

        self.custom_category_combo = ttk.Combobox(
            self.custom_fields,
            textvariable=self.custom_category_var,
            values=list(repair_categories),
            state="readonly",
        )
        self.custom_category_combo.grid(row=1, column=0, sticky="ew", pady=(2, 6))

        ttk.Label(self.custom_fields, text="Description").grid(row=2, column=0, sticky="w")

        self.custom_description_var = tk.StringVar()

        self.custom_description_entry = ttk.Entry(self.custom_fields, textvariable=self.custom_description_var)
        self.custom_description_entry.grid(row=3, column=0, sticky="ew", pady=(2, 6))
        self.custom_description_entry.bind("<Return>", lambda event: self.add_custom_repair())

        self.add_custom_button = ttk.Button(
            self.custom_fields, text="Add Custom Repair", command=self.add_custom_repair
        )
        self.add_custom_button.grid(row=4, column=0, sticky="w")

        # Start collapsed.
        self.custom_fields.grid_remove()

    def build_selected_repairs_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Selected Repairs", padding=8)
        frame.grid(row=1, column=2, sticky="nsew", padx=(5, 0))
        frame.columnconfigure(0, weight=1)

        self.selected_repairs_listbox = tk.Listbox(frame, height=5, exportselection=False)
        self.selected_repairs_listbox.grid(row=1, column=0, sticky="nsew", padx=(0, 10))

        buttons = ttk.Frame(frame)
        buttons.grid(row=1, column=1, sticky="ns")

        self.remove_repair_button = self.add_button(buttons, "Remove", self.remove_selected_repair, 14, 6)

        self.listbox_repair_by_index = {}

    # ================================================================
    # Bottom controls
    # ================================================================

    def build_bottom_section(self):
        frame = ttk.Frame(self.main_frame)
        frame.grid(row=3, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)

        options = ttk.LabelFrame(frame, text="Output Options", padding=9)
        options.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self.var_option = tk.StringVar(value=output_option_folder_and_pdf)

        self.output_option_buttons = self.add_radio_buttons(
            options, self.var_option, output_options, self.update_print_option_state, padx=(0, 24)
        )

        ttk.Separator(options, orient="vertical").grid(row=0, column=3, sticky="ns", padx=(0, 30))
        ttk.Label(options, text="Print File:").grid(row=0, column=4, sticky="w", padx=(0, 8))

        self.print_var = tk.StringVar(value=answer_no)

        self.print_buttons = self.add_radio_buttons(
            options, self.print_var, (answer_yes, answer_no), start_column=5
        )

        actions = ttk.Frame(frame)
        actions.grid(row=0, column=1, sticky="e")

        self.clear_all_button = ttk.Button(actions, text="Clear All", command=self.clear_all, width=24)
        self.clear_all_button.pack(fill="x", pady=(0, 5))
        self.process_button = ttk.Button(actions, text="Process", command=self.process_data, width=24)
        self.process_button.pack(fill="x", ipady=8)

        self.status = tk.StringVar(value="Ready")
        ttk.Label(self.main_frame, textvariable=self.status, relief="sunken", anchor="w").grid(
            row=4, column=0, sticky="ew", pady=(8, 0)
        )

        self.update_print_option_state()

    def set_widgets_enabled(self, widgets, enabled):
        """Enable or disable a group of buttons and checkbuttons at once."""
        state = "!disabled" if enabled else "disabled"

        for widget in widgets:
            widget.state([state])

    def set_textbox_enabled(self, widget, enabled):
        if enabled:
            widget.configure(state="normal", background=self.default_background)
        else:
            widget.configure(state="disabled", background="#f0f0f0")

    def update_print_option_state(self):
        """
        Printing only applies when a PDF is being generated.
        For Folders Only, force Print File to No and disable both choices.
        """
        folders_only = self.var_option.get() == output_option_folders_only

        if folders_only:
            self.print_var.set(answer_no)

        self.set_widgets_enabled(self.print_buttons, not folders_only)

    def update_form_state(self):
        # Only the Evaluation form has images, notes and repairs.
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
        """Strip Helpdesk formatting: markdown links, bold markers, line breaks."""
        value = value.strip()

        link_match = re.fullmatch(r"\[(.*?)\]\((.*?)\)", value)

        if link_match:
            value = link_match.group(1)

        value = value.replace("**", "")
        value = re.sub(r"<br\s*/?>", "", value, flags=re.IGNORECASE)

        return value.strip()

    def split_helpdesk_row(self, columns):
        """
        Turn one Helpdesk row into (Job, Customer, Model, Serial).

        Returns None when the column count is not a shape we understand.
        """
        if len(columns) == 9:
            return [columns[0], columns[4], columns[6], columns[8]]

        if len(columns) == 4:
            return columns

        if len(columns) == 3:
            # A 3-column row is missing either the Job or the Serial.
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

            # Skip the "|---|---|" separator row of a markdown table.
            if stripped_line.startswith("|") and re.fullmatch(r"[\s|:\-]+", stripped_line):
                continue

            row_number += 1

            if "\t" in line:
                columns = [self.clean_helpdesk_cell(value) for value in line.split("\t")]

            elif stripped_line.startswith("|") and stripped_line.endswith("|"):
                columns = [self.clean_helpdesk_cell(value) for value in stripped_line.strip("|").split("|")]

            else:
                errors.append(f"Row {row_number} could not be recognized.")
                continue

            row = self.split_helpdesk_row(columns)

            if row is None:
                errors.append(f"Row {row_number} has the wrong number of columns.")
                continue

            row = (row + [""] * 4)[:4]
            extracted_rows.append(row)

            for _, field_name in self.find_missing_fields([row]):
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
        # Let Tkinter finish inserting the pasted text first,
        # then run extraction on the idle queue.
        self.after_idle(self.auto_extract_helpdesk)

    def auto_extract_helpdesk(self):
        """
        Convert the pasted Helpdesk rows to:
        Job, Customer, Model, Serial.

        On success the Helpdesk box is replaced with the clean
        4-column data. The Extracted Output box is never touched.
        On failure the pasted text is left unchanged.
        """
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
        field_names = ["Job", "Customer", "Model", "Serial"]
        missing_fields = []

        for index, row in enumerate(rows, start=1):
            for field_index, field_name in enumerate(field_names):
                if field_index >= len(row) or not row[field_index].strip():
                    missing_fields.append((index, field_name))

        return missing_fields

    # ================================================================
    # Clipboard image paste
    # ================================================================

    def handle_control_v(self, event=None):
        """
        Normal Ctrl+V remains available inside text-entry controls.
        Everywhere else, Ctrl+V tries to paste an image.
        """
        focused_widget = self.focus_get()

        if focused_widget is None:
            self.paste_image_from_clipboard()
            return "break"

        widget_class = focused_widget.winfo_class()

        text_classes = {
            "Text",
            "Entry",
            "TEntry",
            "TCombobox",
            "Spinbox",
            "TSpinbox",
        }

        if widget_class in text_classes:
            # Let Tkinter do its normal text paste.
            return None

        self.paste_image_from_clipboard()
        return "break"

    def paste_image_from_clipboard(self):
        try:
            from PIL import ImageGrab
        except ImportError:
            messagebox.showerror(
                "Missing Pillow",
                "Pillow is required to paste screenshots.\n\nRun:\npython -m pip install Pillow",
            )
            return

        clipboard_content = ImageGrab.grabclipboard()

        # Windows can sometimes return a list of copied file paths.
        if isinstance(clipboard_content, list):
            image_files = [path for path in clipboard_content if self.is_supported_image_file(path)]

            if not image_files:
                messagebox.showwarning("No Image", "The clipboard does not contain a supported image.")
                return

            for path in image_files:
                self.add_image_path(path)

            self.status.set(f"Added {len(image_files)} image(s) from clipboard.")
            return

        if clipboard_content is None or not hasattr(clipboard_content, "save"):
            messagebox.showwarning("No Image", "The clipboard does not contain an image.")
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
        return os.path.splitext(path)[1].lower() in {".png", ".jpg", ".jpeg", ".bmp", ".pdf"}

    def add_image_path(self, path):
        if path in self.image_paths:
            return

        self.image_paths.append(path)
        self.image_listbox.insert("end", os.path.basename(path))

    def add_images(self):
        paths = filedialog.askopenfilenames(
            title="Select Evaluation Images",
            filetypes=[
                ("Evaluation files", "*.png *.jpg *.jpeg *.bmp *.pdf"),
                ("Image files", "*.png *.jpg *.jpeg *.bmp"),
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
            messagebox.showwarning("No Images", "Add or paste at least one evaluation image first.")
            return

        try:
            combined_text = "\n".join(self.read_evaluation_file(path) for path in self.image_paths)
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
        # The Tesseract copy bundled with the app is used first, so OCR also
        # works on computers where Tesseract is not installed system-wide.
        bundled_path = utils.resource_path(r"Tesseract-OCR\tesseract.exe")
        common_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

        if os.path.exists(bundled_path):
            pytesseract.pytesseract.tesseract_cmd = bundled_path

        elif os.path.exists(common_path):
            pytesseract.pytesseract.tesseract_cmd = common_path

    def load_ocr_libraries(self, need_pdf=False):
        """
        Import the OCR libraries and point pytesseract at a Tesseract copy.

        Returns (pytesseract, Image, ImageOps, fitz). fitz is PyMuPDF and is
        only imported when need_pdf is True, so image OCR keeps working
        without it.
        """
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

            raise RuntimeError(f"{title}\n\nRun:\npython -m pip install {packages}") from error

        self.set_tesseract_path(pytesseract)
        return pytesseract, Image, ImageOps, fitz

    def ocr_text_from_image(self, image, pytesseract, imageops):
        """Shared grayscale -> autocontrast -> OCR preprocessing."""
        gray = imageops.autocontrast(imageops.grayscale(image))
        return pytesseract.image_to_string(gray, config="--psm 6")

    def read_image_with_ocr(self, path):
        pytesseract, image_module, image_ops, _ = self.load_ocr_libraries()
        return self.ocr_text_from_image(image_module.open(path), pytesseract, image_ops)

    def read_pdf_with_ocr(self, path):
        pytesseract, image_module, image_ops, fitz = self.load_ocr_libraries(need_pdf=True)

        document = fitz.open(path)
        text_parts = []

        for page in document:
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = image_module.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
            text_parts.append(self.ocr_text_from_image(image, pytesseract, image_ops))

        document.close()

        return "\n".join(text_parts)

    # ================================================================
    # Comment extraction
    # ================================================================

    def parse_comment_fields(self, text):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        results = []

        # Use form order so the output matches the form.
        for field, label in self.comment_fields:
            comment_lines = self.find_comment_value(field, lines)

            if not comment_lines:
                continue

            # Multiple lines inside one comment box are joined with a comma.
            results.append(f"{label}: {', '.join(comment_lines)}")

        return "\n".join(results)

    def find_comment_value(self, field, lines):
        """
        Find the exact Comment(s) row and collect text that belongs
        to that comment box until another known form field starts.
        """
        comment_pattern = re.compile(rf"^{re.escape(field)}\s+comment(?:\(s\))?\s*:?\s*(.*)$", flags=re.IGNORECASE)

        for index, line in enumerate(lines):
            match = comment_pattern.match(line)

            if not match:
                continue

            comment_lines = []
            same_line_value = match.group(1).strip()

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
        if not value:
            return False

        ignored_values = {"(s)","s",":","n/a","pass","fail",
        }

        if value.lower() in ignored_values:
            return False

        # Ignore isolated OCR number artifacts such as "4".
        if re.fullmatch(r"\d+", value):
            return False

        return True

    def is_form_field_line(self, line):
        return any(pattern.match(line.strip()) for pattern in self.comment_field_patterns)

    # ================================================================
    # Extracted output
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

    def on_repair_search_changed(self, *args):
        self.refresh_repair_matches()

    def find_matching_repairs(self, query):
        """Return repairs like "Replacement: Lens" that contain every search word."""
        words = query.split()
        matches = []

        for category, description in self.repair_options:
            searchable_text = f"{category} {description}".lower()

            if all(word in searchable_text for word in words):
                matches.append(f"{category}: {description}")

        return matches

    def clear_repair_checkboxes(self):
        """Remove the checkboxes currently shown in the results list."""
        for child in self.repair_results_frame.winfo_children():
            child.destroy()

        self.repair_check_vars = {}
        self.repair_checkbuttons = {}

    def refresh_repair_matches(self):
        if not hasattr(self, "repair_results_frame"):
            return

        query = self.repair_search_var.get().strip().lower()
        self.clear_repair_checkboxes()

        # No search yet: hide the result area so the column stays compact.
        if not query:
            self.repair_results_container.grid_remove()
            self.repair_no_match_label.grid_remove()
            return

        matches = self.find_matching_repairs(query)
        enabled = self.form_var.get() == form_evaluation and self.rep_var.get() == answer_yes

        for repair_text in matches:
            check_variable = tk.BooleanVar()

            # A visible checkbox that is already selected stays checked.
            check_variable.set(repair_text in self.selected_repairs)

            checkbutton = ttk.Checkbutton(
                self.repair_results_frame,
                text=repair_text,
                variable=check_variable,
                command=lambda current=repair_text: self.on_repair_check_toggled(current),
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
        # Checked = add to Selected Repairs, unchecked = remove from it.
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
            messagebox.showwarning("Missing Description", "Enter a custom repair description.")
            return

        category = self.custom_category_var.get().strip() or other_category

        self.add_repair(category, description)
        self.custom_description_var.set("")
        self.custom_description_entry.focus_set()

    def remove_selected_repair(self):
        selected = self.selected_repairs_listbox.curselection()

        if not selected:
            return

        # The listbox shows one numbered line per repair, so map the
        # selected row back to the repair text it displays.
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

        lines = []
        self.listbox_repair_by_index = {}

        # One compact numbered line per repair, grouped by priority:
        # Replacement, Repair, Cosmetic, Other. Within each category
        # the original selection order is kept.
        for category in repair_categories:
            for repair_text in self.selected_repairs:
                if not repair_text.startswith(f"{category}: "):
                    continue

                self.listbox_repair_by_index[len(lines)] = repair_text
                lines.append(f"{len(lines) + 1}. {repair_text}")

        for line in lines:
            self.selected_repairs_listbox.insert("end", line)

        self.repairs_text = "\n".join(lines)

        # Keep the visible search checkboxes in sync with Selected Repairs.
        for repair_text, check_variable in self.repair_check_vars.items():
            check_variable.set(repair_text in self.selected_repairs)

    def update_repair_state(self):
        if not hasattr(self, "repair_search_entry"):
            return

        enabled = self.form_var.get() == form_evaluation and self.rep_var.get() == answer_yes

        entry_state = "normal" if enabled else "disabled"

        for widget in (self.repair_search_entry, self.custom_description_entry):
            widget.configure(state=entry_state)

        self.custom_category_combo.configure(state="readonly" if enabled else "disabled")
        self.set_textbox_enabled(self.selected_repairs_listbox, enabled)

        # Make the repair search stand out when the repair part is enabled.
        if enabled:
            self.repair_search_well.configure(highlightbackground="#4a90d9")
            self.repair_search_hint.grid()
        else:
            self.repair_search_well.configure(highlightbackground="#bdbdbd")
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
        """Return the chosen destination folder and the Helpdesk rows, or (None, []) to stop."""
        rows = self.extract_data()

        if not rows:
            return None, []

        output_path = filedialog.askdirectory(title=title)

        if not output_path:
            return None, []

        return output_path, rows

    def create_folders_for_all_rows(self):
        """
        Folders Only mode:
        if the Helpdesk box contains valid rows,
        create one folder per row under one selected destination.
        """
        output_path, rows = self.choose_output_folder("Select Folder to Save New Folders")

        if not output_path:
            return []

        created_folders = []

        try:
            for row in rows:
                full_path = os.path.join(output_path, self.make_folder_name(row))
                os.makedirs(full_path, exist_ok=True)
                created_folders.append(full_path)

            self.status.set(f"Created {len(created_folders)} folder(s).")
            messagebox.showinfo("Folders Created", f"Created {len(created_folders)} folder(s) successfully.")

            return created_folders

        except Exception as error:
            messagebox.showerror("Folder Error", f"Could not create the folders.\n\n{error}")
            return []

    def create_first_folder(self):
        """
        Folder and PDF mode keeps the old behavior:
        create the folder for the first Helpdesk row.
        """
        output_path, rows = self.choose_output_folder("Select Folder to Save New Folder")

        if not output_path:
            return ""

        folder_name = self.make_folder_name(rows[0])
        full_path = os.path.join(output_path, folder_name)

        try:
            os.makedirs(full_path, exist_ok=True)

            self.status.set(f"Folder created: {full_path}")
            messagebox.showinfo("Folder Created", f"Folder created successfully:\n{folder_name}")

            return full_path

        except Exception as error:
            messagebox.showerror("Folder Error", f"Could not create the folder.\n\n{error}")
            return ""

    # ================================================================
    # PDF creation
    # ================================================================

    def confirm_empty_repairs(self, is_final):
        """Ask before writing a blank Required Repairs field."""
        if is_final or self.rep_var.get() != answer_yes or self.repairs_text.strip():
            return True

        return messagebox.askyesno(
            "No Repairs Selected",
            "You chose Yes for repairs, but no repairs are selected.\n\n"
            "Continue with an empty Required Repairs field?",
        )

    def build_pdf_field_values(self, row, is_final):
        """Collect the info, repair and notes text that goes into the PDF."""
        # PDF keeps the original behavior:
        # use the first Helpdesk row for the PDF top information box.
        self.info_text = self.format_pdf_info(row)

        # Final processing ignores evaluation notes and repairs,
        # even when those panels still hold data from Evaluation mode.
        if is_final:
            self.notes_text = ""
        else:
            self.notes_text = self.get_notes_from_output()

        # Repairs are only written when the user asked for the repair part.
        repairs_text = self.repairs_text if self.rep_var.get() == answer_yes else ""

        return {
            utils.pdf_info_field: self.info_text,
            utils.pdf_repairs_field: "" if is_final else repairs_text,
            utils.pdf_notes_field: self.notes_text,
        }

    def prepare_pdf(self):
        is_final = self.form_var.get() == form_final
        original_file = "preship5.pdf" if is_final else "ev7.pdf"
        source_pdf = utils.resource_path(original_file)

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
            writer = utils.fill_pdf_fields(source_pdf, data)

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
        """Reset the current job only. Saved folders and PDFs are never touched."""
        # A disabled Text/Listbox silently ignores delete, so bring the
        # panels back to Evaluation first and reset the choices afterwards.
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
        """
        Send the generated PDF to the Windows default PDF print action.
        """
        if not pdf_path or not os.path.exists(pdf_path):
            messagebox.showwarning("No PDF", "The generated PDF could not be found.")
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