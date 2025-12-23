import os
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
import utils


def is_already_processed(config, subject, session):
    """
    Check if subject_session is already processed successfully.
    Note: Even if QSIprep put files in cache, some steps are recomputed which require several hours of ressources.

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

    # Check if QSIprep already processed without error
    DERIVATIVES_DIR = config["common"]["derivatives"]
    stdout_dir = f"{DERIVATIVES_DIR}/qsiprep/stdout"
    if not os.path.exists(stdout_dir):
        return False

    prefix = f"qsiprep_{subject}_{session}"
    stdout_files = [f for f in os.listdir(stdout_dir) if (f.startswith(prefix) and f.endswith('.out'))]
    if not stdout_files:
        return False

    for file in stdout_files:
        file_path = os.path.join(stdout_dir, file)
        with open(file_path, 'r') as f:
            if 'QSIPrep finished successfully!' in f.read():
                print(f"[QSIPREP] Skip already processed subject {subject}_{session}")
                return True

    return False


def generate_slurm_script(config, subject, session, path_to_script, job_ids=None):
    """
    Generate the SLURM script for QSIprep processing.

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
    qsiprep = config["qsiprep"]
    BIDS_DIR = common["input_dir"]
    DERIVATIVES_DIR = common["derivatives"]

    if job_ids is None:
        job_ids = []

    header = (
        f'#!/bin/bash\n'
        f'#SBATCH -J qsiprep_{subject}_{session}\n'
        f'#SBATCH -p {qsiprep["partition"]}\n'
        f'#SBATCH --gpus-per-node={qsiprep["gpu_per_node"]}\n'
        f'#SBATCH --nodes=1\n'
        f'#SBATCH --mem={qsiprep["requested_mem"]}\n'
        f'#SBATCH -t {qsiprep["requested_time"]}\n'
        f'#SBATCH -e {DERIVATIVES_DIR}/qsiprep/stdout/%x_job-%j.err\n'
        f'#SBATCH -o {DERIVATIVES_DIR}/qsiprep/stdout/%x_job-%j.out\n'
    )

    if job_ids:
        header += (
            f'#SBATCH --dependency=afterok:{":".join(job_ids)}\n'
        )

    if common.get("email"):
        header += (
            f'#SBATCH --mail-type=BEGIN,END\n'
            f'#SBATCH --mail-user={common["email"]}\n'
        )

    if common.get("account"):
        header += f'#SBATCH --account={common["account"]}\n'

    module_export = (
        f'\nmodule purge\n'
        f'module load userspace/all\n'
        f'module load singularity\n'
    )

    # Note: Temporary binding to a local FreeSurfer version is included
    # todo: Once the PR#19 Update FreeSurfer is accepted and new container version is built,
    #  remove bound to local freesurfer 7.4.1 (-B) and env variable (--env)
    singularity_command = (
        f'\napptainer run \\\n'
        f'    --nv --cleanenv --writable-tmpfs \\\n'
        f'    -B {BIDS_DIR}:/data:ro \\\n'
        f'    -B {DERIVATIVES_DIR}/qsiprep:/out \\\n'
        f'    -B {common["freesurfer_license"]}:/license \\\n'
        f'    -B {qsiprep["config_eddy"]}:/config/eddy_params.json \\\n'
        f'    -B {qsiprep["qsiprep_config"]}:/config/qsiprep_config.toml \\\n'
        f'    -B /scratch/lhashimoto/freesurfer-7.4.1/usr/local/freesurfer:/opt/freesurfer:ro \\\n'
        f'    --env FREESURFER_HOME=/opt/freesurfer \\\n'
        f'    {qsiprep["qsiprep_container"]} /data /out/outputs participant \\\n'
        f'    --participant-label {subject} --session-id {session} \\\n'
        f'    --skip-bids-validation -v -w /out/work \\\n'
        f'    --bids-database-dir /out/work/bids_db_dir \\\n'
        f'    --fs-license-file /opt/freesurfer/license.txt \\\n'
        f'    --eddy-config /config/eddy_params.json \\\n'
        f'    --config-file /config/qsiprep_config.toml \\\n'
        f'    --output-resolution {qsiprep["output_resolution"]}\n'
    )

    # Add permissions for shared ownership of the output directory
    ownership_sharing = f'\nchmod -Rf 771 {DERIVATIVES_DIR}/qsiprep\n'
    # Write the complete SLURM script to the specified file
    with open(path_to_script, 'w') as f:
        f.write(header + module_export + singularity_command + ownership_sharing)


def run_qsiprep(config, subject, session, job_ids=None):
    """
    Run the QSIprep for a given subject and session.

    Parameters
    ----------
    job_ids : list, optional
        List of SLURM job IDs to set as dependencies (default is None).
    subject : str
        Subject identifier.
    session : str
        Session identifier.

    Returns
    -------
    str or None
        SLURM job ID if the job is submitted successfully, None otherwise.
    """

    # QSIprep manages already processed subjects.
    # No need to remove existing folder or skip subjects.
    # Required files are checked inside the process.

    DERIVATIVES_DIR = config["common"]["derivatives"]
    qsiprep = config["qsiprep"]

    if is_already_processed(config, subject, session) and qsiprep["skip_processed"]:
        return None

    # Create output (derivatives) directories
    os.makedirs(f"{DERIVATIVES_DIR}/qsiprep", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/qsiprep/stdout", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/qsiprep/scripts", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/qsiprep/outputs", exist_ok=True)

    path_to_script = f"{DERIVATIVES_DIR}/qsiprep/scripts/{subject}_{session}_qsiprep.slurm"
    generate_slurm_script(config, subject, session, path_to_script, job_ids)

    cmd = f"sbatch {path_to_script}"
    job_id = utils.submit_job(cmd)
    return job_id
