#!/usr/bin/env python3
import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import utils


# --------------------------------------------
# HELPERS
# --------------------------------------------
def is_already_processed(config, input_dir, data_type="raw"):
    """
    Check if subject_session is already processed successfully.

    Parameters
    ----------
    input_dir : str
        Input directory path.
    data_type : str
        Type of data to process (possible choices: "raw", "fmriprep", "xcp_d", "qsirecon" or "qsiprep").

    Returns
    -------
    bool
        True if already processed, False otherwise.
    """

    DERIVATIVES_DIR = config["common"]["derivatives"]

    # Check if mriqc already processed without error
    # todo : remonter dans le main()
    if data_type not in ["raw", "fmriprep", "xcp_d", "qsiprep", "qsirecon"]:
        raise ValueError(f"Invalid data_type: {data_type}. Must be 'raw', 'fmriprep', or 'qsiprep'.")

    stdout_dir = f"{DERIVATIVES_DIR}/group_mriqc_{data_type}/stdout"
    if not os.path.exists(stdout_dir):
        print(f"[MRIQC] Could not read standard outputs from MRIQC, recomputing ....")
        return False

    else:
        prefix = f"group_mriqc_{data_type}"
        stdout_files = [f for f in os.listdir(stdout_dir) if (f.startswith(prefix) and f.endswith('.out'))]
        if not stdout_files:
            return False

        for file in stdout_files:
            file_path = os.path.join(stdout_dir, file)
            with open(file_path, 'r') as f:
                if 'MRIQC completed' in f.read():
                    print(f"[MRIQC] Skip already processed input directory {input_dir}")
                    return True
                else:
                    return False


# ------------------------
# Create SLURM job scripts 
# ------------------------
def generate_slurm_mriqc_script(config, input_dir, path_to_script, data_type="raw", job_ids=None):
    """Generate the SLURM job script for MRIQC group processing.
    Parameters
    ----------
   
    input_dir : str
        Input directory path.
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
        f'#SBATCH --job-name=group_mriqc_{data_type}\n'
        f'#SBATCH --output={DERIVATIVES_DIR}/group_mriqc_{data_type}/stdout/group_mriqc_{data_type}_%j.out\n'
        f'#SBATCH --error={DERIVATIVES_DIR}/group_mriqc_{data_type}/stdout/group_mriqc_{data_type}_%j.err\n'
        f'#SBATCH --mem={mriqc["requested_mem"]}\n'
        f'#SBATCH --time={mriqc["requested_time"]}\n'
        f'#SBATCH --partition={mriqc["partition"]}\n'
    )

    if job_ids:
        valid_ids = [str(jid) for jid in job_ids if isinstance(jid, str) and jid.strip()]
        if valid_ids:
            header += f'#SBATCH --dependency=afterok:{":".join(valid_ids)}\n'

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

        f'echo "------ Running group level {mriqc["mriqc_container"]} for input directory: {input_dir} --------"\n'
    )

    tmp_dir_setup = (
        f'\nhostname\n'
        f'# Choose writable scratch directory\n'
        f'if [ -n "$SLURM_TMPDIR" ]; then\n'
        f'    TMP_WORK_DIR="$SLURM_TMPDIR"\n'
        f'elif [ -n "$TMPDIR" ]; then\n'
        f'    TMP_WORK_DIR="$TMPDIR"\n'
        f'else\n'
        f'    TMP_WORK_DIR=$(mktemp -d /tmp/group_mriqc_{data_type})\n'
        f'fi\n'

        f'mkdir -p $TMP_WORK_DIR\n'
        f'chmod -Rf 771 $TMP_WORK_DIR\n'
        f'echo "Using TMP_WORK_DIR = $TMP_WORK_DIR"\n'
        f'echo "Using OUT_MRIQC_DIR = {DERIVATIVES_DIR}/group_mriqc_{data_type}"\n'
    )

    # Define the Singularity command for running MRIQC
    # Note: Unlike fmriprep, no config file is used here, the option doesn't exist for mriqc

    singularity_cmd = (
        f'\napptainer run \\\n'
        f'    --cleanenv \\\n'
        f'    -B {input_dir}:/data:ro \\\n'
        f'    -B {DERIVATIVES_DIR}/group_mriqc_{data_type}/outputs:/out \\\n'
        f'    -B {mriqc["bids_filter_dir"]}:/bids_filter_dir \\\n'
        f'    {mriqc["mriqc_container"]} /data /out group \\\n'
        f'    --mem {mriqc["requested_mem"]} \\\n'
        f'    -w $TMP_WORK_DIR \\\n'
        f'    --fd_thres 0.5 \\\n'
        f'    --verbose-reports \\\n'
        f'    --verbose \\\n'
        f'    --no-sub --notrack\n'
    )

    save_work = (
        f'\necho "Cleaning up temporary work directory..."\n'
        f'\nchmod -Rf 771 {DERIVATIVES_DIR}/group_mriqc_{data_type}\n'
        f'\ncp -r $TMP_WORK_DIR/* {DERIVATIVES_DIR}/group_mriqc_{data_type}/work\n'
        f'echo "Finished MRIQC for group input directory: {input_dir}"\n'
    )

    # Write the complete SLURM script to the specified file
    with open(path_to_script, 'w') as f:
        f.write(header + module_export + tmp_dir_setup + singularity_cmd + save_work)
    print(f"Created MRIQC SLURM job: {path_to_script} for group input directory: {input_dir}")


# ------------------------------
# MAIN JOB SUBMISSION LOGIC
# ------------------------------
def run_mriqc_group(config, input_dir, data_type="raw", job_ids=None):
    """
    Run the MRIQC for a given input directory.
    Parameters
    ----------
    input_dir : str
        Input directory containing the data to be processed.
    data_type : str
        Type of data to process (possible choices: "raw", "fmriprep", "xcp_d", "qsirecon" or "qsiprep").
    job_ids : list, optional
        List of SLURM job IDs to set as dependencies (default is None).
    """

    DERIVATIVES_DIR = config["common"]["derivatives"]

    if is_already_processed(config, input_dir):
        return None

    # Create output (derivatives) directories
    os.makedirs(f"{DERIVATIVES_DIR}/group_mriqc_{data_type}", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/group_mriqc_{data_type}/outputs", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/group_mriqc_{data_type}/stdout", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/group_mriqc_{data_type}/scripts", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/group_mriqc_{data_type}/work", exist_ok=True)

    # Add dependency if this is not the first job in the chain
    path_to_script = f"{DERIVATIVES_DIR}/group_mriqc_{data_type}/scripts/group_mriqc_{data_type}.slurm"
    generate_slurm_mriqc_script(config, input_dir, data_type=data_type, path_to_script=path_to_script, job_ids=job_ids)

    cmd = f"sbatch {path_to_script}"
    job_id = utils.submit_job(cmd)
    return job_id
