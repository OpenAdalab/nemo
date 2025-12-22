#!/usr/bin/env python3
import os
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
import utils
import toml
import nibabel as nib

# ------------------------------
# CONFIG / THRESHOLDS
# ------------------------------
MIN_RETAINED_VOLS = 100 # Minimum number of volumes to retain after censoring
MAX_CENSOR_PCT = 50.0 # Maximum percentage of censored volumes
MAX_MEAN_FD = 0.5 # Maximum mean framewise displacement

# ------------------------------
# CONFIG / THRESHOLDS
# ------------------------------
MIN_RETAINED_VOLS = 100 # Minimum number of volumes to retain after censoring
MAX_CENSOR_PCT = 50.0 # Maximum percentage of censored volumes
MAX_MEAN_FD = 0.5 # Maximum mean framewise displacement

# ------------------------------
# HELPERS
# ------------------------------
def load_if_exists(path):
    """Load a file if it exists, otherwise return None."""
    return path if path.exists() else None

def compute_tsnr_maps(fmri_4d_nii, filename, mask_nii=None):
    img = nib.load(fmri_4d_nii)
    data = img.get_fdata()

    if data.ndim != 4:
        raise ValueError("Input must be a 4D fMRI image")

    mean_img = np.mean(data, axis=3)
    std_img = np.std(data, axis=3, ddof=1)

    tsnr = np.zeros_like(mean_img)
    valid = std_img > 0
    tsnr[valid] = mean_img[valid] / std_img[valid]

    if mask_nii is not None:
        mask = nib.load(mask_nii).get_fdata().astype(bool)
        tsnr[~mask] = 0

    tsnr_nii = nib.Nifti1Image(tsnr, img.affine, img.header)
    nib.save(tsnr_nii, filename)
    
    return tsnr
    
def summarize_tsnr(tsnr_map, mask_nii=None):
    if mask_nii is None:
        tsnr_value = np.nanmean(tsnr_map)
    else:
        mask = nib.load(mask_nii).get_fdata().astype(bool)
        tsnr_value = np.nanmean(tsnr_map[mask])
    return tsnr_value

# ------------------------------
# MAIN QC FUNCTION
# ------------------------------
def run(config, subject, session):
    """
    Run QC on XCP-D outputs.
    Parameters
    ----------
    config: simpleNamespace
        Configuration object.
    xcpd_dir: Path
        Path to the XCP-D output directory.
    """
    
    DERIVATIVES_DIR = config["common"]["derivatives"]
    out_dir = Path(f"{DERIVATIVES_DIR}/qc/xcpd")
    os.makedirs(out_dir, exist_ok=True)

    xcpd_dir = Path(DERIVATIVES_DIR) / "xcpd/outputs" / subject / session

    rows = []
    try:
        # Extract status from log
        finished_status, runtime = utils.read_log(config, subject, session, runtype="xcpd")
        dir_count = utils.count_dirs(f"{DERIVATIVES_DIR}/xcpd/{subject}/{session}")
        file_count = utils.count_files(f"{DERIVATIVES_DIR}/xcpd/{subject}/{session}")

        # Load XCP-D QC file
        qc_files = list(xcpd_dir.glob("**/*_qc.tsv"))
        if not qc_files:
            raise FileNotFoundError("No xcp-d QC file found.")

        qc_df = pd.read_csv(qc_files[0], sep='\t')

        # Basic metrics
        mean_fd = qc_df["mean_fd"].iloc[0] if "mean_fd" in qc_df.columns else None
        censor_pct = qc_df["fd_perc"].iloc[0] if "fd_perc" in qc_df.columns else None
        n_retained = qc_df["n_volumes_retained"].iloc[0] if "n_volumes_retained" in qc_df.columns else None
        dvars = qc_df["dvars_mean"].iloc[0] if "dvars_mean" in qc_df.columns else None


        # PASS / FAIL logic
        # If any of the criteria are not met, mark as FAIL
        fail_reasons = []
        if n_retained is not None and n_retained < MIN_RETAINED_VOLS:
            fail_reasons.append("Too few volumes")
        if censor_pct is not None and censor_pct > MAX_CENSOR_PCT:
            fail_reasons.append("Excessive censoring")
        if mean_fd is not None and mean_fd > MAX_MEAN_FD:
            fail_reasons.append("High motion")
        
        # Add computed metrics to qc_df
        qc_df['Finished_without_error'] = finished_status
        qc_df['Processing_time_hours'] = runtime
        qc_df['Number_of_folders_generated'] = dir_count
        qc_df['Number_of_files_generated'] = file_count
        qc_df['status'] = finished_status
        qc_df['fail_reasons'] = str(fail_reasons)

        # Save the updated qc_df
        path_to_qc = f"{DERIVATIVES_DIR}/qc/xcpd/qc_{subject}_{session}_updated.csv"
        qc_df.to_csv(path_to_qc, index=False, header=True)

        print(f"QC saved in {path_to_qc}\n")
        print(f"XCP-D Quality Check terminated successfully.")

    except Exception as e:
        print(f" Skipping {subject} {session}: {e}")
# ------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--subject', required=True)
    parser.add_argument('--session', required=True)
    args = parser.parse_args()

    with open(args.config, 'r') as f:
        config = toml.load(f)

    run(config, args.subject, args.session)
