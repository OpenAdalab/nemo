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
from config import config
# ------------------------------
# HELPERS
# ------------------------------
def is_already_processed(config, subject, session):
    """
    Check if subject_session is already processed successfully.
    if not, also check that prerequisites are met: FMRIprep is done.

    Parameters
    ----------
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
    prefix = f"xcpd_{subject}_{session}"
    stdout_dir = f"{DERIVATIVES_DIR}/xcpd/stdout"
    if os.path.exists(stdout_dir):
        stdout_files = [f for f in os.listdir(stdout_dir) if (f.startswith(prefix) and f.endswith('.out'))]
        for file in stdout_files:
            file_path = os.path.join(stdout_dir, file)
            with open(file_path, 'r') as f:
                if 'XCP-D finished successfully!' in f.read():
                    print(f"[XCP-D] Skip already processed subject {subject}_{session}")
                    return True
                else:    
                    return False

# -----------------------
# Generate SLURM job scripts
# -----------------------
def generate_slurm_xcpd_script(config, subject, session, path_to_script, job_ids=None):
    """Generate the SLURM job script.
    Parameters
    ----------
    
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
        f'#SBATCH --mem={xcpd["requested_mem"]}\n'
        f'#SBATCH --time={xcpd["requested_time"]}\n'
        f'#SBATCH --partition={xcpd["partition"]}\n'
    )

    if job_ids:
        if isinstance(job_ids, str):
            dependency = [job_ids]
        else:
            dependency = [jid for jid in job_ids if jid]
        header += (
            f'#SBATCH --dependency=afterok:{":".join(dependency)}\n'
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

        f'echo "------ Running {xcpd["xcpd_container"]} for subject: {subject}, session: {session} --------"\n'
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
        f'    fi\n'
        f'done\n'
        f'if [ "$found_success" = false ]; then\n'
        f'    echo "[XCP-D] fMRIPrep did not terminate for {subject} {session}. Please run fMRIPrep command before XCP-D."\n'
        f'    exit 1\n'
        f'fi\n'
    )

    tmp_dir_setup = (
        f'\nhostname\n'
        f'# Choose writable scratch directory\n'
        f'if [ -n "$SLURM_TMPDIR" ]; then\n'
        f'    TMP_WORK_DIR="$SLURM_TMPDIR"\n'
        f'elif [ -n "$TMPDIR" ]; then\n'
        f'    TMP_WORK_DIR="$TMPDIR"\n'
        f'else\n'
        f'    TMP_WORK_DIR=$(mktemp -d /tmp/xcpd_{subject}_{session})\n'
        f'fi\n'
        f'mkdir -p "$TMP_WORK_DIR"\n'
        f'echo "Using TMP_WORK_DIR = $TMP_WORK_DIR"\n'
        f'echo "Using OUT_XCPD_DIR = {DERIVATIVES_DIR}/xcpd"\n'
    )
    
    # Define the Singularity command for running FMRIPrep
    singularity_command = (
        f'\napptainer run --cleanenv \\\n'
        f'    -B {DERIVATIVES_DIR}/fmriprep/outputs:/data:ro \\\n'
        f'    -B {DERIVATIVES_DIR}/xcpd/outputs:/out \\\n'
        f'    -B {common["freesurfer_license"]}:/license.txt \\\n'
        f'    -B {xcpd["bids_filter_dir"]}:/bids_filter_dir\\\n'
        f'    -B {xcpd["xcpd_config"]}:/xcpd_config.toml \\\n'
        f'    {xcpd["xcpd_container"]} /data /out participant \\\n'
        f'      --input-type fmriprep \\\n'
        f'      --participant-label {subject} \\\n'
        f'      --session-id {session} \\\n'
        f'      --fs-license-file /license.txt \\\n'
        f'      --mode linc \\\n'
        f'      --bids-filter-file /bids_filter_dir/bids_filter_{session}.json \\\n'
        f'      --nuisance-regressors 36P \\\n'
        f'      --work-dir $TMP_WORK_DIR \\\n'
        f'      --config-file /xcpd_config.toml \\\n'
    )

    save_work = (
        f'\necho "Cleaning up temporary work directory..."\n'
        f'\nchmod -Rf 771 {DERIVATIVES_DIR}/xcpd\n'
        f'\ncp -r $TMP_WORK_DIR/* {DERIVATIVES_DIR}/xcpd/work\n'
        f'echo "Finished XCP-D for subject: {subject}, session: {session}"\n'
    )

    # Write the complete SLURM script to the specified file
    with open(path_to_script, 'w') as f:
        f.write(header + module_export + prereq_check + tmp_dir_setup + singularity_command + save_work)
    print(f"Created xcpd SLURM job: {path_to_script} for subject {subject}, session {session}")


def run_xcpd(config, subject, session, job_ids=None):
    
    """
    Run the XCP-D for a given subject and session.
    Parameters
    ----------
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

    # Create output (derivatives) directories
    os.makedirs(f"{DERIVATIVES_DIR}/xcpd", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/xcpd/outputs", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/xcpd/stdout", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/xcpd/scripts", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/xcpd/work", exist_ok=True)
    
    if is_already_processed(config, subject, session):
        return None
       
    else: 
        path_to_script = f"{DERIVATIVES_DIR}/xcpd/scripts/{subject}_{session}_xcpd.slurm"
        generate_slurm_xcpd_script(config, subject, session, path_to_script, job_ids=job_ids)
                    
        cmd = f"sbatch {path_to_script}"   
        job_id = utils.submit_job(cmd)
        print(f"[xcpd] Submitting job {cmd}\n")
        return job_id