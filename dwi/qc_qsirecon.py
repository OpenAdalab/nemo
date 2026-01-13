import json
import os
import sys
import pandas as pd
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import utils
from dwi.run_qsirecon import is_already_processed as is_qsirecon_done


def run_participant_qc(config, subject, session, job_ids=None):

    common = config["common"]
    DERIVATIVES_DIR = common["derivatives"]
    mriqc = config["mriqc"]

    if not is_qsirecon_done(config, subject, session):
        print(f"[QSIRECON-QC] QSIrecon did not terminate for {subject} {session}. Please run QSIrecon command before QC.")
        return None

    # Create output (derivatives) directories
    os.makedirs(f"{DERIVATIVES_DIR}/qc/qsirecon", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/qc/qsirecon/outputs/{subject}/{session}", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/qc/qsirecon/stdout", exist_ok=True)

    # Run in interactive mode to avoid using resources on the connection front
    # It is also mandatory to ensure correct orchestration and wait for previous jobs to be terminated
    print(f"[QSIRECON-QC] Submitting QC metric extraction in (background) interactive mode")
    cmd = (f'\nsrun --job-name=py_qc_qsirecon --ntasks=1 '
           f'--partition={mriqc["partition"]} '
           f'--mem={mriqc["requested_mem"]}gb '
           f'--time={mriqc["requested_time"]} '
           f'--out={DERIVATIVES_DIR}/qc/qsirecon/stdout/qc_qsirecon_{subject}_{session}_%j.out '
           f'--err={DERIVATIVES_DIR}/qc/qsirecon/stdout/qc_qsirecon_{subject}_{session}_%j.err ')
    if job_ids:
        cmd += f'--dependency=afterok:{":".join(job_ids)} '
    # Call to python scripts for the rest of QC
    cmd += f"python3 dwi/qc_qsirecon.py '{json.dumps(config)}' participant {subject} {session} &"
    os.system(cmd)


def run_group_qc(config, job_ids=None):

    common = config["common"]
    DERIVATIVES_DIR = common["derivatives"]
    mriqc = config["mriqc"]

    # Run in interactive mode to avoid using resources on the connection front
    # It is also mandatory to ensure correct orchestration and wait for previous jobs to be terminated
    print(f"[QSIRECON-GROUP-QC] Performing QC metric concatenation in (background) interactive mode")
    cmd = (f'\nsrun --job-name=py_qc_qsirecon --ntasks=1 '
           f'--partition={mriqc["partition"]} '
           f'--mem={mriqc["requested_mem"]}gb '
           f'--time={mriqc["requested_time"]} '
           f'--out={DERIVATIVES_DIR}/qc/qsirecon/stdout/qc_group_qsirecon_%j.out '
           f'--err={DERIVATIVES_DIR}/qc/qsirecon/stdout/qc_group_qsirecon_%j.err ')
    if job_ids:
        cmd += f'--dependency=afterok:{":".join(job_ids)} '
    cmd += f"python3 dwi/qc_qsirecon.py '{json.dumps(config)}' group &"
    os.system(cmd)


# ------------------------------------------
# Metric extraction (call from srun command)
# ------------------------------------------
def metric_extraction(config, subject, session):
    """
    Extract QC metrics from QSIPrep outputs.

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
    qsirecon_dir = f"{DERIVATIVES_DIR}/qsirecon/outputs/{subject}/{session}"

    try:
        # Extract process status from log files
        finished_status, runtime = utils.read_log(config, subject, session, runtype="qsirecon")
        dir_count = utils.count_dirs(qsirecon_dir)
        file_count = utils.count_files(qsirecon_dir)

        # Compute QC metrics
        row = dict(
            subject=subject,
            session=session,
            Process_Run="qsiprep",
            Finished_without_error=finished_status,
            Processing_time_hours=runtime,
            Number_of_folders_generated=dir_count,
            Number_of_files_generated=file_count,
        )

        sub_ses_qc = pd.DataFrame([row])
        # Save outputs to csv file
        path_to_qc = f"{DERIVATIVES_DIR}/qc/qsirecon/outputs/{subject}/{session}/{subject}_{session}_qc.csv"
        sub_ses_qc.to_csv(path_to_qc, mode='w', header=True, index=False)
        print(f"QC saved in {path_to_qc}\n")

        print(f"QSIRecon Quality Check terminated successfully for {subject} {session}.")

    except Exception as e:
        print(f"⚠️ ERROR: QC aborted for {subject} {session}: \n{e}")


def metric_concatenation(config):

    DERIVATIVES_DIR = config["common"]["derivatives"]

    qc_inhouse = []

    # List all subjects and sessions in the QSIrecon BIDS output directory
    subjects = utils.get_subjects(f"{DERIVATIVES_DIR}/qsirecon/outputs")
    for subject in subjects:
        sessions = utils.get_sessions(f"{DERIVATIVES_DIR}/qsirecon/outputs", subject)
        for session in sessions:

            # Concatenate in-house metrics
            path_to_qc = Path(f"{DERIVATIVES_DIR}/qc/qsirecon/outputs/{subject}/{session}/{subject}_{session}_qc.csv")
            if not path_to_qc.is_file():
                continue
            qc_inhouse.append(pd.read_csv(path_to_qc))

    if qc_inhouse:
        group_qc = pd.concat(qc_inhouse, ignore_index=True)
        path_to_group_qc = f"{DERIVATIVES_DIR}/qc/qsirecon/group_minimal_qc.csv"
        group_qc.to_csv(path_to_group_qc, index=False)

    print(f"[QSIRECON-QC] Group-level QC saved in {DERIVATIVES_DIR}/qc/qsirecon\n")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        raise RuntimeError(
            "Usage: python qc_qsirecon.py <config> participant <subject> <session>"
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
