import re
import shutil
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".avi"}

# Longest first so 8331FLR does not become 8331F.
DOC_CODES = ["ELR", "FLR", "EW", "FW", "E", "F", "EFirstCall","W"]


# ============================================================
# Source file parsing
# ============================================================

def parse_source_file(file_path: Path):
    if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return None

    stem = file_path.stem.strip()
    doc_code_pattern = "|".join(DOC_CODES)

    # Date + Withdraw:
    # 2026-04-30_1234W.jpg
    # 2026_04_30_1234W.jpg
    # 2026-04-30_1234W (1).jpg
    # 2026-04-30_1234W_front.jpg
    date_withdraw_match = re.match(
        r"^(?P<year>\d{4})[-_]\d{2}[-_]\d{2}_(?P<job>\d+)W(?:$|[^A-Za-z0-9].*|\d.*)",
        stem,
        re.IGNORECASE
    )

    if date_withdraw_match:
        return {
            "path": file_path,
            "filename": file_path.name,
            "match_key": ("job", date_withdraw_match.group("job"), "W"),
            "withdraw_year": date_withdraw_match.group("year"),
            "is_date_withdraw": True,
        }

    # Serial-based:
    # 123456WX1_E01JAN26.jpg
    # 123456WX1_F_side.png
    # 123456WX1_FLR01JAN26.jpg
    serial_match = re.match(
        rf"^(?P<serial>[A-Za-z0-9]+)_(?P<doc_code>{doc_code_pattern})(?:$|[^A-Za-z0-9].*|\d.*)",
        stem,
        re.IGNORECASE
    )

    if serial_match:
        return {
            "path": file_path,
            "filename": file_path.name,
            "match_key": (
                "serial",
                serial_match.group("serial").upper(),
                serial_match.group("doc_code").upper()
            ),
            "withdraw_year": None,
            "is_date_withdraw": False,
        }

    # Job-based:
    # 8331FLR_IMG_0687 (1).JPG
    # 1234E_1.jpg
    # 1234F_front.jpeg
    # 1234EW_1.jpg
    # 1234W_side.jpg
    job_match = re.match(
        rf"^(?P<job>\d+)(?P<doc_code>{doc_code_pattern})(?:$|[^A-Za-z0-9].*|\d.*)",
        stem,
        re.IGNORECASE
    )

    if job_match:
        return {
            "path": file_path,
            "filename": file_path.name,
            "match_key": (
                "job",
                job_match.group("job"),
                job_match.group("doc_code").upper()
            ),
            "withdraw_year": None,
            "is_date_withdraw": False,
        }

    return {
        "path": file_path,
        "filename": file_path.name,
        "match_key": None,
        "withdraw_year": None,
        "is_date_withdraw": False,
    }


# ============================================================
# Category folder helpers
# ============================================================

def normalize_category_name(folder_name: str):
    """
    Accepts category folders like:

        IMS
        IMS 01
        IMS 05
        Loaner Return
        Loaner Return 01
        Loaner Return 06
        Warranty
        Warranty 02
    """

    name = folder_name.strip().lower()
    name = re.sub(r"\s+", " ", name)

    if re.match(r"^ims(?:\s+\d+)?$", name):
        return "IMS"

    if re.match(r"^loaner return(?:\s+\d+)?$", name):
        return "Loaner Return"

    if re.match(r"^warranty(?:\s+\d+)?$", name):
        return "Warranty"

    if re.match(r"^withdrawn(?:\s+\d+)?$", name):
        return "Withdrawn"

    if re.match(r"^withdraw(?:\s+\d+)?$", name):
        return "Withdrawn"

    return None


def get_category_from_path(folder_path: Path, root_path: Path):
    """
    Finds whether a destination folder lives under:

        IMS / IMS 01
        Loaner Return / Loaner Return 01
        Warranty / Warranty 01
        Withdrawn / Withdrawn 01
    """

    try:
        relative_parts = folder_path.relative_to(root_path).parts
    except ValueError:
        relative_parts = folder_path.parts

    for part in relative_parts:
        category = normalize_category_name(part)

        if category:
            return category

    # Also check the root folder itself.
    root_category = normalize_category_name(root_path.name)

    if root_category:
        return root_category

    return None


# ============================================================
# Destination folder parsing
# ============================================================

def is_numbered_folder(folder_name: str) -> bool:
    """
    01-, 02-, 100- = already renamed.
    1234-, 8331- = job folder, not already renamed.
    """

    match = re.match(r"^(?P<num>\d+)-", folder_name)

    if not match:
        return False

    return len(match.group("num")) <= 3


def extract_hash_inside(folder_name: str):
    """
    Supports:

        (#8331FLR-Integrity Medical Service Inc)
        （#8331FLR-Integrity Medical Service Inc）
    """

    hash_match = re.search(
        r"[\(\uFF08]\s*#(?P<inside>[^\)\uFF09]*)[\)\uFF09]",
        folder_name
    )

    if not hash_match:
        return None

    return hash_match.group("inside").strip()


def extract_serial_from_destination_name(folder_name: str):
    before_hash = re.split(r"[\(\uFF08]\s*#", folder_name)[0].strip()

    # Remove text inside parentheses, like "(Pinless)".
    cleaned = re.sub(r"[\(\uFF08][^\)\uFF09]*[\)\uFF09]", " ", before_hash)

    tokens = re.findall(r"[A-Za-z0-9]+", cleaned)

    if not tokens:
        return None

    return tokens[-1].upper()


def parse_destination_folder(folder_path: Path, destination_root: Path):
    """
    Supports:

        8331-CV1-8A (Pinless) K0FNM3GM400054P (#8331FLR-Integrity Medical Service Inc)
        01-CV1-8A (Pinless) K0FNM3GM400054P (#8331FLR-Integrity Medical Service Inc)
        --RAB6-RS (Cartridge) 123456WX1 (#-F-IMS)

    Numbered folders are still valid for moving.
    They just do not get renamed again.
    """

    folder_name = folder_path.name
    inside = extract_hash_inside(folder_name)

    if not inside:
        return None

    doc_code_pattern = "|".join(DOC_CODES)
    category = get_category_from_path(folder_path, destination_root)

    # Job folder key:
    # #8331FLR-Integrity Medical Service Inc
    # #1234E-IMS
    job_match = re.match(
        rf"^(?P<job>\d+)(?P<doc_code>{doc_code_pattern})(?:-|$)",
        inside,
        re.IGNORECASE
    )

    if job_match:
        return {
            "path": folder_path,
            "match_key": (
                "job",
                job_match.group("job"),
                job_match.group("doc_code").upper()
            ),
            "already_numbered": is_numbered_folder(folder_name),
            "rename_allowed": True,
            "category": category,
        }

    # Serial/no-job folder key:
    # #-E-IMS
    # #-FLR-IMS
    no_job_match = re.match(
        rf"^-(?P<doc_code>{doc_code_pattern})(?:-|$)",
        inside,
        re.IGNORECASE
    )

    if no_job_match:
        serial = extract_serial_from_destination_name(folder_name)

        if not serial:
            return None

        return {
            "path": folder_path,
            "match_key": (
                "serial",
                serial,
                no_job_match.group("doc_code").upper()
            ),
            "already_numbered": is_numbered_folder(folder_name),
            "rename_allowed": True,
            "category": category,
        }

    return None


def format_match_key(match_key):
    key_type, value, doc_code = match_key

    if key_type == "job":
        return f"job {value} {doc_code}"

    if key_type == "serial":
        return f"serial {value} {doc_code}"

    return str(match_key)


# ============================================================
# Withdrawn fallback
# ============================================================

def is_withdrawn_folder(folder_path: Path) -> bool:
    return normalize_category_name(folder_path.name) == "Withdrawn"


def find_withdrawn_year_folder(destination_path: Path, year: str):
    # The selected destination may itself be the year folder:
    # .../<anything>/Withdrawn/2026, selected as ".../Withdrawn/2026".
    if is_withdrawn_folder(destination_path.parent) and destination_path.name == year:
        return {
            "path": destination_path,
            "match_key": ("withdrawn_year", year),
            "already_numbered": True,
            "rename_allowed": False,
            "category": "Withdrawn",
        }

    withdrawn_candidates = []

    if is_withdrawn_folder(destination_path):
        withdrawn_candidates.append(destination_path)

    for item in destination_path.rglob("*"):
        if item.is_dir() and is_withdrawn_folder(item):
            withdrawn_candidates.append(item)

    for withdrawn_folder in withdrawn_candidates:
        year_folder = withdrawn_folder / year

        if year_folder.exists() and year_folder.is_dir():
            return {
                "path": year_folder,
                "match_key": ("withdrawn_year", year),
                "already_numbered": True,
                "rename_allowed": False,
                "category": "Withdrawn",
            }

    return None


# ============================================================
# Scanning
# ============================================================

def scan_source_files(source_path: Path):
    files = []

    for item in source_path.rglob("*"):
        if not item.is_file():
            continue

        if item.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        parsed = parse_source_file(item)

        if parsed:
            files.append(parsed)

    return files


def scan_destination_folders(destination_path: Path):
    """
    Scans selected destination folder itself plus all subfolders.

    This supports structures like:

        Parent/
            IMS 01/
            Loaner Return 01/
                8331-CV1-8A (...) (#8331FLR-...)
            Warranty 05/

    Duplicate destination keys are hard errors.
    """

    key_to_infos = {}

    items_to_check = [destination_path]
    items_to_check.extend(destination_path.rglob("*"))

    for item in sorted(items_to_check, key=lambda p: str(p).lower()):
        if not item.is_dir():
            continue

        parsed = parse_destination_folder(item, destination_path)

        if not parsed:
            continue

        key = parsed["match_key"]
        key_to_infos.setdefault(key, []).append(parsed)

    duplicate_map = {
        key: infos
        for key, infos in key_to_infos.items()
        if len(infos) > 1
    }

    folders_by_key = {
        key: infos[0]
        for key, infos in key_to_infos.items()
        if len(infos) == 1
    }

    return folders_by_key, duplicate_map


def build_duplicate_log(duplicate_map):
    lines = [
        "Duplicate destination folders found. No action taken.",
        ""
    ]

    for key in sorted(duplicate_map.keys(), key=lambda k: format_match_key(k)):
        lines.append(f"Duplicate key: {format_match_key(key)}")

        for index, info in enumerate(duplicate_map[key], start=1):
            category_text = f" [{info['category']}]" if info.get("category") else ""
            lines.append(f"{index}. {info['path']}{category_text}")

        lines.append("")

    lines.append("Please remove, rename, or move one duplicate folder before processing.")
    return "\n".join(lines)


# ============================================================
# Moving and renaming
# ============================================================

def get_existing_folder_numbers(parent_path: Path):
    numbers = []

    for item in parent_path.iterdir():
        if not item.is_dir():
            continue

        match = re.match(r"^(?P<num>\d+)-", item.name)

        if not match:
            continue

        prefix = match.group("num")

        if len(prefix) <= 3:
            numbers.append(int(prefix))

    return numbers


def get_next_folder_number(parent_path: Path):
    return max(get_existing_folder_numbers(parent_path), default=0) + 1


def build_renamed_folder_path(folder_path: Path, next_number: int):
    folder_name = folder_path.name
    number_prefix = f"{next_number:02d}"

    if folder_name.startswith("--"):
        rest = folder_name[2:].lstrip("-")
        return folder_path.parent / f"{number_prefix}-{rest}"

    if "-" in folder_name:
        rest = folder_name.split("-", 1)[1]
        return folder_path.parent / f"{number_prefix}-{rest}"

    return folder_path.parent / f"{number_prefix}-{folder_name}"


def safe_move_file(source_file: Path, destination_folder: Path):
    target = destination_folder / source_file.name

    if target.exists():
        base = source_file.stem
        suffix = source_file.suffix
        counter = 1

        while True:
            candidate = destination_folder / f"{base}_copy{counter}{suffix}"

            if not candidate.exists():
                target = candidate
                break

            counter += 1

    shutil.move(str(source_file), str(target))
    return target


def process_files(source_path: Path, destination_path: Path):
    destination_folders_by_key, duplicate_map = scan_destination_folders(destination_path)

    # Hard stop before touching files.
    if duplicate_map:
        return build_duplicate_log(duplicate_map)

    source_files = scan_source_files(source_path)

    grouped_moves = {}
    leftovers = []

    for file_info in source_files:
        match_key = file_info["match_key"]

        if not match_key:
            leftovers.append(file_info["filename"])
            continue

        destination_info = destination_folders_by_key.get(match_key)

        # Withdraw fallback:
        # 2026-04-30_1234W.jpg -> Withdrawn/2026
        if not destination_info and file_info["is_date_withdraw"]:
            destination_info = find_withdrawn_year_folder(
                destination_path,
                file_info["withdraw_year"]
            )

        if not destination_info:
            leftovers.append(file_info["filename"])
            continue

        destination_folder = destination_info["path"]

        grouped_moves.setdefault(destination_folder, {
            "destination_info": destination_info,
            "files": []
        })

        grouped_moves[destination_folder]["files"].append(file_info)

    log_lines = []

    for destination_folder in sorted(grouped_moves.keys(), key=lambda p: str(p).lower()):
        group = grouped_moves[destination_folder]
        destination_info = group["destination_info"]
        files_to_move = group["files"]

        moved_file_names = []

        for file_info in files_to_move:
            source_file = file_info["path"]

            if not source_file.exists():
                leftovers.append(file_info["filename"])
                continue

            safe_move_file(source_file, destination_folder)
            moved_file_names.append(file_info["filename"])

        if not moved_file_names:
            continue

        log_lines.append(
            f"Done moving {', '.join(moved_file_names)} moved to {destination_folder}."
        )

        if not destination_info["rename_allowed"]:
            log_lines.append("Withdrawn year folder. No rename needed.")
            log_lines.append("")
            continue

        if destination_info["already_numbered"]:
            log_lines.append("Destination folder already renamed. No rename needed.")
            log_lines.append("")
            continue

        parent_path = destination_folder.parent
        next_number = get_next_folder_number(parent_path)
        renamed_folder_path = build_renamed_folder_path(destination_folder, next_number)

        while renamed_folder_path.exists():
            next_number += 1
            renamed_folder_path = build_renamed_folder_path(destination_folder, next_number)

        destination_folder.rename(renamed_folder_path)

        log_lines.append(f"Renamed destination folder to {renamed_folder_path}.")
        log_lines.append("")

    if leftovers:
        log_lines.append(f"Left over {', '.join(sorted(leftovers))}")
    else:
        log_lines.append("Left over none")

    if not source_files:
        log_lines.append("")
        log_lines.append("No supported files were found in the source folder.")

    if not grouped_moves and source_files:
        log_lines.append("")
        log_lines.append("No matching destination folders were found.")

    return "\n".join(log_lines)

# ============================================================
# Tkinter GUI
# ============================================================

class ImageFolderOrganizerFrame(ttk.Frame):
    """Reusable folder-organizer interface for a ttk.Notebook tab."""

    def __init__(self, parent):
        super().__init__(parent, padding=16)

        self.source_var = tk.StringVar()
        self.destination_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")

        self.build_ui()

    def build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        heading = ttk.Frame(self)
        heading.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        heading.columnconfigure(0, weight=1)

        ttk.Label(
            heading,
            text="Organize Files",
            font=("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(
            heading,
            text="Move matching images, PDFs, and videos into their destination folders.",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

        folders = ttk.LabelFrame(self, text="Folders", padding=12)
        folders.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        folders.columnconfigure(1, weight=1)

        ttk.Label(folders, text="Source Folder:").grid(
            row=0, column=0, sticky="w", padx=(0, 10), pady=(0, 8)
        )
        ttk.Entry(folders, textvariable=self.source_var).grid(
            row=0, column=1, sticky="ew", pady=(0, 8)
        )
        ttk.Button(
            folders,
            text="Browse...",
            command=self.pick_source_folder,
        ).grid(row=0, column=2, padx=(8, 0), pady=(0, 8))

        ttk.Label(folders, text="Destination Folder:").grid(
            row=1, column=0, sticky="w", padx=(0, 10)
        )
        ttk.Entry(folders, textvariable=self.destination_var).grid(
            row=1, column=1, sticky="ew"
        )
        ttk.Button(
            folders,
            text="Browse...",
            command=self.pick_destination_folder,
        ).grid(row=1, column=2, padx=(8, 0))

        ttk.Label(
            self,
            text=(
                "Scans IMS, Loaner Return, Warranty, and Withdrawn folders, "
                "including numbered category folders such as Loaner Return 01."
            ),
            wraplength=1000,
        ).grid(row=2, column=0, sticky="w", pady=(0, 10))

        log_frame = ttk.LabelFrame(self, text="Processing Log", padding=10)
        log_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_box = tk.Text(log_frame, wrap="word", height=14, state="disabled")
        self.log_box.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_box.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_box.configure(yscrollcommand=scrollbar.set)

        bottom = ttk.Frame(self)
        bottom.grid(row=4, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)

        ttk.Label(bottom, textvariable=self.status_var).grid(
            row=0, column=0, sticky="w"
        )

        self.clear_button = ttk.Button(
            bottom,
            text="Clear Log",
            command=self.clear_log,
        )
        self.clear_button.grid(row=0, column=1, padx=(8, 8))

        self.process_button = ttk.Button(
            bottom,
            text="Organize Files",
            command=self.start_process,
            width=18,
        )
        self.process_button.grid(row=0, column=2)

    def pick_source_folder(self):
        try:
            folder = filedialog.askdirectory(title="Select Source Folder")
        except KeyboardInterrupt:
            return

        if folder:
            self.source_var.set(folder)

    def pick_destination_folder(self):
        try:
            folder = filedialog.askdirectory(title="Select Destination Folder")
        except KeyboardInterrupt:
            return

        if folder:
            self.destination_var.set(folder)

    def clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", tk.END)
        self.log_box.configure(state="disabled")

    def write_log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert(tk.END, text + "\n")
        self.log_box.see(tk.END)
        self.log_box.configure(state="disabled")

    def validate_paths(self):
        source = Path(self.source_var.get().strip())
        destination = Path(self.destination_var.get().strip())

        if not source.exists() or not source.is_dir():
            messagebox.showerror(
                "Invalid Source Folder",
                "Please select a valid source folder.",
            )
            return None, None

        if not destination.exists() or not destination.is_dir():
            messagebox.showerror(
                "Invalid Destination Folder",
                "Please select a valid destination folder.",
            )
            return None, None

        return source, destination

    def start_process(self):
        source, destination = self.validate_paths()

        if not source or not destination:
            return

        self.process_button.state(["disabled"])
        self.clear_log()
        self.write_log("Processing...")
        self.status_var.set("Processing...")

        thread = threading.Thread(
            target=self.run_process_thread,
            args=(source, destination),
            daemon=True,
        )
        thread.start()

    def run_process_thread(self, source, destination):
        try:
            result_log = process_files(source, destination)
            error = None
        except Exception as exc:
            result_log = f"Error: {exc}"
            error = exc

        self.after(0, self.finish_process, result_log, error)

    def finish_process(self, result_log, error=None):
        self.clear_log()
        self.write_log(result_log)
        self.process_button.state(["!disabled"])

        if error is not None:
            self.status_var.set("Processing failed.")
            messagebox.showerror("Organizer Error", str(error))
            return

        self.status_var.set("Processing finished.")
        messagebox.showinfo("Done", "Processing finished.")


# Backward-compatible alias for code that used the old class name.
ImageFolderOrganizerApp = ImageFolderOrganizerFrame


def main():
    root = tk.Tk()
    root.title("Image / PDF Folder Organizer")
    root.geometry("760x560")
    root.minsize(650, 460)

    frame = ImageFolderOrganizerFrame(root)
    frame.pack(fill="both", expand=True)

    root.mainloop()


if __name__ == "__main__":
    main()
