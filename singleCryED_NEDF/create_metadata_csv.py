"""
Module for creating an enhanced csv file that calculates 3D EM quality
"""

import pandas as pd
import os

input_file = "metadata.csv"
output_file = "enhanced_metadata.csv"

df = pd.read_csv(input_file)

def classify_diff_limit(x):
    """
    Clasifies image basesd on diff image
    
    Parameters
    ----------
        x : int
            The number of associated with the diff image of the tiff file
    Returns
    -------
        String
            The word of if the image is a good bad or complex
    """
    if pd.isna(x):
        return None
    if x < 1:
        return "good"
    elif x < 2:
        return "complex"
    else:
        return "bad"

def classify_indexation(x):
    """
    Clasifies image basesd on diff image

    Parameters
    ----------
        x : int
            The number of associated with the diff image of the tiff file
    Returns
    -------
        String
            The word of if the image is a good bad or complex
    """

    if pd.isna(x):
        return None
    if x > 90:
        return "good"
    elif x >= 50:
        return "complex"
    else:
        return "bad"

diff_quality = df["diff_limit"].apply(classify_diff_limit)
index_quality = df["indexation"].apply(classify_indexation)

priority = {"good": 0, "complex": 1, "bad": 2}

def combine_quality(dq, iq):
    """
    Compears the clasification based on indexation and diff_limit 
    and makes a desition on quality based on the worst data

    Parameters
    ----------
        dq : dict
            Dictonary that has the clasification based on diff_limit by name and numerical code ({"good": 0, "complex": 1, "bad": 2})
        iq : dict
            Dictonary that has the clasification based on indexation by name and numerical code ({"good": 0, "complex": 1, "bad": 2})

    Returns
    -------
        dict
            Dictonary that has the clasification by name and numerical code ({"good": 0, "complex": 1, "bad": 2})
    """
    if dq is None:
        return iq
    if iq is None:
        return dq
    return dq if priority[dq] >= priority[iq] else iq

df["3D EM quality"] = [
    combine_quality(dq, iq)
    for dq, iq in zip(diff_quality, index_quality)
]

def clean_and_build_path(row, filename):
    """
    Standardises and builds the relitive file paths of the tiff files
    
    Parameters
    ----------
        row : String
            The row of the csv file being standardised
        filename : String
            The name of the file being created

    Returns
    -------
        String
            The relitive file path of the tiff file.
    """
    if pd.isna(filename):
        return filename

    # normalize slashes
    filename = filename.replace("\\", "/")

    # keep only the file name
    filename = os.path.basename(filename)

    folder = f"./{row['grid_name']}_{row['experiment_name']}"

    return f"{folder}/{filename}"

for col in [
    "diff_img_tiff_filename",
    "grain_img_tiff_filename",
    "frames_tiff_filenames"
]:
    df[col] = df.apply(lambda row: clean_and_build_path(row, row[col]), axis=1)


df.to_csv(output_file, index=False)

print("Clean CSV created with consistent paths and 3D EM quality.")
