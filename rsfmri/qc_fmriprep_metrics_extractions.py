#!/usr/bin/env python3

from venv import logger
import numpy as np
import nibabel as nib
import pandas as pd
from pathlib import Path
from sklearn.metrics import mutual_info_score
from nilearn.image import mean_img
import warnings
import os
import toml
import utils
from config import config

warnings.filterwarnings("ignore")
# -----------------------

def load_any_image(path: Path):
    """
    Load an fMRIPrep/XCP-D output image, handling both NIfTI and GIFTI formats.
    
    Parameters
    ----------
    path : Path
        Path to the .nii(.gz) or .gii file.
    
    Returns
    -------
    img : nibabel image object
        Loaded image object.
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    img = nib.load(str(path)) # type: ignore

    if isinstance(img, nib.gifti.gifti.GiftiImage):
        logger.info(f"Detected GIFTI surface file: {path.name}")
    elif isinstance(img, (nib.Nifti1Image, nib.Nifti2Image)): # type: ignore
        logger.info(f"Detected NIfTI volumetric file: {path.name}")
    else:
        raise TypeError(f"Unsupported file type: {type(img)}")

    return img

def voxel_count(mask):
    """
    Extract voxel count from a mask (binary or multiclass).
    
    :param mask: array data
    :return: number of True voxels
    """

    return np.sum(mask)


def dice(a, b):
    """
    Compute dice similarity coefficient between two binary masks.
    
    :param a: array data
    :param b: array data

    :return: Dice similarity coefficient
    """
    a = a.astype(bool)
    b = b.astype(bool)
    inter = np.logical_and(a, b).sum()
    s = a.sum() + b.sum()
    return (2 * inter / s) if s > 0 else np.nan

def mutual_information(img1, img2, bins=64):
    """
    Compute mutual information between two images.
    
    :param img1: array data
    :param img2: array data
    :param bins: number of bins for histogram
    :return: Mutual information score
    """
    i1 = img1.flatten()
    i2 = img2.flatten()

    if len(i1) != len(i2):
        return np.nan

    hgram, _, _ = np.histogram2d(i1, i2, bins=bins)
    return mutual_info_score(None, None, contingency=hgram)

# -----------------------
# Main extraction
# -----------------------
def run(config, subject, session):
    """
    Extract QC metrics from fMRIPrep outputs.

    Parameters
    ----------
    config : dict
        Configuration dictionary.
    fmriprep_dir : Path
        Path to the fMRIPrep derivatives directory. 
    Returns
    -------
    pd.DataFrame
        DataFrame containing QC metrics for each subject and session.
    """

    DERIVATIVES_DIR = config["common"]["derivatives"]
    try:               
                # Extract process status from log files
                finished_status, runtime = utils.read_log(config, subject, session, runtype="fmriprep")
                dir_count = utils.count_dirs(f"{DERIVATIVES_DIR}/fmriprep/{subject}/{session}")
                file_count = utils.count_files(f"{DERIVATIVES_DIR}/fmriprep/{subject}/{session}")

                anat = Path(DERIVATIVES_DIR) / "fmriprep/outputs" / subject / session / "anat"
                func = Path(DERIVATIVES_DIR) / "fmriprep/outputs" / subject / session / "func"

                # Identify required files
                t1w = next(anat.glob("*_desc-preproc_T1w.nii.gz"))
                t1w_mask = next(anat.glob("*_desc-brain_mask.nii.gz"))
                gm = next(anat.glob("*_label-GM_probseg.nii.gz"))
                wm = next(anat.glob("*_label-WM_probseg.nii.gz"))
                csf = next(anat.glob("*_label-CSF_probseg.nii.gz"))

                bold = next(func.glob("*_desc-preproc_bold.nii.gz"))
                bold_mask = next(func.glob("*_desc-brain_mask.nii.gz"))

                # Load data
                t1w_img = load_any_image(t1w)
                t1w_mask_img = load_any_image(t1w_mask)
                bold_img = load_any_image(bold)

                # Compute mean BOLD image
                mean_bold_img = mean_img(bold_img)
                mean_bold = mean_bold_img.get_fdata()
                
                # Load masks for voxel counts
                brain_mask_img = load_any_image(bold_mask)
                brain_mask = brain_mask_img.get_fdata() > 0
                bg_mask = ~brain_mask

                gm_img = load_any_image(gm)
                gm_mask = gm_img.get_fdata() > 0.5
                wm_img = load_any_image(wm)
                wm_mask = wm_img.get_fdata() > 0.5
                csf_img = load_any_image(csf)
                csf_mask = csf_img.get_fdata() > 0.5

                # Compute QC metrics
                t1w_data = t1w_img.get_fdata()
                t1w_mask_data = t1w_mask_img.get_fdata()
                if t1w_data.shape == t1w_mask_data.shape:
                    t1w_brain = t1w_data[t1w_mask_data > 0]
                else:
                    print(f"Shape mismatch for T1w and mask: {t1w_data.shape} vs {t1w_mask_data.shape}, using all T1w data")
                    t1w_brain = t1w_data.flatten()
                
                if mean_bold.shape == brain_mask.shape:
                    bold_brain = mean_bold[brain_mask > 0]
                else:
                    print(f"Shape mismatch for BOLD and mask: {mean_bold.shape} vs {brain_mask.shape}, using all BOLD data")
                    bold_brain = mean_bold.flatten()
                
                row = dict(
                    subject=subject,
                    session=session,
                    Process_Run="fmriprep",
                    Finished_without_error=finished_status,
                    Processing_time_hours=runtime,
                    Number_of_folders_generated=dir_count,
                    Number_of_files_generated=file_count,
                    brain_voxels=voxel_count(brain_mask),
                    gm_voxels=voxel_count(gm_mask),
                    wm_voxels=voxel_count(wm_mask),
                    csf_voxels=voxel_count(csf_mask),
                    MI_T1w_BOLD=mutual_information(t1w_brain, bold_brain),
                )



    except Exception as e:
                print(f"⚠️ Skipping {subject} {session}: {e}")
    print(f"Fmriprep Quality Check terminated successfully for {subject} {session}.")
    
    sub_ses = pd.DataFrame([row])
    # Save outputs to csv file
    path_to_qc = f"{DERIVATIVES_DIR}/qc/fmriprep/qc_{subject}_{session}.csv"
    sub_ses.to_csv(path_to_qc, mode='w', header=True, index=False)
    print(f"QC saved in {path_to_qc}\n")
    
    
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 4:
        raise RuntimeError(
            "Usage: python qc_fmriprep_metrics_extractions.py <config_path> <subject> <session>"
        )

    config_path, subject, session = sys.argv[1:4]
    with open(config_path, "rb") as f:
        config = tomllib.load(f)
    extract_qc_metrics(config, subject, session)
