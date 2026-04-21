"""
Module for building GUI that evaluates good, complex and bad thresholds based in diff_limit and indexation
"""
import tkinter as tk
from tkinter import Button, Label, Frame, Text, Scrollbar
from PIL import Image, ImageTk
import pandas as pd
import numpy as np
import os

#This data is for pointing to the relevent files.
#This current set up if for running the program in the "learning set file" with the enhansed metadata.csv file also in it.

CSV_FILE = "metadata.csv"
BASE_PATH = "."
IMAGE_SIZE = (400, 400)

#Loads the CSV file
df = pd.read_csv(CSV_FILE)
current_index = 0
manual_labels = []

def classify_diff_limit(val, d1=1, d2=2):
    """
    Converts a diff_limit value into a label (good, complex, or bad) based on threshold boundaries.

    Parameters
    ----------
    val: int
        value that is being calsified
    d1: int
        The curently adusted value for the "good" classification
    d2: int
        The currently adusted value of the "complex" clasification

    Returns
    -------
    str
        The string value of the clasification
    """
    if val < d1:
        return "good"
    elif val < d2:
        return "complex"
    else:
        return "bad"

def classify_indexation(val, i1=50, i2=90):
    """
    Converts an indexation value into a label (good, complex, or bad) based on threshold boundaries.

    Parameters
    ----------
    val: int
        value that is being calsified
    d1: int
        The curently adusted value for the "good" classification
    d2: int
        The currently adusted value of the "complex" clasification

    Returns
    -------
    str
        The string value of the clasification
    """
    if val > i2:
        return "good"
    elif val >= i1:
        return "complex"
    else:
        return "bad"

def combine_labels(diff_label, index_label):
    """
    Uses a “worst-case” rule to combine the two labels, choosing whichever is worse.

    Parameters
    ----------
    diff_label: str 
        The value given when  evaluating the diff_limit.
    index_lable: str
        The value given when  evaluating the index_lable

    Returns
    -------
    str
        The label that is the worst of the diff_lable and the index_label
    """
    order = {"good": 0, "complex": 1, "bad": 2}
    return max([diff_label, index_label], key=lambda x: order[x])


# Builds GUI
root = tk.Tk()
root.title("3D EM Quality Labeller")

main_frame = Frame(root)
main_frame.pack()

# LEFT: Image
left_frame = Frame(main_frame)
left_frame.pack(side="left", padx=10)

img_label = Label(left_frame)
img_label.pack()

# RIGHT: Box
right_frame = Frame(main_frame)
right_frame.pack(side="right", padx=10)

Label(right_frame, text="Metadata", font=("Arial", 14, "bold")).pack()

text_box = Text(right_frame, width=50, height=25, wrap="word")
text_box.pack(side="left")

scrollbar = Scrollbar(right_frame, command=text_box.yview)
scrollbar.pack(side="right", fill="y")

text_box.config(yscrollcommand=scrollbar.set)

# Bottom info
info_label = Label(root, text="", font=("Arial", 12), justify="left")
info_label.pack()

def load_image():
    """
    Loads the current image and updates the GUI with image, metadata, and computed labels.
    """
    global current_index

    if current_index >= len(df):
        finish()
        return

    row = df.iloc[current_index]

    # Load image
    img_path = os.path.join(BASE_PATH, row["diff_img_tiff_filename"])
    try:
        img = Image.open(img_path)
        img.thumbnail(IMAGE_SIZE)
        img_tk = ImageTk.PhotoImage(img)

        img_label.config(image=img_tk, text="")
        img_label.image = img_tk
    except:
        img_label.config(image="", text=f"Error loading:\n{img_path}")

    # Compute labels
    diff_label = classify_diff_limit(row["diff_limit"])
    index_label = classify_indexation(row["indexation"])
    combined = combine_labels(diff_label, index_label)

    assigned = row["3D EM quality"]

    # Update main info
    info_label.config(
        text=f"""
Index: {current_index}

Assigned: {assigned}
Computed: {combined}
"""
    )

    # Fill metadata box
    text_box.delete("1.0", tk.END)

    excluded_columns = {
    "collection_program",
    "processing_program",
    "frames_collected",
    "frame_conversion_program",
    "diff_img_tiff_filename",
    "grain_img_tiff_filename",
    "frames_tiff_filenames"
    }

    for col in df.columns:
        if col in excluded_columns:
            continue

        value = row[col]
        text_box.insert(tk.END, f"{col}:\n{value}\n\n")


def label_image(label):
    """
    Stores the user's manual classification for the current image.

    Parameters
    ----------
    label: str
        The manual classification selected by the user ("good", "complex", or "bad")
    """
    global current_index

    row = df.iloc[current_index]

    diff_label = classify_diff_limit(row["diff_limit"])
    index_label = classify_indexation(row["indexation"])
    combined = combine_labels(diff_label, index_label)

    manual_labels.append({
        "manual": label,
        "assigned": row["3D EM quality"],
        "computed": combined,
        "diff_limit": row["diff_limit"],
        "indexation": row["indexation"]
    })

    current_index += 1
    load_image()

def find_best_thresholds(results):
    """
    Finds the optimal threshold values for diff_limit and indexation that best match manual labels.

    Parameters
    ----------
    results: pandas.DataFrame
        DataFrame containing manual labels, diff_limit, and indexation values

    Returns
    -------
    tuple
        Tuple containing:
        - best_params: (d1, d2, i1, i2) optimal threshold values
        - best_score: float accuracy score of the best thresholds
    """
    best_score = 0
    best_params = None

    diff_vals = results["diff_limit"].values
    index_vals = results["indexation"].values
    labels = results["manual"].values

    for d1 in np.linspace(min(diff_vals), max(diff_vals), 12):
        for d2 in np.linspace(d1, max(diff_vals), 12):

            for i1 in np.linspace(min(index_vals), max(index_vals), 12):
                for i2 in np.linspace(i1, max(index_vals), 12):

                    preds = []

                    for d, i in zip(diff_vals, index_vals):
                        d_label = classify_diff_limit(d, d1, d2)
                        i_label = classify_indexation(i, i1, i2)
                        combined = combine_labels(d_label, i_label)
                        preds.append(combined)

                    score = np.mean([p == l for p, l in zip(preds, labels)])

                    if score > best_score:
                        best_score = score
                        best_params = (d1, d2, i1, i2)

    return best_params, best_score

def suggest_thresholds():
    """
    It calculates and displays the optimal classification thresholds.
    """
    if len(manual_labels) < 5:
        info_label.config(text="Label at least 5 samples first.")
        return

    results = pd.DataFrame(manual_labels)

    (d1, d2, i1, i2), score = find_best_thresholds(results)

    info_label.config(
        text=f"""
--- SUGGESTED THRESHOLDS ---

diff_limit:
  good < {d1:.2f}
  complex {d1:.2f} – {d2:.2f}
  bad > {d2:.2f}

indexation:
  good > {i2:.2f}
  complex {i1:.2f} – {i2:.2f}
  bad < {i1:.2f}

Accuracy: {score*100:.1f}%
"""
    )

# Builds buttons
btn_frame = Frame(root)
btn_frame.pack(pady=10)

Button(btn_frame, text="Good (1)", bg="green",
       command=lambda: label_image("good")).grid(row=0, column=0)

Button(btn_frame, text="Complex (2)", bg="yellow",
       command=lambda: label_image("complex")).grid(row=0, column=1)

Button(btn_frame, text="Bad (3)", bg="red",
       command=lambda: label_image("bad")).grid(row=0, column=2)

Button(root, text="Suggest Boundaries", bg="blue", fg="white",
       command=suggest_thresholds).pack(pady=10)

# Optional keyboard shortcuts
root.bind("1", lambda e: label_image("good"))
root.bind("2", lambda e: label_image("complex"))
root.bind("3", lambda e: label_image("bad"))

def finish():
    """
    Finishes Program
    """
    root.quit()

# start
load_image()
root.mainloop()
