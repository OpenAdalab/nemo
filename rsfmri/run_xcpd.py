#!/usr/bin/env python3
"""
Run XCP-D via SLURM job submission
Author: Henitsoa RASOANANDRIANINA
Date: 2025-10-22
Usage:
    python run_xcpd.py

    """
import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import utils


# ------------------------------
# HELPERS
# ------------------------------
def is_already_processed(config, subject, session):
    """
    Check if subject_session is already processed successfully.

    Parameters
    ----------
    config : dict
        Full pipeline configuration.
    subject : str
        Subject identifier (e.g., "sub-01").
    session : str
        Session identifier (e.g., "ses-01").

    Returns
    -------
    bool
        True if already processed, False otherwise.
    """

    # Check if xcpd already processed without error
    DERIVATIVES_DIR = config["common"]["derivatives"]

    output_dir = f"{DERIVATIVES_DIR}/xcpd/outputs/{subject}/{session}"
    if not os.path.exists(output_dir):
        return False

    stdout_dir = f"{DERIVATIVES_DIR}/xcpd/stdout"
    if not os.path.exists(stdout_dir):
        return False

    prefix = f"xcpd_{subject}_{session}"
    stdout_files = [f for f in os.listdir(stdout_dir) if (f.startswith(prefix) and f.endswith('.out'))]
    if not stdout_files:
        return False

    for file in stdout_files:
        file_path = os.path.join(stdout_dir, file)
        with open(file_path, 'r') as f:
            if 'XCP-D finished successfully!' in f.read():
                return True

    return False


# -----------------------
# Generate SLURM job scripts
# -----------------------
def generate_slurm_script(config, subject, session, path_to_script, job_ids=None):
    """
    Generate the SLURM job script.

    Parameters
    ----------
    config : dict
        Full pipeline configuration.
    subject : str
            Subject identifier.
    session : str
            Session identifier.
    path_to_script : str
            Path where the SLURM script will be saved.
    job_ids : list, optional
            List of SLURM job IDs to set as dependencies (default is None).
    """

    common = config["common"]
    xcpd = config["xcpd"]
    DERIVATIVES_DIR = common["derivatives"]

    header = (
        f'#!/bin/bash\n'
        f'#SBATCH --job-name=xcpd_{subject}_{session}\n'
        f'#SBATCH --output={DERIVATIVES_DIR}/xcpd/stdout/xcpd_{subject}_{session}_%j.out\n'
        f'#SBATCH --error={DERIVATIVES_DIR}/xcpd/stdout/xcpd_{subject}_{session}_%j.err\n'
        f'#SBATCH --mem={xcpd["requested_mem"]}gb\n'
        f'#SBATCH --time={xcpd["requested_time"]}\n'
        f'#SBATCH --partition={xcpd["partition"]}\n'
    )

    if job_ids:
        header += (
            f'#SBATCH --dependency=afterok:{":".join(job_ids)}\n'
        )
                    
    if common.get("email"):
        header += (
            f'#SBATCH --mail-type={common["email_frequency"]}\n'
            f'#SBATCH --mail-user={common["email"]}\n'
        )

    if common.get("account"):
        header += f'#SBATCH --account={common["account"]}\n'

    module_export = (
        f'\nmodule purge\n'
        f'module load userspace/all\n'
        f'module load singularity\n'
    )

    prereq_check = (
        f'\n# Check that FMRIPREP outputs exists\n'
        f'if [ ! -d "{DERIVATIVES_DIR}/fmriprep/outputs/{subject}/{session}" ]; then\n'
        f'    echo "[XCP-D] Please run Fmriprep command before XCP-D."\n'
        f'    exit 1\n'
        f'fi\n'
        
        f'\n# Check that FMRIPREP finished without error\n'
        f'prefix="{DERIVATIVES_DIR}/fmriprep/stdout/fmriprep_{subject}_{session}"\n'
        f'found_success=false\n'
        f'for file in $(ls $prefix*.out 2>/dev/null); do\n'
        f'    if grep -q "fMRIPrep finished successfully" $file; then\n'
        f'        found_success=true\n'
        f'        break\n'
        f'    fi\n'
        f'done\n'
        f'if [ "$found_success" = false ]; then\n'
        f'    echo "[XCP-D] fMRIPrep did not terminate for {subject} {session}. Please run fMRIPrep command before XCP-D."\n'
        f'    exit 1\n'
        f'fi\n'
    )
    
    # Define the Singularity command for running FMRIPrep
    singularity_command = (
        f'\napptainer run --cleanenv \\\n'
        f'    -B {DERIVATIVES_DIR}/fmriprep/outputs:/data:ro \\\n'
        f'    -B {DERIVATIVES_DIR}/xcpd:/out \\\n'
        f'    -B {common["freesurfer_license"]}/license.txt:/opt/freesurfer/license.txt \\\n'
        f'    -B {common["bids_filter_dir"]}:/bids_filter_dir \\\n'
        f'    -B {xcpd["xcpd_config"]}:/config/xcpd_config.toml \\\n'
        f'    {xcpd["xcpd_container"]} /data /out/outputs participant \\\n'
        f'      --input-type fmriprep \\\n'
        f'      --participant-label {subject} \\\n'
        f'      --session-id {session} \\\n'
        f'      --fs-license-file /opt/freesurfer/license.txt \\\n'
        f'      --mode linc \\\n'
        f'      --bids-filter-file /bids_filter_dir/bids_filter_{session}.json \\\n'
        f'      --nuisance-regressors 36P \\\n'
        f'      --work-dir /out/work \\\n'
        f'      --config-file /config/xcpd_config.toml \\\n'
    )

    # Add permissions for shared ownership of the output directory
    ownership_sharing = f'\nchmod -Rf 771 {DERIVATIVES_DIR}/xcpd\n'

    # Write the complete SLURM script to the specified file
    with open(path_to_script, 'w') as f:
        f.write(header + module_export + prereq_check + singularity_command + ownership_sharing)


def run_xcpd(config, subject, session, job_ids=None):
    
    """
    Run XCP-D for a given subject and session.

    Parameters
    ----------
    config : dict
        Full pipeline configuration.
    subject : str
        Subject identifier.
    session : str
        Session identifier.
    job_ids : list, optional
        List of SLURM job IDs to set as dependencies (default is None).
    
    Returns
    -------
    str or None
        SLURM job ID if the job is submitted successfully, None otherwise.
    """

    DERIVATIVES_DIR = config["common"]["derivatives"]
    xcpd = config["xcpd"]

    if is_already_processed(config, subject, session) and xcpd["skip_processed"]:
        print(f"[XCP-D] Skip already processed subject {subject}_{session}")
        return None

    # Create output (derivatives) directories
    os.makedirs(f"{DERIVATIVES_DIR}/xcpd", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/xcpd/outputs", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/xcpd/stdout", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/xcpd/scripts", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/xcpd/work", exist_ok=True)

    path_to_script = f"{DERIVATIVES_DIR}/xcpd/scripts/{subject}_{session}_xcpd.slurm"
    generate_slurm_script(config, subject, session, path_to_script, job_ids=job_ids)

    cmd = f"sbatch {path_to_script}"
    job_id = utils.submit_job(cmd)
    return job_id