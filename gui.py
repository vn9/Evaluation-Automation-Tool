import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import win32api
from dataclasses import dataclass
from datetime import datetime

from popups import RepairsPopup, ItemsPopup
from utils import fill_pdf_fields, add_qr_to_existing_pdf,generate_qr_image, resource_path, PDF_INFO_FIELD, PDF_REPAIRS_FIELD, PDF_ITEMS_FIELD

@dataclass
class Selections:
    info_text: str = ""
    repairs_text: str = ""
    items_text: str = ""

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Fillable PDF Forms")
        self.geometry("680x890")
        icon_path = resource_path("processing.ico")
        try:
            self.iconbitmap(icon_path)
        except Exception as e:
            print(f"Could not load icon: {e}")
        self.sel = Selections()

        # Outer frame for form selection
        self.outer_frame_form = tk.Frame(self)
        self.outer_frame_form.pack(pady=10, padx=10, fill=tk.X)

        self.whichFrom_label = tk.Label(self.outer_frame_form,
            text="Which form would you like to work with?",font=('Arial', 11))

        self.whichFrom_label.grid(row=0, column=0, sticky="w", pady=5)

        self.inner_frame_form = tk.Frame(self.outer_frame_form)
        self.inner_frame_form.grid(row=1, column=0, sticky="w", pady=5, padx=210)

        self.radio_forms = ["Evaluation", "Final"]
        self.form_var = tk.StringVar(value="Evaluation")

        for col, form in enumerate(self.radio_forms):
            form_radio_button = tk.Radiobutton(
                self.inner_frame_form, text=form, variable=self.form_var, value=form
            )
            form_radio_button.grid(row=0, column=col, sticky="w", padx=20)

        # Outer frame for general info
        self.outer_frame_info = tk.Frame(self)
        self.outer_frame_info.pack(pady=10, padx=10, fill=tk.X)

        self.input_label = tk.Label(self.outer_frame_info,
            text="Paste your data copied from Helpdesk here:",font=('Arial', 11))
        self.input_label.grid(row=0, column=0, sticky="w", pady=5)

        # Multi-line question
        self.multi_frame = tk.Frame(self.outer_frame_info)
        self.multi_frame.grid(row=1, column=0, sticky="w", pady=5)

        tk.Label(self.multi_frame,
            text="Do you want to EXTRACT multiple lines of data at once?",font=('Arial', 9),fg='blue'
            ).grid(row=0, column=0, sticky="w")

        self.multi_var = tk.StringVar(value="no")
        ttk.Radiobutton(self.multi_frame, text="Yes", value="yes", variable=self.multi_var, command=self.on_radio
        ).grid(row=0, column=1, padx=(12,4))
        ttk.Radiobutton(self.multi_frame, text="No", value="no", variable=self.multi_var, command=self.on_radio
        ).grid(row=0, column=2)

        # Textbox for user input
        self.input_textbox = tk.Text(self.outer_frame_info, height=5)
        self.input_textbox.grid(row=2, column=0, sticky="ew", pady=5)

        # Options row
        self.inner_frame = tk.Frame(self.outer_frame_info)
        self.inner_frame.grid(row=3, column=0, sticky="w", pady=5)

        self.radio_options = ["Folder and PDF", "Folders Only", "PDF Only", "Extract Data Only"]
        self.var_option = tk.StringVar(value="Folder and PDF")

        for col, option in enumerate(self.radio_options):
            ra_button = tk.Radiobutton(
                self.inner_frame, text=option, variable=self.var_option, value=option)
            ra_button.grid(row=0, column=col, padx=20, sticky="w")

        # Make columns expand evenly
        for col in range(len(self.radio_options)):
            self.inner_frame.grid_columnconfigure(col, weight=1)
        for col in range(len(self.radio_forms)):
            self.inner_frame_form.grid_columnconfigure(col, weight=1)


        # Items preview and button for ITEMS PopUp
        self.items_frame = tk.Frame()
        self.items_frame.pack(fill=tk.X, padx=12)
        ttk.Label(self.items_frame, text="Do you need to fill in the Items part?", font=('Arial', 11)).pack(side="left")
        self.items_var = tk.StringVar(value="no")
        ttk.Radiobutton(self.items_frame, text="Yes", value="yes", variable=self.items_var, command=self.on_radio).pack(side="left", padx=(12, 4))
        ttk.Radiobutton(self.items_frame, text="No", value="no", variable=self.items_var, command=self.on_radio).pack(side="left")

        ip = ttk.LabelFrame(self, text='Items (preview)', padding=8)
        ip.pack(fill="both", expand=False, padx=12, pady=12)

        self.items_preview = tk.Text(ip, height=6, wrap="word", state="disabled")
        self.items_preview.pack(fill="x", pady=(0, 8))

        self.choose_items_btn = ttk.Button(ip, text="Choose items…", command=self.open_items_popup)
        self.choose_items_btn.pack(anchor="w")
        self.choose_items_btn.state(["disabled"])

        self.copy_items_btn = ttk.Button(ip, text="Copy Text", command=self.copy_items_text)
        self.copy_items_btn.pack(anchor="w", pady=(5, 0))
        self.copy_items_btn.state(["disabled"])

        
        # Items preview and button for REQUIRE REPAIRS PopUp
        self.repair_frame = tk.Frame()
        self.repair_frame.pack(fill=tk.X, padx=12)
        ttk.Label(self.repair_frame, text="Do you need to fill in the repair part?", font=('Arial', 11)).pack(side="left")
        
        self.rep_var = tk.StringVar(value="no")
        ttk.Radiobutton(self.repair_frame, text="Yes", value="yes", variable=self.rep_var, command=self.on_radio).pack(side="left", padx=(12, 4))
        ttk.Radiobutton(self.repair_frame, text="No", value="no", variable=self.rep_var, command=self.on_radio).pack(side="left")

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


    def open_repairs_popup(self):
        RepairsPopup(self, on_done=self.set_repairs_text)

    def open_items_popup(self):
        ItemsPopup(self, on_done=self.set_items_text)

    def set_repairs_text(self, text: str):
        self.sel.repairs_text = text
        self.repairs_preview.config(state="normal")
        self.repairs_preview.delete("1.0", "end")
        self.repairs_preview.insert("1.0", text)
        self.repairs_preview.config(state="disabled")

    def set_items_text(self, text: str):
        self.sel.items_text = text
        self.items_preview.config(state="normal")
        self.items_preview.delete("1.0", "end")
        self.items_preview.insert("1.0", text)
        self.items_preview.config(state="disabled")

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

    def copy_items_text(self):
        # Get the current repairs text from the preview
        items_text = self.items_preview.get("1.0", "end").strip()
        
        if items_text:
            # Copy the text to clipboard
            self.clipboard_clear()
            self.clipboard_append(items_text)
            self.update()

            # Switch radio button to "No"
            self.items_var.set("no")

            # Disable the "Choose repair items" and "Copy Text" buttons
            self.choose_items_btn.state(["disabled"])
            self.copy_items_btn.state(["disabled"])

             # Clear repairs preview text
            self.set_items_text("") 

            messagebox.showinfo("Copied", "Items text copied to clipboard and radio set to 'No'.")
        else:
            messagebox.showwarning("No Text", "There is no text to copy.")

    def extract_data(self) -> list:
        """
        Extract multiple lines of tab-delimited text.
        Returns a list of rows.
        Each row is: [Job#, Customer, Model, Serial]
        """
        text_content = self.input_textbox.get("1.0", tk.END).strip()

        if not text_content:
            messagebox.showwarning("Empty Text", "Please copy and paste data.")
            return []

        lines = [line.strip() for line in text_content.split("\n") if line.strip()]
        extracted_rows = []

        for line in lines:
            cols = line.split("\t")

            # Standard helpdesk format
            if len(cols) == 9:
                extracted_rows.append([cols[0], cols[4], cols[6], cols[-1]])

            # Already formatted 4-column data
            elif len(cols) == 4:
                extracted_rows.append(cols)

            # 3 columns but missing job number
            elif len(cols) == 3:
                if not cols[0].isnumeric():
                    cols.insert(0, "")
                extracted_rows.append(cols)

            else:
                messagebox.showwarning("Invalid line", f"Invalid data:\n{line}")
                continue

        return extracted_rows

    def format_data(self, row) -> str:
        #print(f'Job#: {row[0]}\nModel: {row[2]}\nS/N: {row[-1]}\nCustomer: {row[1]}')
        return f'Job#: {row[0]}\nModel: {row[2]}\nS/N: {row[3]}\nCustomer: {row[1]}'
    
    def preview_extracting(self):
        rows = self.extract_data()

        preview_lines = []

        if self.multi_var.get() == 'yes':
            # Loop through all extracted rows and format each
            for row in rows:
                preview_lines.append('\t'.join(row))
        else:
            # Only show first row
            preview_lines.append('\t'.join(rows[0]))

        preview = "\n".join(preview_lines)
        self.repairs_preview.config(state="normal")
        self.repairs_preview.delete("1.0", "end")
        self.repairs_preview.insert("1.0", preview)
        self.repairs_preview.config(state="disabled")

    def on_radio(self):
        if self.rep_var.get() == "yes":
            self.choose_btn.state(["!disabled"])
            self.copy_btn.state(["!disabled"])
        else:
            self.choose_btn.state(["disabled"])
            self.copy_btn.state(["disabled"])
            self.set_repairs_text("") # clear preview if switching to No

        if self.items_var.get() == "yes":
            self.choose_items_btn.state(["!disabled"])
            self.copy_items_btn.state(["!disabled"])
        else:
            self.choose_items_btn.state(["disabled"])
            self.copy_items_btn.state(["disabled"])
            self.set_items_text("") # clear preview if switching to No
        
    def prepare_pdf(self):
        """Fill PDF fields, generate QR, overlay it safely, and save the PDF."""
        # Determine source PDF based on form selection
        original_file = "ev7.pdf"  # default
        if self.form_var.get() == "Final":
            original_file = "preship5.pdf"
        SRC_PDF = resource_path(original_file)

        if not os.path.exists(SRC_PDF):
            messagebox.showerror("Missing file", f"Input PDF not found: {SRC_PDF}")
            return

        #Extract data from input textbox
        rows = self.extract_data()
        if not rows:
            return
        first_row = rows[0]
        self.sel.info_text = self.format_data(first_row)

        # Validate repairs and items text
        if self.rep_var.get() == "yes" and not self.sel.repairs_text.strip():
            if not messagebox.askyesno("No repairs selected",
                                   "You chose 'Yes' but no repair items are selected.\nContinue with empty 'repairs'?"):
                return

        if self.items_var.get() == "yes" and not self.sel.items_text.strip():
            if not messagebox.askyesno("No items selected",
                                   "You chose 'Yes' but no items are selected.\nContinue with empty 'notes'?"):
                return

        # Prepare data dictionary
        data = {
            PDF_INFO_FIELD: self.sel.info_text,
            PDF_REPAIRS_FIELD: self.sel.repairs_text if self.rep_var.get() == "yes" else "",
            PDF_ITEMS_FIELD: self.sel.items_text if self.items_var.get() == "yes" else "",
        }

        job, customer, model, serial = rows[0]
        
        # Generate QR code in memory
        qr_data = "\t".join([job, customer, model, serial])
        qr_bytes = generate_qr_image(qr_data)

        try:
            # Fill PDF fields
            writer = fill_pdf_fields(SRC_PDF, data)
            
            #writer = add_qr_to_existing_pdf(writer, qr_bytes)

            # Choose output folder and file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_fileName = f"{original_file[:-4]}_filled_{timestamp}.pdf"
            output_folder = filedialog.askdirectory(title="Select Folder to Save PDFs")
            if not output_folder:
                return
            dst_pdf = os.path.join(output_folder, new_fileName)

            with open(dst_pdf, "wb") as f:
                writer.write(f)

            # Show success message
            messagebox.showinfo("Done", f"New PDF saved: {dst_pdf}")
            self.status.set(f"New PDF saved at: {dst_pdf}")

            # Optional printing
            if self.print_var.get() == "yes":
                win32api.ShellExecute(0, "print", str(dst_pdf), None, ".", 0)
                self.print_var.set("no")
                self.status.set(f"New PDF saved at: {dst_pdf} AND was printed")

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
            rows = self.extract_data()
            if not rows:
                return
            data_row = rows[0]
            #print(data_row)
            folder_name = f"{data_row[0]}-{data_row[2]} {data_row[3]} (#{data_row[0]}{option}-{data_row[1]})"
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
