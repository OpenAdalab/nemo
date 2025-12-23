#!/usr/bin/env python3
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
    Note: Even if FMRIprep put files in cache, some steps are recomputed which require several hours of ressources.

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
    # todo : separer is_already_processed de check_prerequisites
    # Check required files
    BIDS_DIR = config["common"]["input_dir"]
    if not utils.has_anat(BIDS_DIR, subject):
        print(f"[FMRIPREP] ERROR - No anatomical data found for {subject} {session}.")
        return False
    
    if not utils.has_func_fmap(BIDS_DIR, subject):
        print(f"[FMRIPREP] ERROR - No functional data found for {subject} {session}.")
        return False

    # Check if fmriprep already processed without error
    DERIVATIVES_DIR = config["common"]["derivatives"]
    stdout_dir = f"{DERIVATIVES_DIR}/fmriprep/stdout"
    if not os.path.exists(stdout_dir):
        return False

    prefix = f"fmriprep_{subject}_{session}"
    stdout_files = [f for f in os.listdir(stdout_dir) if (f.startswith(prefix) and f.endswith('.out'))]
    if not stdout_files:
        return False

    for file in stdout_files:
        file_path = os.path.join(stdout_dir, file)
        with open(file_path, 'r') as f:
            if 'fMRIPrep finished successfully!' in f.read():
                # todo: move to main function with complete if test pour TOUS
                print(f"[FMRIPREP] Skip already processed subject {subject}_{session}")
                return True

    return False

# def is_freesurfer_done(config, subject, session):
#     """
#     Check that FreeSurfer recon-all finished successfully.

#     Parameters
#     ----------
#     subject : str
#         Subject identifier (e.g., "sub-01").
#     session : str
#         Session identifier (e.g., "ses-01").

#     Returns
#     -------
#     bool
#         True if FreeSurfer is done, False otherwise.
#     """

#     # Check that FreeSurfer finished without error
#     DERIVATIVES_DIR = config["common"]["derivatives"]
#     if not os.path.exists(f"{DERIVATIVES_DIR}/freesurfer/{subject}_{session}"):
#         print(f"[FMRIPREP] No FreeSurfer outputs found - Running full fmriprep.")
#         return False

#     else:
#         logs = f"{DERIVATIVES_DIR}/freesurfer/{subject}_{session}/scripts/recon-all-status.log"
#         with open(logs, 'r') as f:
#             lines = f.readlines()
#         for l in lines:
#             if not 'finished without error' in l:
#                 print(f"[FMRIPREP] FreeSurfer did not terminate.")
#                 return False
#             else:
#                 return True


# ------------------------
# Create SLURM job scripts 
# ------------------------
def generate_slurm_fmriprep_script(config, subject, session, path_to_script, fs_done=False, job_ids=None):
    """Generate a SLURM job script for fMRIPrep processing.
    This function creates a SLURM submission script that runs fMRIPrep via Singularity/Apptainer
    container. The script includes setup for temporary directories, FreeSurfer dependency checking,
    module loading, and cleanup procedures.
    config : dict
        Configuration dictionary containing 'common' and 'fmriprep' sections with settings for
        input/output directories, container paths, SLURM parameters, and resource requirements.
        Subject identifier (e.g., 'sub-001').
        Session identifier (e.g., 'ses-01').
        File path where the generated SLURM script will be saved.
    fs_done : bool, optional
        Deprecated parameter indicating FreeSurfer completion status (default is False).
        Currently unused but retained for backward compatibility.
    job_ids : list of str, optional
        List of SLURM job IDs to set as dependencies using 'afterok' constraint.
        If provided, this job will wait for those jobs to complete successfully (default is None).
    Returns
    -------
    None
        Writes the SLURM script directly to the file specified by path_to_script and prints
        a confirmation message.
    Raises
    ------
    IOError
        If the script cannot be written to path_to_script.
    Notes
    -----
    The generated script performs the following steps:
    - Loads required modules (Singularity/Apptainer)
    - Checks FreeSurfer preprocessing completion before starting fMRIPrep
    - Sets up a temporary work directory (using SLURM_TMPDIR or TMPDIR)
    - Runs fMRIPrep container with specified output spaces and configurations
    - Handles output directory permissions and work file consolidation
    """

    common = config["common"]
    fmriprep = config["fmriprep"]
    DERIVATIVES_DIR = common["derivatives"]

    header = (
        f'#!/bin/bash\n'
        f'#SBATCH --job-name=fmriprep_{subject}_{session}\n'
        f'#SBATCH --output={common["derivatives"]}/fmriprep/stdout/fmriprep_{subject}_{session}_%j.out\n'
        f'#SBATCH --error={common["derivatives"]}/fmriprep/stdout/fmriprep_{subject}_{session}_%j.err\n'
        f'#SBATCH --mem={fmriprep["requested_mem"]}\n'
        f'#SBATCH --time={fmriprep["requested_time"]}\n'
        f'#SBATCH --partition={fmriprep["partition"]}\n'
    )

    if job_ids:
        header += f'#SBATCH --dependency=afterok:{":".join(job_ids)}\n'

    if common.get("email"):
        header += (
            f'#SBATCH --mail-type={common["email_frequency"]}\n'
            f'#SBATCH --mail-user={common["email"]}\n'
        )

    module_export = (
        f'\nmodule purge\n'
        f'module load userspace/all\n'
        f'module load singularity\n'

        f'echo "------ Running {fmriprep["fmriprep_container"]} for subject: {subject}, session: {session} --------"\n'
    )
    
    if job_ids:
        if isinstance(job_ids, str):
            dependency = [job_ids]
        else:
            dependency = [jid for jid in job_ids if jid]
        header += (
            f'#SBATCH --dependency=afterok:{":".join(dependency)}\n'
        )
    

    tmp_dir_setup = (
        f'\nhostname\n'
        f'# Choose writable scratch directory\n'
        f'if [ -n "$SLURM_TMPDIR" ]; then\n'
        f'    TMP_WORK_DIR="$SLURM_TMPDIR"\n'
        f'elif [ -n "$TMPDIR" ]; then\n'
        f'    TMP_WORK_DIR="$TMPDIR"\n'
        f'else\n'
        f'    TMP_WORK_DIR=$(mktemp -d /tmp/fmriprep_{subject}_{session})\n'
        f'fi\n'
        f'mkdir -p "$TMP_WORK_DIR"\n'
        f'echo "Using TMP_WORK_DIR = $TMP_WORK_DIR"\n'
        f'echo "Using OUT_FMRIPREP_DIR = {common["derivatives"]}/fmriprep"\n'
    )
        
    prereq_check = (

        f'\n# Check that FreeSurfer finished without error\n'
        f'if [ ! -d "{DERIVATIVES_DIR}/freesurfer/outputs/{subject}_{session}" ]; then\n'
        f'    echo "[FMRIPREP] Please run FreeSurfer recon-all command before FMRIPREP."\n'
        f'    exit 1\n'
        f'fi\n'
        f'if ! grep -q "finished without error" {DERIVATIVES_DIR}/freesurfer/outputs/{subject}_{session}/scripts/recon-all.log; then\n'
        f'    echo "[FMRIPREP] FreeSurfer did not terminate for {subject} {session}."\n'
        f'    exit 1\n'
        f'fi\n'
    )

        # Define the Singularity command for running FMRIPrep (skip FreeSurfer)
    singularity_command = (
        f'\napptainer run --cleanenv \\\n'
        f'    -B {common["input_dir"]}:/data:ro \\\n'
        f'    -B {DERIVATIVES_DIR}/freesurfer/outputs:/freesurfer \\\n'
        f'    -B {DERIVATIVES_DIR}/fmriprep:/out \\\n'
        f'    -B {common["freesurfer_license"]}/license.txt:/opt/freesurfer/license.txt \\\n'
        f'    -B {fmriprep["fmriprep_config"]}:/config/fmriprep_config.toml \\\n'
        f'    -B {fmriprep["bids_filter_dir"]}:/bids_filter_dir \\\n'
        f'    {fmriprep["fmriprep_container"]} /data /out/outputs participant \\\n'
        f'    --participant-label {subject} \\\n'
        f'    --session-label {session} \\\n'
        f'    --fs-subjects-dir /freesurfer \\\n'
        f'    --fs-license-file /opt/freesurfer/license.txt \\\n'
        f'    --bids-filter-file /bids_filter_dir/bids_filter_{session}.json \\\n'
        f'    --project-goodvoxels \\\n'
        f'    --cifti-output {fmriprep["cifti_outputs"]} \\\n'
        f'    --mem-mb {fmriprep["requested_mem"]} \\\n'
        f'    --output-spaces fsLR:den-32k T1w fsaverage:den-164k MNI152NLin6Asym:res-native \\\n'
        f'    --skip-bids-validation \\\n'
        f'    --work-dir /out/work \\\n'
        f'    --config-file /config/fmriprep_config.toml \\\n'
        # f'    --fs-no-reconall\n'  # The fs-no-recon-all step will disable further downstream surface level steps,
        # like boundary based registration, which you should want to keep. The volumetric analogs may be quicker,
        # but generally do not perform as well.
    )

    save_work = (
        # f'\necho "Cleaning up temporary work directory..."\n'
        f'\nchmod -Rf 771 {DERIVATIVES_DIR}/fmriprep\n'
        # f'\ncp -r $TMP_WORK_DIR/* {DERIVATIVES_DIR}/fmriprep/work\n'
        f'\nrsync -av {DERIVATIVES_DIR}/fmriprep/outputs/{subject}/anat/ {DERIVATIVES_DIR}/fmriprep/outputs/{subject}/{session}/anat/\n'
        f'\nrm -rf {DERIVATIVES_DIR}/fmriprep/outputs/{subject}/anat\n'
        # f'echo "Finished fMRIPrep for subject: {subject}, session: {session}"\n'
    )

    # Write the complete SLURM script to the specified file
    with open(path_to_script, 'w') as f:
        # f.write(header + module_export + tmp_dir_setup + singularity_command + save_work)
        f.write(header + module_export + prereq_check + singularity_command + save_work)
    # print(f"Created FMRIPREP SLURM job: {path_to_script} for subject {subject}, session {session}")


def run_fmriprep(config, subject, session, job_ids=None):
    """
    Run the FMRIPrep for a given subject and session.
    Parameters
    ----------
    subject : str
        Subject identifier.
    session : str
        Session identifier.
    job_ids : list, optional
        List of job IDs to set as dependencies for this job.

    Returns
    -------
    str or None
        SLURM job ID if the job is submitted successfully, None otherwise.
    """

    DERIVATIVES_DIR = config["common"]["derivatives"]
    fmriprep = config["fmriprep"]

    if is_already_processed(config, subject, session) and fmriprep["skip_processed"]:
        return None

    # Create output (derivatives) directories if they do not exist
    os.makedirs(f"{DERIVATIVES_DIR}/fmriprep", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/fmriprep/outputs", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/fmriprep/work", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/fmriprep/stdout", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/fmriprep/scripts", exist_ok=True)

    path_to_script = f"{DERIVATIVES_DIR}/fmriprep/scripts/{subject}_{session}_fmriprep.slurm"
    generate_slurm_fmriprep_script(config, subject, session, path_to_script, job_ids=job_ids)

    cmd = f"sbatch {path_to_script}"
    job_id = utils.submit_job(cmd)
    return job_id
