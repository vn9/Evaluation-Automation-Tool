import tkinter as tk
import pyperclip

# Create the main application window
root = tk.Tk()
root.title("Require Repair Form")
root.geometry("750x750")

# Define colors for frames (optional, for better visualization)
colors = ["lightblue", "lightcoral", "lightgreen", "yellow"]
labels = ["Notes", "Replacement", "Repair", "Cosmetic"]

# Dictionary to store checkbox variables
#checkbox_vars = {label: [] for label in labels}
checkbox_vars = {}
for label in labels:
    checkbox_vars[label] = []

#Options for Notes
notes_options = [
    "NEED LENS REPLACEMENT FOR FURTHER EVALUATION",
    "Can't Fix/Repair - *Replace this with your reasons not to repair/fix*"
]

# Options for Replacement frame
replacement_options = [
    "Lens", "Cap", "Array", "Shaft Housing", "Housing Strain Relief", "Cable",
    "Connector Strain Relief", "Connector Housing", "Connector Housing Label",
    "Connector Knob", "Connector Housing Frame"
]

# Options for Repair frame
repair_options = [
    "Lens", "Lens Gap", "Cap", "Array", "Lens Gap", "Shaft Housing Halves Splits", "Housing Strain Relief",
    "Cable Jacket", "Connector Strain Relief", "Leak", "3D/4D", "Electrical"
]

# Options for Cosmetic frame
cosmetic_options = [
    "Shaft Housing", "Housing Strain Relief", "Connector Strain Relief", "Connector Housing", "Cable"
]

# Function to add checkboxes to the each frame
def add_checkboxes(checkbox_vars, options_array):
    for idx, option in enumerate(options_array):
        var = tk.BooleanVar()
        checkbox_vars[labels[i]].append(var)
        checkbox = tk.Checkbutton(checkbox_frame, text=option, bg=colors[i], variable=var)
        checkbox.grid(row=idx // 4, column=idx % 4, padx=5, pady=5, sticky="w")

# Create and pack three frames, each with a label and checkboxes
for i in range(4):
    frame = tk.Frame(root, bg=colors[i], pady=10, padx=10)
    frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    label = tk.Label(frame, text=labels[i], bg=colors[i], font=("Arial", 14))
    label.pack(side=tk.TOP, anchor="center", pady=5)

    # Add a container for checkboxes
    checkbox_frame = tk.Frame(frame, bg=colors[i])
    checkbox_frame.pack(expand=True, anchor="center")

    # Add checkboxes specific to each frame
    if labels[i] == "Replacement":
        add_checkboxes(checkbox_vars, replacement_options)
    elif labels[i] == "Repair":
        add_checkboxes(checkbox_vars, repair_options)
    elif labels[i] == "Cosmetic":
        add_checkboxes(checkbox_vars, cosmetic_options)
    else:
        add_checkboxes(checkbox_vars, notes_options)
        

# Function to display selected checkboxes
def display_selected():
    selected = []
    for category, vars_list in checkbox_vars.items():
        selected_options = []
        for i, var in enumerate(vars_list):
            if var.get():
                if category == "Replacement":
                    selected_options.append(f"{category}: {replacement_options[i]}")
                elif category == "Repair":
                    selected_options.append(f"{category}: {repair_options[i]}")
                elif category == "Cosmetic":
                    selected_options.append(f"{category}: {cosmetic_options[i]}")
                else:
                    selected_options.append(f"{category}: {notes_options[i]}")
        selected.extend(selected_options)
    text_box.delete(1.0, tk.END)
    for index in range(len(selected)):
        selected[index] = f"{index+1}. {selected[index]}"
    text_box.insert(tk.END, "\n".join(selected))

# Function to copy text to clipboard and clear the text box
def copy_to_clipboard():
    root.clipboard_clear()  # Optional.
    root.clipboard_append(text_box.get('1.0', tk.END).rstrip())
    text_box.delete('1.0','end')

# Function to uncheck all checkboxes
def uncheck_all():
    for vars_list in checkbox_vars.values():
        for var in vars_list:
            var.set(False)

# Add a text box at the bottom of the frames
text_box = tk.Text(root, height=5, width=80)
text_box.pack(pady=10, padx=10)

# Add a frame for buttons
button_frame = tk.Frame(root)
button_frame.pack(anchor="center", pady=10)

# Add a "Peak" button to display selected checkboxes
peak_button = tk.Button(button_frame, text="Peak", command=display_selected)
peak_button.pack(side=tk.LEFT, padx=10)

# Add a "Copy" button to copy text and clear the text box
copy_button = tk.Button(button_frame, text="Copy", command=copy_to_clipboard)
copy_button.pack(side=tk.LEFT, padx=10)

# Add an "Uncheck" button to uncheck all checkboxes
uncheck_button = tk.Button(button_frame, text="Uncheck", command=uncheck_all)
uncheck_button.pack(side=tk.LEFT, padx=10)

# Add a "Quit" button to close the application
quit_button = tk.Button(button_frame, text="Quit", command=root.quit)
quit_button.pack(side=tk.LEFT, padx=10)

# Start the main loop
root.mainloop()
