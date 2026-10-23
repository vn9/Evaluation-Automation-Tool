# Processing Tools v4

Processing Tools v4 is a desktop application for extracting service information, creating folders and PDFs, converting PDFs to images, and organizing files.

## Main Processing

The Main Processing tab supports two input methods:

- paste Helpdesk text
- paste or upload images

Images may contain Helpdesk information, Evaluation information, or both.

The application extracts recognized data from the input and displays it in the output areas for review.

The Images input offers paste from the clipboard, file upload, removing selected entries and running the extraction. The Text input is parsed when the text is pasted.

### Helpdesk Output

Extracted Helpdesk information is displayed in an editable output area, one row per record.

The user can:
- review extracted records
- correct extracted values
- select the record to use for PDF processing
- copy all extracted Helpdesk records

### Evaluation Output

Extracted Evaluation information is displayed in an editable text area.

The user can review and correct the extracted notes before processing.

### Repairs

The Repairs section supports:
- suggested repairs
- repair search
- custom repairs
- selected repairs

Repairs are applied to the Evaluation form.

### Output Options

Available processing options include:
- Folder and PDF
- Folders Only
- PDF Only

Folders Only can create multiple folders when multiple Helpdesk records are available.

PDF-related processing uses the selected Helpdesk record together with the edited Evaluation information and selected repairs.

The print option sends the finished PDF to the default printer.

## PDF -> Images

The PDF -> Images tab converts selected PDF files into PNG images.

For each selected PDF:
- the application opens the PDF
- uses the first page
- renders the first page as an image
- saves the result as a PNG file

This is useful when the first page of a PDF needs to be used as an image for later processing.

The user can select one or multiple PDF files and choose which files to convert instead of automatically converting every PDF in a folder. Entering a folder path instead converts every PDF in that folder.

The output folder can be chosen; it defaults to the source folder.

## Organize Files

The Organize Files tab moves supported files into matching destination folders.

It uses the existing file and folder matching rules to:
- find the appropriate destination
- move matching files
- avoid overwriting duplicate filenames
- rename destination folders when required
- handle the existing withdrawn-folder workflow

## Editing Extracted Data

Extracted data can be edited before processing.

The values currently shown in the application are used when creating folders, PDFs, and other output.

## Running

Requirements:
- Windows
- Python 3
- Tesseract OCR (the bundled Tesseract folder is used when present, otherwise a standard installation is found automatically)

Install the dependencies and start the application with the v4 entry script:

```bat
python -m pip install -r requirements.txt
python main_eval_final_v4.py
```

Packaging uses the PyInstaller spec, which bundles the PDF templates, the icon and the Tesseract folder:

```bat
pyinstaller ProbeLab_Tool.spec
```
