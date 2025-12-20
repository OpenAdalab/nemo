#!/usr/bin/env python3
import os
import numpy as np
import pandas as pd
from pathlib import Path
import nibabel as nb
import utils
from config import config

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

def compute_tsnr(nifti_file, mask_file=None):
    """
    Compute temporal signal-to-noise ratio (tSNR) for a given NIfTI file.

    Parameters
    ----------
    
    nifti_file: Path
        Path to the NIfTI file.
        
    mask_file: Path, optional
        Path to a mask NIfTI file to apply before computing tSNR.
    """
    img = nb.load(nifti_file)
    data = img.get_fdata()

    if mask_file:
        mask = nb.load(mask_file).get_fdata().astype(bool)
        data = data[mask]

    mean_img = np.mean(data, axis=-1)
    std_img = np.std(data, axis=-1)
    tsnr = np.nanmean(mean_img / std_img)
    return float(tsnr)

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

    rows = []
    try:
        # Extract status from log
        finished_status, runtime = utils.read_log(config, subject, session, runtype="xcpd")
        dir_count = utils.count_dirs(f"{DERIVATIVES_DIR}/xcpd/{subject}/{session}")
        file_count = utils.count_files(f"{DERIVATIVES_DIR}/xcpd/{subject}/{session}")

        # Load XCP-D QC file
        qc_files = list(subject.glob("**/*_qc.csv"))
        if not qc_files:
            raise FileNotFoundError("No xcp-d QC file found.")

        qc_df = pd.read_csv(qc_files[0])

        # Basic metrics
        mean_fd = qc_df["mean_fd"].iloc[0]
        censor_pct = qc_df["fd_perc"].iloc[0]
        n_retained = qc_df["n_volumes_retained"].iloc[0]
        dvars = qc_df["dvars_mean"].iloc[0]

        # Denoised BOLD
        bold_files = list(subject.glob("**/*desc-denoised_bold.nii.gz"))
        tsnr = None
        if bold_files:
            # Compute tSNR on the first denoised BOLD file found
            tsnr = compute_tsnr(bold_files[0])

        # Functional connectivity sanity
        fc_files = list(subject.glob("**/*connectivity*.tsv"))
        fc_ok = True
        for f in fc_files:
            mat = pd.read_csv(f, sep="\t", header=None).values
            if np.isnan(mat).any() or not np.allclose(mat, mat.T):
                fc_ok = False

        # PASS / FAIL logic
        # If any of the criteria are not met, mark as FAIL
        fail_reasons = []
        if n_retained < MIN_RETAINED_VOLS:
            fail_reasons.append("Too few volumes")
        if censor_pct > MAX_CENSOR_PCT:
            fail_reasons.append("Excessive censoring")
        if mean_fd > MAX_MEAN_FD:
            fail_reasons.append("High motion")
        if not fc_ok:
            fail_reasons.append("Invalid Functional Connectivity matrix")

        status = "FAIL" if fail_reasons else "CORRECT"

        row = dict(
            subject = subject,
            session = session,
            Finished_without_error = finished_status,
            Processing_time_hours = runtime,
            Number_of_folders_generated = dir_count,
            Number_of_files_generated = file_count,
            mean_fd = mean_fd,
            censor_pct = censor_pct,
            n_volumes_retained = n_retained,
            dvars_mean = dvars,
            tsnr = tsnr,
            fc_ok = fc_ok,
            status = status,
            fail_reasons = fail_reasons,
        )
        rows.append(row)

    except Exception as e:
        print(f"⚠️ Skipping {subject} {session}: {e}")
    
    # Save outputs
    qc = pd.DataFrame(rows)
    path_to_qc = f"{DERIVATIVES_DIR}/qc/xcpd/qc_{subject}_{session}.csv"
    qc.to_csv(path_to_qc, index=False)

    print(f"QC saved in {path_to_qc}\n")
    print(f"XCP-D Quality Check terminated successfully.")
# ------------------------------
