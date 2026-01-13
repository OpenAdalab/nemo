#!/usr/bin/env python3
import json
import warnings
import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import utils
from rsfmri.run_fmriprep import is_already_processed as is_fmriprep_done
from run_mriqc import run_mriqc
from run_mriqc_group import run_mriqc_group
warnings.filterwarnings("ignore")


def run_participant_qc(config, subject, session, job_ids=None):
    """
    Run the qc_fmriprep for a given subject and session.

    Parameters
    ----------
    config : dict
        Configuration arguments.
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

    common = config["common"]
    DERIVATIVES_DIR = common["derivatives"]
    mriqc = config["mriqc"]

    if not is_fmriprep_done(config, subject, session):
        print(f"[FMRIPREP-QC] FMRIPrep did not terminate for {subject} {session}. Please run FMRIPrep command before QC.")
        return None

    # Run participant-level MRIQC
    # print(f"[QC-FMRIPREP] Submitting MRIQC job")
    # mriqc_job_id = run_mriqc(config, subject, session, data_type="fmriprep", job_ids=job_ids)
    mriqc_job_id = None

    print(f"[FMRIPREP-QC] Submitting QC metric extraction in (background) interactive mode")
    cmd = (f'\nsrun --job-name=py_qc_fmriprep --ntasks=1 '
           f'--partition={mriqc["partition"]} '
           f'--mem={mriqc["requested_mem"]}gb '
           f'--time={mriqc["requested_time"]} '
           f'--out={DERIVATIVES_DIR}/qc/fmriprep/stdout/qc_fmriprep_{subject}_{session}_%j.out '
           f'--err={DERIVATIVES_DIR}/qc/fmriprep/stdout/qc_fmriprep_{subject}_{session}_%j.err ')
    if job_ids:
        cmd += f'--dependency=afterok:{":".join(job_ids)} '
    # Call to python scripts for the rest of QC
    cmd += f"python3 rsfmri/qc_fmriprep.py '{json.dumps(config)}' participant {subject} {session} &"
    os.system(cmd)

    return mriqc_job_id


def run_group_qc(config, job_ids=None):

    common = config["common"]
    DERIVATIVES_DIR = common["derivatives"]
    mriqc = config["mriqc"]

    # Run group-level MRIQC
    print(f"[FMRIPREP-GROUP-QC] Submitting MRIQC job")
    run_mriqc_group(config, f"{DERIVATIVES_DIR}/fmriprep/outputs", data_type="fmriprep", job_ids=job_ids)

    # Run in interactive mode to avoid using resources on the connection front
    # It is also mandatory to ensure correct orchestration and wait for previous jobs to be terminated
    print(f"[FMRIPREP-GROUP-QC] Performing QC metric concatenation in (background) interactive mode")
    cmd = (f'\nsrun --job-name=py_qc_fmriprep --ntasks=1 '
           f'--partition={mriqc["partition"]} '
           f'--mem={mriqc["requested_mem"]} '
           f'--time={mriqc["requested_time"]} '
           f'--out={DERIVATIVES_DIR}/qc/fmriprep/stdout/qc_group_fmriprep_%j.out '
           f'--err={DERIVATIVES_DIR}/qc/fmriprep/stdout/qc_group_fmriprep_%j.err ')
    if job_ids:
        cmd += f'--dependency=afterok:{":".join(job_ids)} '
    cmd += f"python3 rsfmri/qc_fmriprep.py '{json.dumps(config)}' group &"
    os.system(cmd)


# ------------------------------------------
# Metric extraction (call from srun command)
# ------------------------------------------
def metric_extraction(config, subject, session):
    """
    Extract QC metrics from fMRIPrep outputs.

    Parameters
    ----------
    config : dict
        Configuration dictionary.
    fmriprep_dir : Path
        Path to the fMRIPrep derivatives directory.
    Returns
    -------
    pd.DataFrame
        DataFrame containing QC metrics for each subject and session.
    """

    DERIVATIVES_DIR = config["common"]["derivatives"]
    fmriprep_dir = f"{DERIVATIVES_DIR}/fmriprep/outputs/{subject}/{session}"

    # Read bids_filter file to get the list of tasks to consider
    tasks = utils.get_tasks(session)

    for task in tasks:
        try:
            # Extract process status from log files
            finished_status, runtime = utils.read_log(config, subject, session, runtype="fmriprep")
            dir_count = utils.count_dirs(fmriprep_dir)
            file_count = utils.count_files(fmriprep_dir)

            # Load TSV file produced by FMRIprep
            fmriprep_metrics = f'{subject}_{session}_task-{task}_desc-confounds_timeseries.tsv'
            df = pd.read_csv(os.path.join(fmriprep_dir, 'func', fmriprep_metrics), sep='\t')

            max_framewise_displacement = df['framewise_displacement'].max()
            max_rot_x = df['rot_x'].max()
            max_rot_y = df['rot_y'].max()
            max_rot_z = df['rot_z'].max()
            max_trans_x = df['trans_x'].max()
            max_trans_y = df['trans_y'].max()
            max_trans_z = df['trans_z'].max()
            max_dvars = df['dvars'].max()
            max_rmsd = df['rmsd'].max()

            anat = Path(os.path.join(fmriprep_dir, "anat"))
            func = Path(os.path.join(fmriprep_dir, "func"))

            # Identify required files
            t1w = next(anat.glob("*_desc-preproc_T1w.nii.gz"))
            t1w_mask = next(anat.glob("*_desc-brain_mask.nii.gz"))
            gm = next(anat.glob("*_label-GM_probseg.nii.gz"))
            wm = next(anat.glob("*_label-WM_probseg.nii.gz"))
            csf = next(anat.glob("*_label-CSF_probseg.nii.gz"))
            bold = next(func.glob(f"*{task}_space-T1w_desc-preproc_bold.nii.gz"))
            bold_mask = next(func.glob(f"*{task}_space-T1w_desc-brain_mask.nii.gz"))

            # Load data
            t1w_img = utils.load_any_image(t1w)
            t1w_data = t1w_img.get_fdata()
            del t1w_img
            t1w_mask_img = utils.load_any_image(t1w_mask)
            t1w_mask_data = t1w_mask_img.get_fdata()
            del t1w_mask_img
            bold_img = utils.load_any_image(bold)
            bold_data = bold_img.get_fdata()
            del bold_img

            # Compute mean BOLD image
            mean_bold = np.mean(bold_data, axis=3)

            # Load masks for voxel counts
            bold_mask_img = utils.load_any_image(bold_mask)
            bold_mask_data = bold_mask_img.get_fdata()
            del bold_mask_img
            t1w_brain = t1w_data * t1w_mask_data
            bold_brain = mean_bold * bold_mask_data

            gm_img = utils.load_any_image(gm)
            gm_mask = gm_img.get_fdata() > 0.5
            del gm_img
            wm_img = utils.load_any_image(wm)
            wm_mask = wm_img.get_fdata() > 0.5
            del wm_img
            csf_img = utils.load_any_image(csf)
            csf_mask = csf_img.get_fdata() > 0.5
            del csf_img

            # Resample bold into t1w space
            bold_brain_hr = utils.resample(bold_brain, t1w_data)
            bold_mask_data_hr = utils.resample(bold_mask_data, t1w_data)

            # Compute QC metrics
            row = dict(
                subject=subject,
                session=session,
                task=task,
                Process_Run="fmriprep",
                Finished_without_error=finished_status,
                Processing_time_hours=runtime,
                Number_of_folders_generated=dir_count,
                Number_of_files_generated=file_count,
                t1w_shape=t1w_data.shape,
                brain_voxels_t1w=np.sum(t1w_mask_data > 0),
                brain_voxels_bold=np.sum(bold_mask_data > 0),
                bold_shape=bold_data.shape,
                gm_voxels=np.sum(gm_mask > 0),
                wm_voxels=np.sum(wm_mask > 0),
                csf_voxels=np.sum(csf_mask > 0),
                DICE_t1w_bold=utils.dice(t1w_mask_data, bold_mask_data_hr),
                MI_t1w_bold=utils.mutual_information(t1w_brain, bold_brain_hr),
                max_framewise_displacement=max_framewise_displacement,
                max_rot_x=max_rot_x,
                max_rot_y=max_rot_y,
                max_rot_z=max_rot_z,
                max_trans_x=max_trans_x,
                max_trans_y=max_trans_y,
                max_trans_z=max_trans_z,
                max_dvars=max_dvars,
                max_rmsd=max_rmsd,
            )

            # Save outputs to csv file
            sub_ses_qc = pd.DataFrame([row])
            path_to_qc = f"{DERIVATIVES_DIR}/qc/fmriprep/outputs/{subject}/{session}/{subject}_{session}_task-{task}_qc.csv"
            sub_ses_qc.to_csv(path_to_qc, mode='w', header=True, index=False)
            print(f"QC saved in {path_to_qc}\n")

            print(f"Fmriprep Quality Check terminated successfully for {subject} {session} task-{task}.")

        except Exception as e:
            print(f"⚠️ ERROR: QC aborted for {subject} {session} task-{task}: \n{e}")


def metric_concatenation(config):

    DERIVATIVES_DIR = config["common"]["derivatives"]

    # Load and Concatenate participant-level metrics
    qc_inhouse = []
    # List all subjects and sessions in the FMRIPrep BIDS output directory
    subjects = utils.get_subjects(f"{DERIVATIVES_DIR}/fmriprep/outputs")
    for subject in subjects:
        sessions = utils.get_sessions(f"{DERIVATIVES_DIR}/fmriprep/outputs", subject)
        for session in sessions:
            tasks = utils.get_tasks(session)
            for task in tasks:
                # Concatenate in-house metrics
                path_to_qc = Path(f"{DERIVATIVES_DIR}/qc/fmriprep/outputs/{subject}/{session}/{subject}_{session}_task-{task}_qc.csv")
                if not path_to_qc.is_file():
                    continue
                qc_inhouse.append(pd.read_csv(path_to_qc))

    if qc_inhouse:
        group_qc = pd.concat(qc_inhouse, ignore_index=True)
        path_to_group_qc = f"{DERIVATIVES_DIR}/qc/fmriprep/group_minimal_qc.csv"
        group_qc.to_csv(path_to_group_qc, index=False)

    print(f"[QC-FMRIPREP] Group-level QC saved in {DERIVATIVES_DIR}/qc/fmriprep\n")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        raise RuntimeError(
            "Usage: python qc_fmriprep.py <config> participant <subject> <session>"
            "Usage: python qc_qsirecon.py <config> group"
        )
    config = json.loads(sys.argv[1])
    level = sys.argv[2]
    if level == 'participant':
        subject = sys.argv[3]
        session = sys.argv[4]
        metric_extraction(config, subject, session)
    if level == 'group':
        metric_concatenation(config)