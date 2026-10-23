"""Helpdesk parsing shared by the Text input tab and the image OCR path.

Both entry points produce the same record shape: a list of
``[Job, Customer, Model, Serial]`` rows, so the Helpdesk Output table does
not care whether a row came from pasted text or from an OCR screenshot.
"""

import re


# Every Helpdesk row is trimmed/padded to exactly this many columns.
helpdesk_column_count = 4

# The Helpdesk columns this app reads, in the order it reads them.
helpdesk_field_names = ("Job", "Customer", "Model", "Serial")

# "Job #8379", "Job#8379", "Job # 8379", "Job 8379", "Job Number: 8379",
# "Job No. 8379".
job_number_pattern = re.compile(
    r"\bjob\s*(?:number|num|no\.?|#)?\s*[:#]?\s*(\d{2,})\b",
    re.IGNORECASE,
)

# Labels that open a block on a Helpdesk page. A value never runs past the
# next label, so "Customer" stops at "Service Location" instead of eating
# every line up to the Job Name.
helpdesk_block_labels = {
    "Address": "address",
    "Assigned To": "assigned_to",
    "Contact": "contact",
    "Customer": "customer",
    "Description": "description",
    "Email": "email",
    "Job Details": "job_details",
    "Job Name": "job_name",
    "Job Number": "job_number",
    "Job Type": "job_type",
    "Model": "model",
    "Notes": "notes",
    "Order Number": "order_number",
    "Phone": "phone",
    "Priority": "priority",
    "Requested By": "requested_by",
    "Serial": "serial",
    "Serial Number": "serial_number",
    "Service Location": "service_location",
    "Site": "site",
    "Status": "status",
    "Symptom": "symptom",
    "Term": "term",
    "Type": "type",
}

# The same labels, keyed the way the OCR writes them.
helpdesk_block_keys = {
    name.lower(): key for name, key in helpdesk_block_labels.items()
}

# Only these labels prove an image is a Helpdesk page.
helpdesk_indicator_labels = (
    "assigned to",
    "customer",
    "job details",
    "job name",
    "job number",
    "order number",
    "requested by",
    "service location",
    "status",
)

# Status wording that only shows up on a Helpdesk page.
helpdesk_status_words = (
    "closed",
    "evaluation complete",
    "in-progress",
    "in progress",
    "open",
    "pending",
)

# How many indicators an image needs before it is read as a Helpdesk page.
# One word is too easy to hit by accident, so two is the floor.
helpdesk_indicator_threshold = 2


def _word_pattern(names):
    """Build a pattern that finds the given words as whole words."""
    return re.compile(
        r"(?<![A-Za-z0-9])(?:"
        + "|".join(re.escape(name) for name in sorted(names, key=len, reverse=True))
        + r")(?![A-Za-z0-9])",
        re.IGNORECASE,
    )


# Finds a block label and the value that follows it on the same line.
label_scan_pattern = re.compile(
    r"(?<![A-Za-z0-9])(?P<label>"
    + "|".join(
        re.escape(name) for name in sorted(helpdesk_block_labels, key=len, reverse=True)
    )
    + r")(?![A-Za-z0-9])\s*:?\s*",
    re.IGNORECASE,
)

# Finds the strong labels only, used to tell a Helpdesk page apart.
indicator_pattern = _word_pattern(helpdesk_indicator_labels)
status_pattern = _word_pattern(helpdesk_status_words)

# "V4-8 SN: B24919310016436" and "RIC5-9W-RS SN:216930KR8" - the model may
# hold letters, digits and hyphens, the serial is the next token. Text that
# follows the serial is ignored, so a line that also carries the next field
# label still reads.
model_serial_pattern = re.compile(
    r"(?P<model>[A-Za-z0-9][A-Za-z0-9\-_./]*)\s+S/?N\s*:?\s*"
    r"(?P<serial>[A-Za-z0-9][A-Za-z0-9\-_./]*)",
    re.IGNORECASE,
)

# A serial on its own is still usable, the model stays empty.
serial_only_pattern = re.compile(
    r"^S/?N\s*:?\s*(?P<serial>[A-Za-z0-9][A-Za-z0-9\-_./]*)\s*$",
    re.IGNORECASE,
)

# The chrome the page shows next to a label, never a field value.
ui_noise_tokens = ("(", ")", "|", "~", "@", "&", "€", ".")

# The OCR reads the gap between two columns as a lone period.
column_separator_pattern = re.compile(r"\s+\.\s+")

# Characters the OCR adds around a word.
word_cleaners = ".,:;|'\"()[]{}‘’“”"


def clean_cell(value):
    """Strip the Markdown decoration a copied Helpdesk cell can carry."""
    value = value.strip()

    link_match = re.fullmatch(r"\[(.*?)\]\((.*?)\)", value)

    if link_match:
        value = link_match.group(1)

    value = value.replace("**", "")
    value = re.sub(r"<br\s*/?>", "", value, flags=re.IGNORECASE)

    return value.strip()


def split_row(columns):
    """Map the raw columns of one pasted row onto Job/Customer/Model/Serial."""
    if len(columns) == 9:
        return [columns[0], columns[4], columns[6], columns[8]]

    if len(columns) == helpdesk_column_count:
        return columns

    if len(columns) == 3:
        if not columns[0].isnumeric():
            return ["", *columns]

        return [*columns, ""]

    return None


def find_missing_fields(rows):
    """Return (row index, field name) for every empty field of every row."""
    missing_fields = []

    for index, row in enumerate(rows, start=1):
        for field_index, field_name in enumerate(helpdesk_field_names):
            if field_index >= len(row) or not row[field_index].strip():
                missing_fields.append((index, field_name))

    return missing_fields


def split_pasted_line(line):
    """Split one pasted line into raw columns, or None when it is unreadable."""
    if "\t" in line:
        return line.split("\t")

    stripped_line = line.strip()

    if stripped_line.startswith("|") and stripped_line.endswith("|"):
        return stripped_line.strip("|").split("|")

    # Fall back on runs of two or more spaces, which is how a copied
    # Helpdesk row can look when it arrives without tabs.
    columns = re.split(r"\s{2,}", stripped_line)

    if len(columns) > 1:
        return columns

    return None


def parse_helpdesk_text(text):
    """Parse pasted Helpdesk text.

    Returns (rows, errors). Valid rows are always returned, so one bad row
    does not throw away the good ones; the errors describe what was skipped.
    """
    rows = []
    errors = []
    row_number = 0

    for line in text.splitlines():
        stripped_line = line.strip()

        if not stripped_line:
            continue

        # A Markdown table separator such as "|---|---|" is not a data row.
        if stripped_line.startswith("|") and re.fullmatch(
            r"[\s|:\-]+", stripped_line
        ):
            continue

        row_number += 1

        raw_columns = split_pasted_line(line)

        if raw_columns is None:
            errors.append(f"Row {row_number} could not be recognized.")
            continue

        columns = [clean_cell(value) for value in raw_columns]

        row = split_row(columns)

        if row is None:
            errors.append(f"Row {row_number} has the wrong number of columns.")
            continue

        row = (row + [""] * helpdesk_column_count)[:helpdesk_column_count]
        rows.append(row)

        for _index, field_name in find_missing_fields([row]):
            errors.append(f"Row {row_number} is missing {field_name}.")

    return rows, errors


def parse_job_name(text):
    """Read the Model and the Serial Number out of a Job Name line.

    Returns ("", "") when the line cannot be read with confidence.
    """
    text = " ".join(text.split())

    match = model_serial_pattern.search(text)

    if match:
        return match.group("model"), match.group("serial")

    match = serial_only_pattern.match(text)

    if match:
        return "", match.group("serial")

    return "", ""


def strip_ui_noise(text):
    """Drop the page chrome that sits next to a label, like "(edit)"."""
    kept = []

    for word in text.split():
        if word in ui_noise_tokens:
            continue

        if word.strip("()").lower() in ("edit", "view", "add", "print"):
            continue

        kept.append(word)

    return " ".join(kept)


def cut_at_column_separator(text):
    """Cut a line that holds two columns at the separator the OCR read."""
    return column_separator_pattern.split(text, 1)[0]


def split_labeled_line(line):
    """Return the (block, value) pairs one OCR line carries.

    A line can hold more than one label, for example "Job Name RIC5-9W-RS
    SN:216930KR8 Status Open", so every label takes the text up to the next
    label as its value.
    """
    matches = list(label_scan_pattern.finditer(line))
    segments = []

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(line)
        label = match.group("label").lower()
        value = line[match.end():end].strip()
        segments.append((helpdesk_block_keys[label], value))

    return segments


def detect_helpdesk(text):
    """Return the Helpdesk indicators found in one OCR text.

    The indicators are what tells a Helpdesk screenshot apart from an
    Evaluation one, so they are counted from the raw text and not from the
    fields that could be read out of it.
    """
    indicators = []

    if job_number_pattern.search(text):
        indicators.append("Job #")

    found_labels = {
        match.group(0).lower() for match in indicator_pattern.finditer(text)
    }

    for label in helpdesk_indicator_labels:
        if label in found_labels:
            indicators.append(label.title())

    status_match = status_pattern.search(text)

    if status_match:
        indicators.append(f"Status: {status_match.group(0)}")

    return indicators


def is_helpdesk_text(text):
    """Return (is_helpdesk, indicators) for one OCR text."""
    indicators = detect_helpdesk(text)

    return len(indicators) >= helpdesk_indicator_threshold, indicators


def read_customer_value(lines, label_index, same_line_value):
    """Read the Customer value that belongs to a Customer label.

    The page puts the Customer next to the Service Location, so the OCR can
    merge both columns into one line. The value is therefore read from the
    lines under the label and cut where the next column starts.
    """
    value = strip_ui_noise(same_line_value)

    if value:
        return value

    value_lines = []

    for line in lines[label_index + 1:]:
        if split_labeled_line(line):
            break

        value_lines.append(line)

    return strip_ui_noise(cut_at_column_separator(" ".join(value_lines)))


def parse_helpdesk_ocr(text):
    """Read Helpdesk records out of OCR text.

    Every "Job #" starts a new record and the labelled blocks that follow
    belong to it. A block stops at the next label, so the Customer is never
    the Service Location or the Job Details. A record keeps the fields that
    could be read, a missing optional field is not a reason to drop it.
    """
    records = []
    current = None
    block = None
    value_lines = []

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    def close_value():
        """Hand the collected lines to the block they belong to."""
        nonlocal value_lines

        if current is not None and block is not None:
            value = " ".join(value_lines).strip()

            if block == "job_name":
                current["model"], current["serial"] = parse_job_name(value)

        value_lines = []

    def close_record():
        nonlocal current, block

        close_value()

        if current is not None:
            records.append(current)

        current = None
        block = None

    for index, line in enumerate(lines):
        job_match = job_number_pattern.search(line)

        if job_match:
            close_record()

            current = {
                "job": job_match.group(1),
                "customer": "",
                "model": "",
                "serial": "",
            }

        # The labels of the line belong to the record that is open now, and
        # a job number on the same line as a label does not eat the label.
        segments = split_labeled_line(line)

        if not segments:
            if current is not None and block is not None:
                value_lines.append(line)

            continue

        for name, value in segments:
            close_value()

            if name == "customer":
                # The Customer column sits next to the Service Location, so
                # the value is read from the lines under the label.
                if current is not None:
                    current["customer"] = read_customer_value(lines, index, value)

                block = None
                value_lines = []
                continue

            block = name
            value_lines = [value] if value else []

    close_record()

    return [
        [record["job"], record["customer"], record["model"], record["serial"]]
        for record in records
        if record["job"]
    ]


# ================================================================
# Positional OCR, used to read the columns of a Helpdesk page
# ================================================================


def group_ocr_words(data):
    """Group the words of pytesseract image_to_data into positioned lines.

    Each line is a list of words, each word is (text, left, top, right, bottom).
    """
    lines = {}

    for index, text in enumerate(data.get("text", [])):
        text = text.strip()

        if not text:
            continue

        key = (
            data["block_num"][index],
            data["par_num"][index],
            data["line_num"][index],
        )

        left = data["left"][index]
        top = data["top"][index]

        word = (
            text,
            left,
            top,
            left + data["width"][index],
            top + data["height"][index],
        )

        lines.setdefault(key, []).append(word)

    grouped = [sorted(words, key=lambda word: word[1]) for words in lines.values()]

    return sorted(grouped, key=lambda words: words[0][2])


def words_spell_label(words, index, label):
    """Return the index after the label when the words spell it out."""
    wanted = label.lower().split()

    for offset, part in enumerate(wanted):
        if index + offset >= len(words):
            return None

        text = words[index + offset][0].strip(word_cleaners).lower()

        if text != part:
            return None

    return index + len(wanted)


def find_label_words(lines, label):
    """Find a label in the positioned words: (line index, word index, left)."""
    for line_index, words in enumerate(lines):
        for word_index in range(len(words)):
            if words_spell_label(words, word_index, label) is not None:
                return line_index, word_index, words[word_index][1]

    return None


def find_column_end(words, label_left):
    """The left edge of the next label to the right: that is the next column."""
    end = None

    for index, word in enumerate(words):
        if word[1] <= label_left:
            continue

        for label in helpdesk_block_labels:
            if words_spell_label(words, index, label) is None:
                continue

            if end is None or word[1] < end:
                end = word[1]

            break

    return end


def word_in_column(word, column_start, column_end):
    """True when a word starts inside the column of a label."""
    if word[1] < column_start - 30:
        return False

    if column_end is not None and word[1] >= column_end:
        return False

    return True


def line_starts_a_field(words, column_start, column_end):
    """True when a line opens a new field inside the column of a label."""
    for index, word in enumerate(words):
        if not word_in_column(word, column_start, column_end):
            continue

        for label in helpdesk_block_labels:
            if words_spell_label(words, index, label) is not None:
                return True

    return False


def read_column_below(lines, label_line_index, column_start, column_end):
    """Read the words under a label, in the column the label owns."""
    collected = []

    for words in lines[label_line_index + 1:]:
        if line_starts_a_field(words, column_start, column_end):
            break

        column_words = [
            word for word in words if word_in_column(word, column_start, column_end)
        ]

        if not column_words:
            continue

        collected.extend(column_words)

    return strip_ui_noise(" ".join(word[0] for word in collected))


def read_labeled_value(lines, label):
    """Read the value of a label: the text next to it or the text under it."""
    found = find_label_words(lines, label)

    if found is None:
        return ""

    line_index, word_index, left = found
    words = lines[line_index]
    end = words_spell_label(words, word_index, label)

    # The value can sit right next to the label, up to the next label.
    same_line = []

    for index in range(end, len(words)):
        if any(
            words_spell_label(words, index, other) is not None
            for other in helpdesk_block_labels
        ):
            break

        same_line.append(words[index])

    value = strip_ui_noise(" ".join(word[0] for word in same_line))

    if value:
        return value

    # Or under the label, in the column the label owns.
    return read_column_below(lines, line_index, left, find_column_end(words, left))


def find_text_box(lines, label):
    """Return the box of a label and its value: (left, top, right, bottom)."""
    found = find_label_words(lines, label)

    if found is None:
        return None

    line_index, word_index, left = found
    words = lines[line_index]
    end = words_spell_label(words, word_index, label)

    box_words = list(words[word_index:end])

    for index in range(end, len(words)):
        if any(
            words_spell_label(words, index, other) is not None
            for other in helpdesk_block_labels
        ):
            break

        box_words.append(words[index])

    return (
        min(word[1] for word in box_words),
        min(word[2] for word in box_words),
        max(word[3] for word in box_words),
        max(word[4] for word in box_words),
    )


def parse_helpdesk_from_words(lines):
    """Read Helpdesk records out of positioned OCR words.

    Each line is a list of words, each word is (text, left, top, right, bottom).
    The positions are what separate the columns of the page, so the Customer
    is the text under the Customer label and not the Service Location next
    to it.
    """
    records = []
    job_lines = []

    for line_index, words in enumerate(lines):
        text = " ".join(word[0] for word in words)
        match = job_number_pattern.search(text)

        if match:
            job_lines.append((line_index, match.group(1)))

    for index, (line_index, job_number) in enumerate(job_lines):
        end_index = (
            job_lines[index + 1][0] if index + 1 < len(job_lines) else len(lines)
        )

        region = lines[line_index:end_index]

        customer = read_labeled_value(region, "Customer")
        model, serial = parse_job_name(read_labeled_value(region, "Job Name"))

        records.append([job_number, customer, model, serial])

    return records


def ocr_confidence(data, box):
    """The average OCR confidence of the words that fall inside a box."""
    left, top, right, bottom = box
    confidences = []

    for index, text in enumerate(data.get("text", [])):
        if not text.strip():
            continue

        word_left = data["left"][index]
        word_top = data["top"][index]
        word_right = word_left + data["width"][index]
        word_bottom = word_top + data["height"][index]

        if word_right < left or word_left > right:
            continue

        if word_bottom < top or word_top > bottom:
            continue

        confidences.append(data["conf"][index])

    if not confidences:
        return -1.0

    return sum(confidences) / len(confidences)


def format_copy_text(rows):
    """Build the clipboard text: one record per line, real tabs between."""
    return "\n".join("\t".join(row) for row in rows)
