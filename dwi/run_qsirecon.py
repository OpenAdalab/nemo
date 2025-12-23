import os
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
import utils


# --------------------------------------------
# HELPERS
# --------------------------------------------
def is_already_processed(config, subject, session):
    """
    Check if subject_session is already processed successfully.

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
    # Check if qsirecon already processed without error
    DERIVATIVES_DIR = config["common"]["derivatives"]
    stdout_dir = f"{DERIVATIVES_DIR}/qsirecon/stdout"
    if not os.path.exists(stdout_dir):
        return False

    prefix = f"qsirecon_{subject}_{session}"
    stdout_files = [f for f in os.listdir(stdout_dir) if (f.startswith(prefix) and f.endswith('.out'))]
    if not stdout_files:
        return False

    for file in stdout_files:
        file_path = os.path.join(stdout_dir, file)
        with open(file_path, 'r') as f:
            if 'QSIRecon finished successfully!' in f.read():
                print(f"[QSIRECON] Skip already processed subject {subject}_{session}")
                return True

    return False


def generate_slurm_script(config, subject, session, path_to_script, job_ids=None):
    """
    Generate the SLURM script for QSIrecon processing.

    Parameters
    ----------
    args : Namespace
        Configuration arguments containing parameters for SLURM and QSIrecon.
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
    qsirecon = config["qsirecon"]
    DERIVATIVES_DIR = common["derivatives"]

    header = (
        f'#!/bin/bash\n'
        f'#SBATCH -J qsirecon_{subject}_{session}\n'
        f'#SBATCH -p {qsirecon["partition"]}\n'
        f'#SBATCH --gpus-per-node={qsirecon["gpu_per_node"]}\n'
        f'#SBATCH --nodes=1\n'
        f'#SBATCH --mem={qsirecon["requested_mem"]}\n'
        f'#SBATCH -t {qsirecon["requested_time"]}\n'
        f'#SBATCH -e {DERIVATIVES_DIR}/qsirecon/stdout/%x_job-%j.err\n'
        f'#SBATCH -o {DERIVATIVES_DIR}/qsirecon/stdout/%x_job-%j.out\n'
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

    prereq_check = (
        f'\n# Check that FreeSurfer finished without error\n'
        f'if [ ! -d "{DERIVATIVES_DIR}/freesurfer/outputs/{subject}_{session}" ]; then\n'
        f'    echo "[QSIRECON] Please run FreeSurfer recon-all command before QSIrecon."\n'
        f'    exit 1\n'
        f'fi\n'
        f'if ! grep -q "finished without error" {DERIVATIVES_DIR}/freesurfer/outputs/{subject}_{session}/scripts/recon-all.log; then\n'
        f'    echo "[QSIRECON] FreeSurfer did not terminate for {subject} {session}."\n'
        f'    exit 1\n'
        f'fi\n'
        f'\n# Check that QSIprep finished without error\n'
        f'prefix="{DERIVATIVES_DIR}/qsiprep/stdout/qsiprep_{subject}_{session}"\n'
        f'found_success=false\n'
        f'for file in $(ls $prefix*.out 2>/dev/null); do\n'
        f'    if grep -q "QSIPrep finished successfully" $file; then\n'
        f'        found_success=true\n'
        f'        break\n'
        f'    fi\n'
        f'done\n'
        f'if [ "$found_success" = false ]; then\n'
        f'    echo "[QSIRECON] QSIprep did not terminate for {subject} {session}. Please run QSIprep before QSIrecon.'
        f'QSIrecon."\n'
        f'    exit 1\n'
        f'fi\n'
    )

    singularity_command = (
        f'\napptainer run \\\n'
        f'    --nv --cleanenv --writable-tmpfs \\\n'
        f'    -B {DERIVATIVES_DIR}/qsiprep:/data:ro \\\n'
        f'    -B {DERIVATIVES_DIR}/qsirecon:/out \\\n'
        f'    -B {DERIVATIVES_DIR}/freesurfer/outputs/{subject}_{session}:/freesurfer/{subject} \\\n'  # Mount subject's 
        # folder to address the unrecognized folder name containing _ses-XX. Bug reported and fixed in end-2024 but 
        # apparently still not working in last version qsirecon-1.1.1
        f'    -B {common["freesurfer_license"]}/license.txt:/opt/freesurfer/license.txt \\\n'
        f'    -B {qsirecon["qsirecon_config"]}:/config/qsirecon_config.toml \\\n'
        f'    --env TEMPLATEFLOW_HOME=/opt/templateflow \\\n'  # probably unnecessary since apptainer always binds $HOME
        f'    {qsirecon["qsirecon_container"]} /data /out/outputs participant \\\n'
        f'    --participant-label {subject} --session-id {session} \\\n'
        f'    -v -w /out/work \\\n'
        f'    --fs-license-file /opt/freesurfer/license.txt \\\n'
        f'    --fs-subjects-dir /freesurfer \\\n'
        f'    --atlases {" ".join(qsirecon["atlases"])} \\\n'
        f'    --config-file /config/qsirecon_config.toml\n'
    )
    # f'    --bids-database-dir /out/temp_qsirecon/bids_db_dir\n'

    # Add permissions for shared ownership of the output directory
    ownership_sharing = f'\nchmod -Rf 771 {DERIVATIVES_DIR}/qsirecon\n'

    # Write the complete SLURM script to the specified file
    with open(path_to_script, 'w') as f:
        f.write(header + module_export + prereq_check + singularity_command + ownership_sharing)


def run_qsirecon(config, subject, session, job_ids=None):
    """
    Run the QSIrecon for a given subject and session.

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

    # QSIrecon manages already processed subjects.
    # No need to remove existing folder or skip subjects.
    # Required files are checked inside the process.

    DERIVATIVES_DIR = config["common"]["derivatives"]
    qsirecon = config["qsirecon"]

    if is_already_processed(config, subject, session) and qsirecon["skip_processed"]:
        return None

    # Create output (derivatives) directories
    os.makedirs(f"{DERIVATIVES_DIR}/qsirecon", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/qsirecon/stdout", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/qsirecon/scripts", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/qsirecon/outputs", exist_ok=True)

    path_to_script = f"{DERIVATIVES_DIR}/qsirecon/scripts/{subject}_{session}_qsirecon.slurm"
    generate_slurm_script(config, subject, session, path_to_script, job_ids)

    cmd = f"sbatch {path_to_script}"
    job_id = utils.submit_job(cmd)
    return job_id
