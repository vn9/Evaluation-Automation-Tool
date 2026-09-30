# Evaluation Automation Tool

A Python desktop application for automating evaluation and final-form workflows, including Helpdesk data extraction, evaluation screenshot OCR, repair selection, folder creation, PDF generation, and optional printing.

This repository contains two versions of the tool:

## Versions

### `tool_v1.0`
Original version of the Evaluation Automation Tool.

This version contains the earlier workflow and UI used before the Version 2 redesign.

### `tool_v2.0`
Current version of the Evaluation Automation Tool.

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

Version 2 is the current version and should be used for normal operation.

## Repository Structure

```text
Evaluation-Automation-Tool/
├── tool_v1.0/
│   └── Version 1 application files
│
├── tool_v2.0/
│   └── Version 2 application files
│
└── README.md
```

Each version is kept in its own folder so the previous workflow remains available while Version 2 continues to be developed.

## Run Version 2

Open a terminal in:

```text
tool_v2.0
```

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Then start the application:

```bash
python main_eval_final.py
```

## Version 2 Workflow

### Evaluation

Evaluation mode supports the full workflow:

1. Paste Helpdesk data.
2. The application automatically extracts Job, Customer, Model, and Serial.
3. Upload or paste evaluation screenshots.
4. Extract evaluation comments with OCR.
5. Search for required repairs or add a custom repair.
6. Choose the output option.
7. Process the job and optionally print the generated PDF.

### Final

Final mode uses the Helpdesk data needed to generate the final form.

Evaluation-specific image, extracted-note, and repair controls are not required for the Final workflow.

## More Information

For Version 2 screenshots, detailed features, installation notes, and executable build instructions, see:

[`tool_v2.0/README.md`](./tool_v2.0/README_v2.md)

For information about the original version, see:

[`tool_v1.0/README.md`](./tool_v1.0/README_v1.md)
