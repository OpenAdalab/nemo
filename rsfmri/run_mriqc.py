#!/usr/bin/env python3
import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import utils


# --------------------------------------------
# HELPERS
# --------------------------------------------
def is_already_processed(config, subject, session, data_type="raw"):
    """
    Check if subject_session is already processed successfully.

    Parameters
    ----------
    subject : str
        Subject identifier (e.g., "sub-01").
    session : str
        Session identifier (e.g., "ses-01").
    data_type : str
        Type of data to process (possible choices: "raw", "fmriprep", "xcpd", "qsirecon" or "qsiprep").

    Returns
    -------
    bool
        True if already processed, False otherwise.
    """

    # Check if mriqc already processed without error
    DERIVATIVES_DIR = config["common"]["derivatives"]
    stdout_dir = f"{DERIVATIVES_DIR}/mriqc_{data_type}/stdout"
    if not os.path.exists(stdout_dir):
        return False

    prefix = f"mriqc_{subject}_{session}"
    stdout_files = [f for f in os.listdir(stdout_dir) if (f.startswith(prefix) and f.endswith('.out'))]
    if not stdout_files:
        return False

    for file in stdout_files:
        file_path = os.path.join(stdout_dir, file)
        with open(file_path, 'r') as f:
            if 'MRIQC completed' in f.read():
                print(f"[MRIQC] Skip already processed subject {subject}_{session}")
                return True

    return False


def derivatives_datatype_exists(config, subject, session, data_type="raw"):
    """
    Check if derivatives data type directory exists for a given subject and session.

    Parameters
    ----------
    subject : str
        Subject identifier (e.g., "sub-01").
    session : str
        Session identifier (e.g., "ses-01").
    data_type : str
        Type of data to process (possible choices: "raw", "fmriprep", "xcpd", "qsirecon" or "qsiprep").

    Returns
    -------
    bool
        True if derivatives data type directory exists, False otherwise.
    """
    DERIVATIVES_DIR = config["common"]["derivatives"]
    deriv_dir = f"{DERIVATIVES_DIR}/{data_type}/outputs/{subject}/{session}"
    stdout_dir = f"{DERIVATIVES_DIR}/{data_type}/stdout"
    # Check if derivatives data type directory exists
    if not os.path.exists(deriv_dir):
        print(f"[MRIQC] Derivatives directory {deriv_dir} does not exist. MRIQC cannot proceed.")
        return False
    else:
        prefix = f"{data_type}_{subject}_{session}"
        stdout_files = [f for f in os.listdir(stdout_dir) if (f.startswith(prefix) and f.endswith('.out'))]
        if not stdout_files:
            print(f"[MRIQC] Could not read standard outputs from {data_type}, MRIQC cannot proceed.")
            return False

        for file in stdout_files:
            file_path = os.path.join(stdout_dir, file)
            with open(file_path, 'r') as f:
                if f'{data_type} completed' or 'successful' in f.read():
                    print(f"[MRIQC] Skip already processed subject {subject}_{session}")
                    return True
                else:
                    return False
    return


# ------------------------
# Create SLURM job script for MRIQC
# ------------------------
def generate_slurm_script(config, subject, session, path_to_script, data_type="raw", job_ids=None):
    """Generate the SLURM job script.
    Parameters
    ----------
   
    subject : str
        Subject identifier.
    session : str
        Session identifier.
    data_type : str
        Type of data to process (e.g., "raw" or "fmriprep" or "qsiprep").
    job_ids : list, optional
        List of SLURM job IDs to set as dependencies (default is None).
    """

    common = config["common"]
    mriqc = config["mriqc"]
    BIDS_DIR = common["input_dir"]
    DERIVATIVES_DIR = common["derivatives"]

    header = (
        f'#!/bin/bash\n'
        f'#SBATCH --job-name=mriqc_{data_type}_{subject}_{session}\n'
        f'#SBATCH --output={DERIVATIVES_DIR}/qc/{data_type}/stdout/mriqc_{data_type}_{subject}_{session}_%j.out\n'
        f'#SBATCH --error={DERIVATIVES_DIR}/qc/{data_type}/stdout/mriqc_{data_type}_{subject}_{session}_%j.err\n'
        f'#SBATCH --mem={mriqc["requested_mem"]}\n'
        f'#SBATCH --time={mriqc["requested_time"]}\n'
        f'#SBATCH --partition={mriqc["partition"]}\n'
    )

    if job_ids:
        header += f'#SBATCH --dependency=afterok:{":".join(job_ids)}\n'

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
        f'\n# Check that {data_type} finished without error\n'
        f'deriv_data_type_dir="{DERIVATIVES_DIR}/{data_type}/outputs/{subject}/{session}" \n'
        f'if [ ! -d "$deriv_data_type_dir" ]; then\n'
        f'    exit 1\n'
        f'fi\n'

        f'stdout_dir="{DERIVATIVES_DIR}/{data_type}/stdout"\n'
        f'prefix="{data_type}_{subject}_{session}"\n'
        f'if [{data_type} == "fmriprep"]; then\n'
        f'    success_string="fMRIPrep finished successfully"\n'
        f'elif [{data_type} == "xcpd"]; then\n'
        f'    success_string="XCP-D finished successfully"\n'
        f'elif [{data_type} == "qsiprep"]; then\n'
        f'    success_string="QSIPrep finished successfully"\n'
        f'elif [{data_type} == "qsirecon"]; then\n'
        f'    success_string="QSIRecon finished successfully"\n'
        f'fi\n'
        f'found_success=false\n'
        f'for file in $(ls $prefix*.out 2>/dev/null); do\n'
        f'    if grep -q "$success_string" $file; then\n'
        f'        found_success=true\n'
        f'        break\n'
        f'    fi\n'
        f'done\n'
        f'if [ "$found_success" = false ]; then\n'
        f'    echo "[MRIQC] {data_type} did not terminate for {subject} {session}. Please run {data_type} command before."\n '
        f'    exit 1\n'
        f'fi\n'

    )

    # Define the Singularity command for running MRIQC
    # Note: Unlike fmriprep, no config file is used here, the option doesn't exist for mriqc
    if data_type == "raw":
        MRIQC_INPUT = BIDS_DIR
    else:
        MRIQC_INPUT = f"{DERIVATIVES_DIR}/{data_type}/outputs"

    singularity_cmd = (
        f'\napptainer run \\\n'
        f'    --cleanenv \\\n'
        f'    -B {MRIQC_INPUT}:/data:ro \\\n'
        f'    -B {DERIVATIVES_DIR}/qc/{data_type}/outputs:/out \\\n'
        f'    -B {mriqc["bids_filter_dir"]}:/bids_filter_dir \\\n'
        f'    {mriqc["mriqc_container"]} /data /out participant \\\n'
        f'    --participant_label {subject} \\\n'
        f'    --session-id {session} \\\n'
        f'    --bids-filter-file /bids_filter_dir/bids_filter_{session}.json \\\n'
        f'    --mem {mriqc["requested_mem"]} \\\n'
        f'    -w /out/work \\\n'
        f'    --fd_thres 0.5 \\\n'
        f'    --verbose-reports \\\n'
        f'    --verbose \\\n'
        f'    --no-sub --notrack\n'
    )

    save_work = (
        f'\necho "Cleaning up temporary work directory..."\n'
        f'\nchmod -Rf 771 {DERIVATIVES_DIR}/mriqc_{data_type}\n'
        # f'\ncp -r $TMP_WORK_DIR/* {DERIVATIVES_DIR}/mriqc_{data_type}/work\n'
        f'echo "Finished MRIQC for subject: {subject}, session: {session}"\n'
    )

    # Write the complete SLURM script to the specified file
    if data_type == "raw":
        with open(path_to_script, 'w') as f:
            f.write(header + module_export + singularity_cmd + save_work)
    else:
        with open(path_to_script, 'w') as f:
            f.write(header + module_export + prereq_check + singularity_cmd + save_work)


# ------------------------------
# MAIN JOB SUBMISSION LOGIC
# ------------------------------
def run_mriqc(config, subject, session, data_type="raw", job_ids=None):
    """
    Run the MRIQC for a given subject and session.
    Parameters
    ----------
    subject : str
        Subject identifier.
    session : str
        Session identifier.
    data_type : str
        Type of data to process (possible choices: "raw", "fmriprep", "xcpd", "qsirecon" or "qsiprep").
    job_ids : list, optional
        List of SLURM job IDs to set as dependencies (default is None).
    """

    if data_type not in ["raw", "fmriprep", "xcpd", "qsiprep", "qsirecon"]:
        print(f"Invalid data_type: {data_type}. Must be 'raw', 'fmriprep', or 'qsiprep'.")
        return None

    DERIVATIVES_DIR = config["common"]["derivatives"]
    mriqc = config["mriqc"]

    if is_already_processed(config, subject, session, data_type) and mriqc["skip_processed"]:
        return None

    # Create output (derivatives) directories
    os.makedirs(f"{DERIVATIVES_DIR}/qc/{data_type}", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/qc/{data_type}/outputs", exist_ok=True) # todo: change outputs to mriqc ?
    os.makedirs(f"{DERIVATIVES_DIR}/qc/{data_type}/stdout", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/qc/{data_type}/scripts", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/qc/{data_type}/work", exist_ok=True)

    # Add dependency if this is not the first job in the chain
    path_to_script = f"{DERIVATIVES_DIR}/qc/{data_type}/scripts/{subject}_{session}_mriqc.slurm"
    generate_slurm_script(config, subject, session, path_to_script, data_type=data_type, job_ids=job_ids)

    cmd = f"sbatch {path_to_script}"
    job_id = utils.submit_job(cmd)
    return job_id
