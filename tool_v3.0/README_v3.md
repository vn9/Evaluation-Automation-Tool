# Processing Tools

Tkinter desktop app for the daily processing workflow. Three tabs in one
window:

- **Main Processing** — paste Helpdesk rows, OCR evaluation screenshots, pick
  repairs, fill and print PDF forms.
- **PDF → Images** — convert the first page of PDFs to PNG.
- **Organize Files** — move images/PDFs/videos into destination subfolders by
  filename.

## Requirements

- Windows (uses `win32api` for printing and Tkinter for the UI).
- Python 3.x.
- Tesseract OCR. The bundled `Tesseract-OCR/` folder (with `tesseract.exe` and
  `tessdata/`) is used if present; otherwise a standard install at
  `C:\Program Files\Tesseract-OCR` is found automatically.

Install dependencies:

```bat
python -m pip install -r requirements.txt
```

`pymupdf` (needed by the PDF tabs) is not in `requirements.txt` — add it:

```bat
python -m pip install PyMuPDF
```

## Running

```bat
python main_eval_final_v3.py
```

## Main Processing

1. **Helpdesk Data** — paste rows copied from Helpdesk (Markdown table or
   tab-separated). Each row becomes `Job, Customer, Model, Serial`. Rows with
   wrong column counts or missing fields are reported before processing.
2. **Evaluation Images** (Evaluation form only) — upload or paste screenshots
   (`.png`, `.jpg`, `.jpeg`, `.bmp`, `.pdf`). "Extract Evaluation" runs OCR
   and pulls the populated `Comment(s)` fields into the output box, where they
   can be edited.
3. **Repairs** — answer "Yes" to fill the repair part, search the built-in
   repair descriptions by keyword, or add custom repairs. Selected repairs are
   numbered and can be copied.
4. **Output Options**:
   - *Folder and PDF* — creates a job folder, then fills and saves the PDF in it.
   - *Folders Only* — creates a folder for every pasted row.
   - *PDF Only* — fills the PDF and asks for a save location.
   - Optionally sends the finished PDF to the printer.

Form type determines the source template and behavior:

| Form | Template | Notes |
|------|----------|-------|
| Evaluation | `ev7.pdf` | Fills info, notes and repairs fields. |
| Final | `preship5.pdf` | Fills info only; notes and repairs stay empty. |

Folder names follow `Job-Model Serial (#Job{Esuffix}-Customer)`.

### Suggested Repairs

After extraction, the **Suggested Repairs** panel lists repairs implied by the
evaluation comments (checkboxes — tick the ones to use). Rules, first match
wins:

| Comment keywords | Suggestion |
|------------------|------------|
| leaking, leak, bubbles | `Repair: Leak` |
| damaged, torn, tear, delaminated, cut, hole, many ... (e.g. many dead elements / paint scratches / deep scratches) | `Replacement: <field>` |
| 3D/4D error, can't find home, broken driving wire | `Repair: 3D/4D` and `Replacement: Array Housing` |
| peeling, discolored, yellow stains, scratches | `Cosmetic: <field>` |

Comments saying **"use as is" / "used as it is"** produce no suggestion.

## PDF → Images

- **Source** — select one or more PDF files (or type/paste a folder path to
  convert every PDF in it). The entry shows the files' common folder.
- **Output** — pick a folder for the PNGs (defaults to the source folder if
  empty).
- Converts the **first page** of each PDF. Output name keeps the rule:
  first 4 characters of the filename + `FirstCall.png`
  (e.g. `8331FLR_IMG.jpg` → `8331F...FirstCall.png`).
- Runs in a background thread; progress appears in the log.

## Organize Files

Moves supported files (`.pdf`, `.jpg`, `.jpeg`, `.png`, `.avi`) from a source
folder into matching destination subfolders, based on the filename.

- Source files are scanned **recursively** — nested subfolders are handled
  automatically.
- Destination subfolders are matched by job or serial code.

Filename patterns recognized:

| Pattern | Example | Destination key |
|---------|---------|-----------------|
| Job-based | `8331FLR_IMG_0687.JPG`, `1234E_1.jpg`, `1234W_side.jpg` | job + code (E/F/W/EW/FLR/ELR) |
| Serial-based | `123456WX1_E01JAN26.jpg`, `123456WX1_FLR01JAN26.jpg` | serial + code |
| Date + withdraw | `2026-04-30_1234W.jpg` | moves to `Withdrawn/<year>` |

Destination folders are recognized by the `(#8331FLR-...)` marker in the name
(for job folders) or `(Pinless) SERIAL (#-F-IMS)` style (for serial folders).
Category folders `IMS`, `Loaner Return`, `Warranty`, `Withdrawn` (with or
without a number suffix) are recognized anywhere under the destination.

Behavior notes:

- Duplicate destination keys (two folders matching the same job) are a hard
  stop — nothing is moved until they are resolved.
- Already-numbered destination folders (`01-`, `02-`, ...) are not renamed;
  unnumbered ones get the next available `NN-` prefix.
- File name collisions in the destination get a `_copy1`, `_copy2`, ... suffix.
- Withdrawn files go to `Withdrawn/<year>`. Selecting `Withdrawn`, the parent
  of `Withdrawn/2026`, or `Withdrawn/2026` itself all work.

## Layout

- `main_eval_final_v3.py` — entry point.
- `gui_v3.py` — main window, Helpdesk parsing, OCR extraction, repair list,
  PDF/folder output.
- `pdf_to_img.py` — PDF→PNG conversion tab.
- `image_folder_organizer.py` — organize-files tab and matching logic.
- `utils_v3.py` — PDF form filling (PyPDF2) and PyInstaller resource helper.
- `ev7.pdf`, `preship5.pdf` — fillable templates.