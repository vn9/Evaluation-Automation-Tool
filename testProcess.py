import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from dataclasses import dataclass
from typing import List, Dict
from datetime import datetime
from pathlib import Path
from collections import defaultdict
import os, win32api

# ---- PDF filling (pypdf) ----
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, BooleanObject, DictionaryObject

# ----------------------------- CONFIG -----------------------------

PDF_INFO_FIELD = "info"       # must match your PDF form field
PDF_REPAIRS_FIELD = "repair" # must match your PDF form field

# Get the path of the current running script
def resource_path(relative_path: str) -> str:
    """ Get the path to the resource (PDF) that is bundled with the app """
    try:
        # PyInstaller creates a temporary folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = Path(__file__).parent
    return os.path.join(base_path, relative_path)

# Fixed file behavior:
#BASE_DIR = Path(__file__).resolve().parent
# ------------------------------------------------------------------

def set_need_appearances(writer: PdfWriter) -> None:
    if "/AcroForm" in writer._root_object:
        writer._root_object["/AcroForm"].update(
            {NameObject("/NeedAppearances"): BooleanObject(True)}
        )
    else:
        writer._root_object.update({
            NameObject("/AcroForm"): DictionaryObject({
                NameObject("/NeedAppearances"): BooleanObject(True)
            })
        })

def fill_pdf_fields(src_pdf: Path, dst_pdf: Path, data: Dict[str, str]) -> None:
    reader = PdfReader(str(src_pdf))
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    if "/AcroForm" in reader.trailer["/Root"]:
        writer._root_object.update({
            NameObject("/AcroForm"): reader.trailer["/Root"]["/AcroForm"]
        })

    set_need_appearances(writer)

    for page in writer.pages:
        writer.update_page_form_field_values(page, data)

    with open(dst_pdf, "wb") as f:
        writer.write(f)

@dataclass
class Selections:
    info_text: str = ""
    repairs_text: str = ""

class RepairsPopup(tk.Toplevel):
    def __init__(self, master, on_done):
        super().__init__(master)
        self.title("Select Repairs")
        self.transient(master)
        self.grab_set()
        self.resizable(False, True)

        # --- Define categories and items ---
        self.categories = {
            "Replacement": [
                "Lens", "Cap", "Array", "Shaft Housing", "Housing Strain Relief", "Cable",
                "Connector Strain Relief", "Connector Housing", "Connector Housing Label",
                "Connector Knob", "Connector Housing Frame", "Others",
            ],
            "Repair": [
                "Lens", "Lens Gap", "Cap", "Array", "Lens Gap", "Shaft Housing Halves Splits", "Housing Strain Relief",
                "Cable Jacket", "Connector Strain Relief", "Leak", "3D/4D", "Electrical", "Others",
            ],
            "Cosmetic": [
                 "Shaft Housing", "Housing Strain Relief", "Connector Strain Relief", 
                 "Connector Housing", "Cable", "Others",
            ],
        }

        # Colors for each category
        self.colors = {
            "Replacement": "lightcoral",
            "Repair": "lightgreen",
            "Cosmetic": "yellow",
        }

        self.vars = []  # (cat, item, var)

        # --- Layout: frames side by side ---
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)

        for col, (cat, items) in enumerate(self.categories.items()):
            # Frame with background color
            frm = tk.Frame(outer, bg=self.colors[cat], bd=2, relief="groove")
            frm.grid(row=0, column=col, padx=5, sticky="n")

            # Category label
            lbl = tk.Label(frm, text=cat, font=("Segoe UI", 10, "bold"), bg=self.colors[cat])
            lbl.pack(anchor="w", padx=6, pady=(4, 6))

            # Add checkboxes
            for item in items:
                var = tk.BooleanVar(value=False)
                cb = tk.Checkbutton(frm, text=item, variable=var, bg=self.colors[cat], anchor="w")
                cb.pack(anchor="w", padx=12, pady=2)
                self.vars.append((cat, item, var))

        # Preview + buttons
        self.preview = tk.Text(self, height=5, wrap="word", state="normal")
        self.preview.pack(fill="x", padx=12, pady=(8, 0))

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=12, pady=12)
        ttk.Button(btns, text="Preview", command=self.do_preview).pack(side="left")
        ttk.Button(btns, text="OK", command=lambda: self.finish(on_done)).pack(side="left", padx=8)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right")

        self.bind("<Return>", lambda e: self.finish(on_done))
        self.bind("<Escape>", lambda e: self.destroy())

    def get_selected_text(self) -> str:
        # Priority order
        order = {"Replacement": 0, "Repair": 1, "Cosmetic": 2}
        chosen = [(cat, item) for (cat, item, v) in self.vars if v.get()]
        chosen.sort(key=lambda ci: (order.get(ci[0], 99), ci[1].lower()))
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


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Fillable PDF Forms")
        self.geometry("680x660")
        self.sel = Selections()

        # Create a frame to hold the radio_buttones
        self.outer_frame_form = tk.Frame()
        self.outer_frame_form.pack(pady=10, padx=10, fill=tk.X)

        self.inner_frame_form = tk.Frame(self.outer_frame_form)
        self.inner_frame_form.grid(row=1, column=0, padx=210)

        self.outer_frame_info = tk.Frame()
        self.outer_frame_info.pack(pady=10, padx=10, fill=tk.X)

        self.inner_frame = tk.Frame(self.outer_frame_info)
        self.inner_frame.grid(row=3, column = 0, pady=5, padx=5)

        self.repair_frame = tk.Frame()
        self.repair_frame.pack(fill=tk.X, padx=12)

        #repair_frame = ttk.Frame(self)
        #repair_frame.pack(fill="x", padx=12)
        ttk.Label(self.repair_frame, text="Do you need to fill in the repair part?", font=('Arial', 11)).pack(side="left")
        
        self.rep_var = tk.StringVar(value="no")
        ttk.Radiobutton(self.repair_frame, text="Yes", value="yes", variable=self.rep_var, command=self.on_radio).pack(side="left", padx=(12, 4))
        ttk.Radiobutton(self.repair_frame, text="No", value="no", variable=self.rep_var, command=self.on_radio).pack(side="left")

        self.whichFrom_label = tk.Label(self.outer_frame_form,text="Which form would you like to work with?",font=('Arial', 11))
        self.whichFrom_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.input_label = tk.Label(self.outer_frame_info, text="Paste your data copied from Helpdesk here:",font=('Arial', 11))
        self.input_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        
        # List of forms
        self.radio_forms = ["Evaluation", "Final"]
        self.radio_options = ["Folder and PDF", "Folders Only", "PDF Only","Extract Data Only"]

        self.form_var = tk.StringVar(value="Evaluation")

        for col, form in enumerate(self.radio_forms):
            form_radio_button = tk.Radiobutton(self.inner_frame_form, text=form, variable=self.form_var, value=form)
            form_radio_button.grid(row=0, column=col, sticky="ew", padx=20)
    
        self.input_textbox = tk.Text(self.outer_frame_info, height=5)
        self.input_textbox.grid(row=1, column=0, padx=10, pady=5)

        # List of options that you want to generate on the same row
        
        self.var_option = tk.StringVar(value="Folder and PDF")

        for col, option in enumerate(self.radio_options):
            ra_button = tk.Radiobutton(self.inner_frame, text=option, variable=self.var_option, value=option)
            ra_button.grid(row=0, column=col, padx=10, pady=10, sticky="w")
       
        rp = ttk.LabelFrame(self, text='Repairs (preview)', padding=8)
        rp.pack(fill="both", expand=False, padx=12, pady=12)
        self.repairs_preview = tk.Text(rp, height=6, wrap="word", state="disabled")
        self.repairs_preview.pack(fill="x", pady=(0, 8))
        self.choose_btn = ttk.Button(rp, text="Choose repair items…", command=self.open_repairs_popup)
        self.choose_btn.pack(anchor="w")
        self.choose_btn.state(["disabled"])
        self.copy_btn = ttk.Button(rp, text="Copy Text", command=self.copy_repairs_text)
        self.copy_btn.pack(anchor="w", pady=(5, 0))
        self.copy_btn.state(["disabled"])

        print_frame = ttk.Frame(self)
        print_frame.pack(fill="x", padx=12)
        ttk.Label(print_frame, text="Do you want to print the file?", font=('Arial', 11)).pack(side="left")
        self.print_var = tk.StringVar(value="no")
        ttk.Radiobutton(print_frame, text="Yes", value="yes", variable=self.print_var).pack(side="left", padx=(12, 4))
        ttk.Radiobutton(print_frame, text="No", value="no", variable=self.print_var).pack(side="left")

        bf = ttk.Frame(self)
        bf.pack(fill="x", padx=12, pady=(20, 12))
        ttk.Button(bf, text="Processing Data", command=self.process_pdf).pack()

        self.status = tk.StringVar(value=f"Looking for input file")
        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w").pack(fill="x")

    def copy_repairs_text(self):
        # Get the current repairs text from the preview
        repairs_text = self.repairs_preview.get("1.0", "end").strip()
        
        if repairs_text:
            # Copy the text to clipboard
            self.clipboard_clear()
            self.clipboard_append(repairs_text)
            self.update()

            # Switch radio button to "No"
            self.rep_var.set("no")

            # Disable the "Choose repair items" and "Copy Text" buttons
            self.choose_btn.state(["disabled"])
            self.copy_btn.state(["disabled"])

             # Clear repairs preview text
            self.set_repairs_text("") 

            messagebox.showinfo("Copied", "Repairs text copied to clipboard and radio set to 'No'.")
        else:
            messagebox.showwarning("No Text", "There is no text to copy.")

    def extract_data(self) -> list:
        # Retrieve the content of the text box
        text_content = self.input_textbox.get("1.0", tk.END).strip()
        if not text_content:
            messagebox.showwarning("Empty Text", "Please copy and paste data.")
            return

        # Split the text into rows (by newline character)
        #print(text_content)
        row = text_content.split("\t")
        #print(row)
        if len(row) == 9:
            return [row[0], row[4], row[6], row[-1]]
        elif len(row) == 4:
            return row
        elif len(row) == 3:
            if not row[0].isnumeric():
                row.insert(0,'')
            return row
        else:
            messagebox.showwarning("Invalid data", "Please make sure you copy all the data.")
            return
    
    def format_data(self, row) -> str:
        #print(f'Job#: {row[0]}\nModel: {row[2]}\nS/N: {row[-1]}\nCustomer: {row[1]}')
        return f'Job#: {row[0]}\nModel: {row[2]}\nS/N: {row[-1]}\nCustomer: {row[1]}'
    
    def preview_extracting(self):
        extracted_data = self.extract_data()
        preview_extracted_data = f'{extracted_data[0]}\t{extracted_data[1]}\t{extracted_data[2]}\t{extracted_data[3]}'
        self.repairs_preview.config(state="normal")
        self.repairs_preview.delete("1.0", "end")
        self.repairs_preview.insert("1.0", preview_extracted_data)
        self.repairs_preview.config(state="disabled")

    def on_radio(self):
        if self.rep_var.get() == "yes":
            self.choose_btn.state(["!disabled"])
            self.copy_btn.state(["!disabled"])
        else:
            self.choose_btn.state(["disabled"])
            self.copy_btn.state(["disabled"])
        
        # clear preview if switching to No
        self.set_repairs_text("")

    def open_repairs_popup(self):
        RepairsPopup(self, on_done=self.set_repairs_text)

    def set_repairs_text(self, text: str):
        self.sel.repairs_text = text
        self.repairs_preview.config(state="normal")
        self.repairs_preview.delete("1.0", "end")
        self.repairs_preview.insert("1.0", text)
        self.repairs_preview.config(state="disabled")

    def prepare_pdf(self):
        # Use resource_path to get the path for the bundled PDF files
        original_file = "ev6.pdf"  # Default file
        if self.form_var.get() == 'Final':
            original_file = 'preship5.pdf'

        # Use resource_path to find the PDFs in the bundled app
        SRC_PDF = resource_path(original_file)

        if not os.path.exists(SRC_PDF):
            messagebox.showerror("Missing file", f"Input PDF not found: {SRC_PDF}")
            return

        try:
            data_row = self.extract_data()
            self.sel.info_text = self.format_data(data_row)
        except Exception as e:
            messagebox.showerror("Error", f"Check your input data.\n\n{e}")
            return

        if not self.sel.info_text:
            messagebox.showwarning("Missing info", "Please paste text into the INFO box.")
            return

        if self.rep_var.get() == "yes" and not self.sel.repairs_text.strip():
            if not messagebox.askyesno("No repairs selected",
                                       "You chose 'Yes' but no repair items are selected.\nContinue with empty 'repairs'?"):
                return

        data = {
            PDF_INFO_FIELD: self.sel.info_text,
            PDF_REPAIRS_FIELD: self.sel.repairs_text if self.rep_var.get() == "yes" else ""
        }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_fileName = f"{original_file[:-5]}_filled_{timestamp}.pdf"
        output_folder = filedialog.askdirectory(title="Select Folder to Save PDFs")
        #dst_pdf = Path(output_folder).with_name(new_fileName)
        dst_pdf = output_folder + f"/{new_fileName}"
        #print(output_folder)
        #print(dst_pdf)

        try:
            fill_pdf_fields(SRC_PDF, dst_pdf, data)
            messagebox.showinfo("Done", f"New PDF saved: {dst_pdf}")
            self.status.set( f"New PDF saved at: {dst_pdf}")
            if self.print_var.get() == 'yes':
                win32api.ShellExecute(0, "print", str(dst_pdf), None, ".", 0)
                self.print_var.set("no")
                self.status.set( f"New PDF saved at: {dst_pdf} AND was printed")

        except Exception as e:
            messagebox.showerror("Error", f"Could not fill PDF.\n\n{e}")

    def create_button(self, parent, text, command, padding=(0, 0)):
        button = ttk.Button(parent, text=text, command=command)
        button.grid(padx=padding[0], pady=padding[1])

    def create_folder(self):
        option = 'E'
        if self.form_var.get() == 'Final':
            option = 'F'

        output_path = filedialog.askdirectory(title="Select Folder to Save new Folder")
        if not output_path:
            return
        try:
            data_row = self.extract_data()
            #print(data_row)
            folder_name = f"-{data_row[2]} {data_row[3]} (#{data_row[0]}{option}-{data_row[1]})"
            full_path = os.path.join(output_path, folder_name)
            os.makedirs(full_path, exist_ok=True)
            messagebox.showwarning("Success", f"Folder '{folder_name}' created successfully.")
        except Exception as e:
            self.status.set("Error while reading input values")
            messagebox.showerror("Error", f"Check your input data.\n\n{e}")

    def process_pdf(self):
        if self.var_option.get() == 'Extract Data Only':
            self.preview_extracting()
        elif self.var_option.get() == 'Folders Only':
            self.create_folder()
        elif self.var_option.get() == 'PDF Only':
            self.prepare_pdf()
        else:
            self.create_folder()
            self.prepare_pdf()    

if __name__ == "__main__":
    app = App()
    app.mainloop()
