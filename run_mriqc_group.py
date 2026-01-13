#!/usr/bin/env python3
import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import utils


# ------------------------
# Create SLURM job scripts 
# ------------------------
def generate_slurm_script(config, input_dir, path_to_script, data_type="raw", job_ids=None):
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
    DERIVATIVES_DIR = common["derivatives"]

    header = (
        f'#!/bin/bash\n'
        f'#SBATCH --job-name=group_mriqc_{data_type}\n'
        f'#SBATCH --output={DERIVATIVES_DIR}/qc/{data_type}/stdout/group_mriqc_{data_type}_%j.out\n'
        f'#SBATCH --error={DERIVATIVES_DIR}/qc/{data_type}/stdout/group_mriqc_{data_type}_%j.err\n'
        f'#SBATCH --mem={mriqc["requested_mem"]}gb\n'
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

    # Define the Singularity command for running MRIQC
    # Note: Unlike fmriprep, no config file is used here, the option doesn't exist for mriqc
    singularity_cmd = (
        f'\napptainer run \\\n'
        f'    --cleanenv \\\n'
        f'    -B {input_dir}:/data:ro \\\n'
        f'    -B {DERIVATIVES_DIR}/qc/{data_type}:/out \\\n'
        f'    {mriqc["mriqc_container"]} /data /out/outputs group \\\n'
        f'    --mem {mriqc["requested_mem"]} \\\n'
        f'    -w /out/work \\\n'
        f'    --fd_thres 0.5 \\\n'
        f'    --verbose-reports \\\n'
        f'    --verbose \\\n'
        f'    --no-sub --notrack\n'
    )

    save_work = (
        f'\nmv {DERIVATIVES_DIR}/qc/{data_type}/outputs/group* {DERIVATIVES_DIR}/qc/{data_type}/\n'
        f'\nchmod -Rf 771 {DERIVATIVES_DIR}/qc/{data_type}\n'
    )

    # Write the complete SLURM script to the specified file
    with open(path_to_script, 'w') as f:
        f.write(header + module_export + singularity_cmd + save_work)


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

    if data_type not in ["raw", "fmriprep", "xcp_d", "qsiprep", "qsirecon"]:
        print(f"Invalid data_type: {data_type}. Must be 'raw', 'fmriprep', or 'qsiprep'.")
        return None

    DERIVATIVES_DIR = config["common"]["derivatives"]

    path_to_script = f"{DERIVATIVES_DIR}/qc/{data_type}/scripts/group_mriqc_{data_type}.slurm"
    generate_slurm_script(config, input_dir, data_type=data_type, path_to_script=path_to_script, job_ids=job_ids)

    cmd = f"sbatch {path_to_script}"
    job_id = utils.submit_job(cmd)
    return job_id
