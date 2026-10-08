"""PDF-to-image conversion logic and reusable Tkinter tab."""

import os
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pymupdf


def find_pdf_files(directory):
    """Return PDF files directly inside *directory*, sorted by name."""
    folder = Path(directory)
    return sorted(
        (
            path
            for path in folder.iterdir()
            if path.is_file() and path.suffix.lower() == ".pdf"
        ),
        key=lambda path: path.name.lower(),
    )


def n_files(directory):
    """Backward-compatible helper that returns the number of PDFs in a folder."""
    return len(find_pdf_files(directory))


def build_output_name(pdf_path):
    """Keep the original naming rule: first four filename characters + FirstCall.png."""
    return f"{pdf_path.stem[:4]}FirstCall.png"


def convert_pdf_to_image(pdf_path, output_folder):
    """Convert the first page of one PDF to PNG and return the output path."""
    pdf_path = Path(pdf_path)
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    output_path = output_folder / build_output_name(pdf_path)

    document = pymupdf.open(pdf_path)
    try:
        if document.page_count == 0:
            raise ValueError(f"PDF has no pages: {pdf_path.name}")

        pixmap = document[0].get_pixmap()
        pixmap.save(output_path)
    finally:
        document.close()

    return output_path


def convert_pdfs(source_folder, output_folder=None, progress_callback=None):
    """Convert the first page of every PDF in *source_folder* to PNG."""
    source_folder = Path(source_folder)
    output_folder = Path(output_folder) if output_folder else source_folder

    pdf_files = find_pdf_files(source_folder)
    converted = []

    for index, pdf_file in enumerate(pdf_files, start=1):
        output_path = convert_pdf_to_image(pdf_file, output_folder)
        converted.append((pdf_file, output_path))

        if progress_callback:
            progress_callback(index, len(pdf_files), pdf_file, output_path)

    return converted


class PDFToImageFrame(ttk.Frame):
    """Reusable PDF conversion interface for a ttk.Notebook tab."""

    def __init__(self, parent):
        super().__init__(parent, padding=16)

        self.source_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.source_files = []
        self.status_var = tk.StringVar(value="Ready")
        self.count_var = tk.StringVar(value="PDF files found: 0")

        self.build_ui()

    def build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        heading = ttk.Frame(self)
        heading.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        heading.columnconfigure(0, weight=1)

        ttk.Label(
            heading,
            text="Convert PDF to Images",
            font=("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(
            heading,
            text="Convert the first page of each PDF into a PNG image.",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

        folders = ttk.LabelFrame(self, text="Folders", padding=12)
        folders.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        folders.columnconfigure(1, weight=1)

        ttk.Label(folders, text="Source Folder:").grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 10),
            pady=(0, 8),
        )
        ttk.Entry(folders, textvariable=self.source_var).grid(
            row=0,
            column=1,
            sticky="ew",
            pady=(0, 8),
        )
        ttk.Button(
            folders,
            text="Browse...",
            command=self.pick_source_folder,
        ).grid(row=0, column=2, padx=(8, 0), pady=(0, 8))

        ttk.Label(folders, text="Output Folder:").grid(
            row=1,
            column=0,
            sticky="w",
            padx=(0, 10),
        )
        ttk.Entry(folders, textvariable=self.output_var).grid(
            row=1,
            column=1,
            sticky="ew",
        )
        ttk.Button(
            folders,
            text="Browse...",
            command=self.pick_output_folder,
        ).grid(row=1, column=2, padx=(8, 0))

        details = ttk.Frame(self)
        details.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        details.columnconfigure(0, weight=1)

        ttk.Label(details, textvariable=self.count_var).grid(
            row=0,
            column=0,
            sticky="w",
        )
        ttk.Label(
            details,
            text="Output naming keeps the existing rule: first 4 characters + FirstCall.png",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

        log_frame = ttk.LabelFrame(self, text="Conversion Log", padding=10)
        log_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_box = tk.Text(
            log_frame,
            height=12,
            wrap="word",
            state="disabled",
        )
        self.log_box.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(
            log_frame,
            orient="vertical",
            command=self.log_box.yview,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_box.configure(yscrollcommand=scrollbar.set)

        bottom = ttk.Frame(self)
        bottom.grid(row=4, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)

        ttk.Label(bottom, textvariable=self.status_var).grid(
            row=0,
            column=0,
            sticky="w",
        )

        self.clear_button = ttk.Button(
            bottom,
            text="Clear Log",
            command=self.clear_log,
        )
        self.clear_button.grid(row=0, column=1, padx=(8, 8))

        self.convert_button = ttk.Button(
            bottom,
            text="Convert PDFs",
            command=self.start_conversion,
            width=18,
        )
        self.convert_button.grid(row=0, column=2)

    def pick_source_folder(self):
        try:
            paths = filedialog.askopenfilenames(
                title="Select PDF Files",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            )
        except KeyboardInterrupt:
            return

        if not paths:
            return

        self.source_files = [Path(path) for path in paths]

        # The entry shows the files' common folder; the actual file list is
        # kept separately so the conversion uses exactly what was selected.
        self.source_var.set(
            str(Path(os.path.commonpath([str(p) for p in self.source_files])))
        )

        if not self.output_var.get().strip():
            self.output_var.set(self.source_var.get())

        self.refresh_pdf_count()

    def selected_pdf_files(self):
        if self.source_files:
            return [path for path in self.source_files if path.is_file()]

        source = Path(self.source_var.get().strip())

        if source.is_dir():
            return find_pdf_files(source)

        return []

    def pick_output_folder(self):
        try:
            folder = filedialog.askdirectory(title="Select Folder for Converted Images")
        except KeyboardInterrupt:
            return

        if folder:
            self.output_var.set(folder)

    def refresh_pdf_count(self):
        pdf_files = self.selected_pdf_files()

        if pdf_files:
            self.count_var.set(f"PDF files selected: {len(pdf_files)}")
        else:
            self.count_var.set("No PDF files selected")

    def clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", tk.END)
        self.log_box.configure(state="disabled")

    def write_log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert(tk.END, text + "\n")
        self.log_box.see(tk.END)
        self.log_box.configure(state="disabled")

    def start_conversion(self):
        output_text = self.output_var.get().strip()
        output = Path(output_text) if output_text else None

        if output is not None and (not output.exists() or not output.is_dir()):
            messagebox.showerror(
                "Invalid Output Folder",
                "Please select a valid output folder.",
            )
            return

        pdf_files = self.selected_pdf_files()

        if not pdf_files:
            self.refresh_pdf_count()
            messagebox.showwarning(
                "No PDFs Found",
                "There are no PDF files to convert in the selected source folder.",
            )
            return

        if output is None:
            output = pdf_files[0].parent

        self.convert_button.state(["disabled"])
        self.clear_log()
        self.write_log(f"Starting conversion of {len(pdf_files)} PDF file(s)...")
        self.status_var.set("Processing...")

        thread = threading.Thread(
            target=self.run_conversion_thread,
            args=(pdf_files, output),
            daemon=True,
        )
        thread.start()

    def run_conversion_thread(self, pdf_files, output):
        try:
            converted = [
                (pdf_file, convert_pdf_to_image(pdf_file, output))
                for pdf_file in pdf_files
            ]
            error = None
        except Exception as exc:
            converted = []
            error = exc

        self.after(0, self.finish_conversion, converted, error)

    def finish_conversion(self, converted, error):
        if error is not None:
            self.write_log(f"Error: {error}")
            self.status_var.set("Conversion failed.")
            self.convert_button.state(["!disabled"])
            messagebox.showerror("Conversion Error", str(error))
            return

        for source_file, output_file in converted:
            self.write_log(f"{source_file.name} -> {output_file.name}")

        self.write_log("")
        self.write_log(f"Converted {len(converted)} PDF file(s).")
        self.status_var.set(f"Converted {len(converted)} PDF file(s).")
        self.refresh_pdf_count()
        self.convert_button.state(["!disabled"])
        messagebox.showinfo("Done", "PDF conversion finished.")


def main():
    root = tk.Tk()
    root.title("Convert PDF to Images")
    root.geometry("760x520")
    root.minsize(650, 430)

    frame = PDFToImageFrame(root)
    frame.pack(fill="both", expand=True)

    root.mainloop()


if __name__ == "__main__":
    main()
