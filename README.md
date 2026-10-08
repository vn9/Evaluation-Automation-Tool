# Evaluation Automation Tool

A Python desktop application for automating evaluation and final-form workflows, including Helpdesk data extraction, evaluation screenshot OCR, repair selection, folder creation, PDF generation, and optional printing.

This repository contains three versions of the tool:

## Versions

### `tool_v1.0`
Original version of the Evaluation Automation Tool.

This version contains the earlier workflow and UI used before the Version 2 redesign.

### `tool_v2.0`
Second version of the tool.

Version 2 adds a redesigned workflow with:

- Automatic Helpdesk data extraction after paste
- Validation for missing Job, Customer, Model, or Serial data
- Evaluation and Final modes
- Uploading evaluation screenshots
- Pasting screenshots directly from the clipboard
- OCR extraction from evaluation `Comment(s)` fields
- Editable extracted evaluation notes
- Repair search with selectable matching repairs
- Custom repair entry
- Prioritized repair ordering:
  - Replacement
  - Repair
  - Cosmetic
  - Other
- Multiple folder creation when processing multiple Helpdesk rows
- Evaluation and Final PDF generation
- Optional printing
- Global Clear All reset
- Compact redesigned GUI

### `tool_v3.0`
Current version. Implemented in [`ponytail_evaluation_tool/`](ponytail_evaluation_tool/).

Version 3 keeps the Version 2 workflow and adds two standalone tabs:

- **PDF → Images** — convert the first page of PDFs to PNG, selecting PDF
  files or a folder, with an optional output folder.
- **Organize Files** — move images, PDFs, and videos into matching destination
  subfolders by filename, including:
  - recursive source folders (multiple levels of subfolders)
  - IMS / Loaner Return / Warranty / Withdrawn category matching
  - numbered destination-folder renaming
  - duplicate-destination detection (hard stop before touching files)
  - Withdrawn-year fallback (`Withdrawn/2026`)

## Repository Structure

```text
Evaluation-Automation-Tool/
├── tool_v1.0/
│   └── Version 1 application files
│
├── tool_v2.0/
│   └── Version 2 application files
│
├── ponytail_evaluation_tool/
│   └── Version 3 application files
│       ├── main_eval_final_v3.py
│       ├── gui_v3.py
│       ├── pdf_to_img.py
│       ├── image_folder_organizer.py
│       ├── utils_v3.py
│       └── README_v3.md
│
└── README.md
```

Each version is kept in its own folder so previous workflows remain available while the current version continues to be developed.

## Run the Current Version (v3)

Open a terminal in:

```text
ponytail_evaluation_tool
```

Install the required dependencies:

```bash
pip install -r requirements.txt
pip install PyMuPDF
```

(`PyMuPDF` is used by the PDF tabs but is not yet in `requirements.txt`.)

Then start the application:

```bash
python main_eval_final_v3.py
```

## Version 3 Workflow

### Main Processing

1. Paste Helpdesk data.
2. The application automatically extracts Job, Customer, Model, and Serial.
3. Upload or paste evaluation screenshots.
4. Extract evaluation comments with OCR.
5. Search for required repairs or add a custom repair.
6. Choose the output option (Folder and PDF, Folders Only, or PDF Only).
7. Process the job and optionally print the generated PDF.

Evaluation form (`ev7.pdf`) fills info, notes, and repair fields. Final form
(`preship5.pdf`) fills info only.

### PDF → Images

1. Select one or more PDF files (or a folder path).
2. Choose an output folder (defaults to the source folder).
3. First page of each PDF is saved as PNG, named with the existing
   `first-4-characters + FirstCall.png` rule.

### Organize Files

1. Select a source folder (images may sit in nested subfolders).
2. Select a destination folder containing job/serial-named subfolders.
3. Files are matched by filename and moved to the right destination folder;
   unnumbered destination folders get the next `NN-` prefix.

## More Information

For Version 3 screenshots, detailed features, installation notes, and per-tab usage, see:

[`ponytail_evaluation_tool/README_v3.md`](./ponytail_evaluation_tool/README_v3.md)

For information about the original version, see:

[`tool_v1.0/README.md`](./tool_v1.0/README_v1.md)