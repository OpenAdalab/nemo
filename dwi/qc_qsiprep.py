import json
import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
import utils
from run_mriqc_group import run_mriqc_group
from run_mriqc import run_mriqc
from dwi.run_qsiprep import is_already_processed as is_qsiprep_done


def run_participant_qc(config, subject, session, job_ids=None):
    common = config["common"]
    DERIVATIVES_DIR = common["derivatives"]
    mriqc = config["mriqc"]

    if not is_qsiprep_done(config, subject, session):
        print(f"[QC-QSIPREP] QSIPrep did not terminate for {subject} {session}. Please run QSIprep command before QC.")
        return None

    # Run participant-level MRIQC
    print(f"[QC-QSIPREP] Submitting MRIQC job")
    mriqc_job_id = run_mriqc(config, subject, session, data_type="qsiprep", job_ids=job_ids)

    # Run in interactive mode to avoid using resources on the connection front
    # It is also mandatory to ensure correct orchestration and wait for previous jobs to be terminated
    print(f"[QC-QSIPREP] Submitting QC metric extraction in (background) interactive mode")
    cmd = (f'\nsrun --job-name=fsqc --ntasks=1 '
           f'--partition={mriqc["partition"]} '
           f'--mem={mriqc["requested_mem"]} '
           f'--time={mriqc["requested_time"]} '
           f'--out={DERIVATIVES_DIR}/qc/qsiprep/stdout/qc_qsiprep_{subject}_{session}_%j.out '
           f'--err={DERIVATIVES_DIR}/qc/qsiprep/stdout/qc_qsiprep_{subject}_{session}_%j.err ')
    if job_ids:
        cmd += f'--dependency=afterok:{":".join(job_ids)} '
    # Call to python scripts for the rest of QC
    cmd += (
        f'\necho "Running QC metric extraction"\n'
        f'python3 dwi/qc_qsiprep.py '
        f"'{json.dumps(config)}' 'participant' '{subject}' '{session}'\n"
    )
    os.system(cmd)

    return mriqc_job_id


def run_group_qc(config, job_ids=None):

    common = config["common"]
    DERIVATIVES_DIR = common["derivatives"]
    mriqc = config["mriqc"]

    # Run group-level MRIQC
    # run_mriqc_group(config, f"{DERIVATIVES_DIR}/qsiprep/outputs", data_type="qsiprep", job_ids=job_ids)

    # Run in interactive mode to avoid using resources on the connection front
    # It is also mandatory to ensure correct orchestration and wait for previous jobs to be terminated
    print(f"[QSIPREP-GROUP-QC] Performing QC metric concatenation in (background) interactive mode")
    cmd = (f'\nsrun --job-name=fsqc --ntasks=1 '
           f'--partition={mriqc["partition"]} '
           f'--mem={mriqc["requested_mem"]} '
           f'--time={mriqc["requested_time"]} '
           f'--out={DERIVATIVES_DIR}/qc/qsiprep/stdout/qc_group_qsiprep_%j.out '
           f'--err={DERIVATIVES_DIR}/qc/qsiprep/stdout/qc_group_qsiprep_%j.err ')
    if job_ids:
        cmd += f'--dependency=afterok:{":".join(job_ids)} '
    cmd += f"'python3 dwi/qc_qsiprep.py {json.dumps(config)} 'group' &"
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
    Returns
    -------
    pd.DataFrame
        DataFrame containing QC metrics for each subject and session.
    """

    DERIVATIVES_DIR = config["common"]["derivatives"]
    output_dir = f"{DERIVATIVES_DIR}/qsiprep/outputs/{subject}/{session}"
    anat = Path(f"{DERIVATIVES_DIR}/qsiprep/outputs/{subject}/{session}/anat")
    dwi = Path(f"{DERIVATIVES_DIR}/qsiprep/outputs/{subject}/{session}/dwi")

    try:
        # Extract process status from log files
        finished_status, runtime = utils.read_log(config, subject, session, runtype="qsiprep")
        dir_count = utils.count_dirs(output_dir)
        file_count = utils.count_files(output_dir)

        # Load TSV file produced by QSIprep
        qsiprep_metrics = f'{subject}_{session}_run-01_desc-confounds_timeseries.tsv'
        df = pd.read_csv(os.path.join(output_dir, 'dwi', qsiprep_metrics), sep='\t')

        max_framewise_displacement = df['framewise_displacement'].max()
        max_rot_x = df['rot_x'].max()
        max_rot_y = df['rot_y'].max()
        max_rot_z = df['rot_z'].max()
        max_trans_x = df['trans_x'].max()
        max_trans_y = df['trans_y'].max()
        max_trans_z = df['trans_z'].max()
        max_eddy_stdevs = df['eddy_stdevs'].max()
        max_denoising_change = df['DWIDenoise_change'].max() if 'DWIDenoise_change' in df.columns else 0
        max_unringing_change = df['MRDeGibbs_change'].max() if 'MRDeGibbs_change' in df.columns else 0

        # Identify required files
        t1w = next(anat.glob("*_desc-preproc_T1w.nii.gz"))
        t1w_mask = next(anat.glob("*_desc-brain_mask.nii.gz"))
        seg = next(anat.glob("*_dseg.nii.gz"))
        dwiref = next(dwi.glob("*_dwiref.nii.gz"))
        dwi_mask = next(dwi.glob("*_desc-brain_mask.nii.gz"))

        # Load data
        t1w_img = utils.load_any_image(t1w)
        t1w_data = t1w_img.get_fdata()
        t1w_mask_img = utils.load_any_image(t1w_mask)
        t1w_mask_data = t1w_mask_img.get_fdata()
        dwi_img = utils.load_any_image(dwiref)
        dwi_data = dwi_img.get_fdata()
        dwi_mask_img = utils.load_any_image(dwi_mask)
        dwi_mask_data = dwi_mask_img.get_fdata()
        seg_img = utils.load_any_image(seg)
        seg_data = seg_img.get_fdata()

        # Resample dwi into t1w space
        t1w_brain = t1w_data * t1w_mask_data
        dwi_brain = dwi_data * dwi_mask_data
        dwi_brain_hr = utils.resample(dwi_brain, t1w_data)
        dwi_mask_data_hr = utils.resample(dwi_mask_data, t1w_data)

        # Compute QC metrics
        row = dict(
            subject=subject,
            session=session,
            Process_Run="qsiprep",
            Finished_without_error=finished_status,
            Processing_time_hours=runtime,
            Number_of_folders_generated=dir_count,
            Number_of_files_generated=file_count,
            t1w_shape=t1w_data.shape,
            dwiref_shape=dwi_data.shape,
            brain_voxels_t1w=np.sum(t1w_mask_data > 0),
            brain_voxels_dwi=np.sum(dwi_mask_data > 0),
            gm_voxels=np.sum(seg_data == 2),
            wm_voxels=np.sum(seg_data == 3),
            csf_voxels=np.sum(seg_data == 1),
            DICE_t1w_dwi=utils.dice(t1w_mask_data, dwi_mask_data_hr),
            MI_t1w_dwi=utils.mutual_information(t1w_brain, dwi_brain_hr),
            max_framewise_displacement=max_framewise_displacement,
            max_rot_x=max_rot_x,
            max_rot_y=max_rot_y,
            max_rot_z=max_rot_z,
            max_trans_x=max_trans_x,
            max_trans_y=max_trans_y,
            max_trans_z=max_trans_z,
            max_eddy_stdevs=max_eddy_stdevs,
            max_denoising_change=max_denoising_change,
            max_unringing_change=max_unringing_change,
        )

        sub_ses_qc = pd.DataFrame([row])
        # Save outputs to csv file
        path_to_qc = f"{DERIVATIVES_DIR}/qc/qsiprep/outputs/{subject}/{session}/{subject}_{session}_qc.csv"
        sub_ses_qc.to_csv(path_to_qc, mode='w', header=True, index=False)
        print(f"QC saved in {path_to_qc}\n")

        print(f"QSIPrep Quality Check terminated successfully for {subject} {session}.")

    except Exception as e:
        print(f"⚠️ ERROR: QC aborted for {subject} {session}: \n{e}")


def metric_concatenation(config):

    DERIVATIVES_DIR = config["common"]["derivatives"]

    # Load and Concatenate participant-level metrics
    qc_inhouse = []
    qc_qsiprep = []
    # List all subjects and sessions in the QSIprep BIDS output directory
    subjects = utils.get_subjects(f"{DERIVATIVES_DIR}/qsiprep/outputs")
    for subject in subjects:
        sessions = utils.get_sessions(f"{DERIVATIVES_DIR}/qsiprep/outputs", subject)
        for session in sessions:

            # Concatenate in-house metrics
            path_to_qc = Path(f"{DERIVATIVES_DIR}/qc/qsiprep/outputs/{subject}/{session}/{subject}_{session}_qc.csv")
            if not path_to_qc.is_file():
                continue
            qc_inhouse.append(pd.read_csv(path_to_qc))

            # Concatenate QSIPrep metrics
            path_to_dwi = Path(f"{DERIVATIVES_DIR}/qsiprep/outputs/{subject}/{session}/dwi")
            path_to_qc = next(path_to_dwi.glob("*_desc-image_qc.tsv"))
            if not path_to_qc.is_file():
                continue
            qc_qsiprep.append(pd.read_csv(path_to_qc, sep='\t'))

    if qc_inhouse:
        group_qc = pd.concat(qc_inhouse, ignore_index=True)
        path_to_group_qc = f"{DERIVATIVES_DIR}/qc/qsiprep/group_minimal_qc.csv"
        group_qc.to_csv(path_to_group_qc, index=False)

    if qc_qsiprep:
        group_qc = pd.concat(qc_qsiprep, ignore_index=True)
        path_to_group_qc = f"{DERIVATIVES_DIR}/qc/qsiprep/group_qsiprep_image_qc.csv"
        group_qc.to_csv(path_to_group_qc, index=False)

    print(f"[QC-QSIPREP] Group-level QC saved in {DERIVATIVES_DIR}/qc/qsiprep\n")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        raise RuntimeError(
            "Usage: python qc_qsiprep.py <config> participant <subject> <session>"
            "Usage: python qc_qsiprep.py <config> group"
        )
    config = json.loads(sys.argv[1])
    level = sys.argv[2]
    if level == 'participant':
        subject = sys.argv[3]
        session = sys.argv[4]
        metric_extraction(config, subject, session)
    if level == 'group':
        metric_concatenation(config)
