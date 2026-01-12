# run_workflow.py
"""
This script orchestrates the execution of various neuroimaging workflows including
fMRIPrep, FreeSurfer, QSIprep, QSIrecon, XCP-D, and MRIQC. It reads configuration
settings from a TOML file, checks for the existence of required data, and submits
jobs for each workflow step based on the specified subjects and sessions.
It also handles group-level MRIQC jobs for the processed data.

It is designed to be run in a Slurm environment, where each step can be submitted as a job.
Usage:
    python run_workflow.py [--config <path_to_config_file>]
"""

import os
from datetime import datetime
from pathlib import Path
import sys
import toml
sys.path.append(str(Path(__file__).resolve().parent))
import utils
from anat import qc_freesurfer
from dwi import qc_qsiprep, qc_qsirecon
from rsfmri import qc_fmriprep, qc_xcpd
from anat.run_freesurfer import run_freesurfer
from dwi.run_qsiprep import run_qsiprep
from dwi.run_qsirecon import run_qsirecon
from rsfmri.run_fmriprep import run_fmriprep
from rsfmri.run_xcpd import run_xcpd
from run_mriqc import run_mriqc
from run_mriqc_group import run_mriqc_group


def main(config_file=None):
    """
    Main function to execute the workflow steps based on the configuration file.
    Parameters
    ----------
    config_file : str, optional
        Path to the configuration file. If None, a default path is used.
    """

    # -------------------------------
    # Load configuration
    # -------------------------------
    if not config_file:
        config_file = f"{Path(__file__).parent}/config/config.toml"
    config = utils.load_config(config_file)

    common = config["common"]
    workflow = config["workflow"]

    BIDS_DIR = common["input_dir"]
    DERIVATIVES_DIR = common["derivatives"]

    # Save config with datetime
    filename = f"{DERIVATIVES_DIR}/config_{datetime.now().strftime('%Y%m%d-%H%M%S')}.toml"
    with open(filename, "w") as f:
        toml.dump(config, f)

    # -------------------------------------------------------
    # Sanity checks
    # -------------------------------------------------------
    if not os.path.exists(BIDS_DIR):
        print("Dataset directory does not exist.")
        return 0

    subjects_sessions = []
    freesurfer_job_ids = []
    mriqc_job_ids = []
    qc_qsiprep_job_ids = []
    qc_qsirecon_job_ids = []
    qc_fmriprep_job_ids = []
    qc_xcpd_job_ids = []

    # -------------------------------------------------------
    # Loop over subjects and sessions
    subjects = utils.get_subjects(BIDS_DIR, common.get('subjects'))

    print("\nThe following subjects will be processed :", subjects)

    # -------------------------------------------------------
    # Workflow per subject
    # -------------------------------------------------------
    for subject in subjects:
        # Check if subject exists
        if not utils.subject_exists(BIDS_DIR, subject):
            print(f"[WARNING] Subject {subject} does not exist in the input directory. Skipping.")
            continue

        print(f"\n================ {subject} ================")

        # -------------------------------------------
        # Loop over sessions
        # -------------------------------------------
        sessions = utils.get_sessions(BIDS_DIR, subject, common.get('sessions'))

        # FMRIprep must wait for a session to be finished before running the next one
        fmriprep_sub_job_ids = []

        for session in sessions:

            print('\n', subject, ' - ', session, '\n')
            subjects_sessions.append(f"{subject}_{session}")

            # -------------------------------------------
            # 0. MRIQC on raw BIDS data
            # -------------------------------------------
            if workflow.get("run_raw_qc"):
                print("[MRIQC-RAW] (raw data)")
                mriqc_raw_job_id = run_mriqc(
                    config,
                    subject=subject,
                    session=session,
                    data_type="raw"
                    )
                mriqc_job_ids.append(mriqc_raw_job_id)

            # -------------------------------------------
            # 1. FREESURFER
            # -------------------------------------------
            if workflow.get("run_freesurfer"):
                print("[FREESURFER]")
                freesurfer_job_id = run_freesurfer(
                    config,
                    subject=subject,
                    session=session
                )
                freesurfer_job_ids.append(freesurfer_job_id)
            else:
                freesurfer_job_id = None

            # -------------------------------------------
            # 2a. QSIprep
            # -------------------------------------------
            if workflow.get("run_qsiprep"):
                print("[QSIPREP]")
                qsiprep_job_id = run_qsiprep(
                    config,
                    subject=subject,
                    session=session
                )
            else:
                qsiprep_job_id = None
            # -------------------------------------------
            # 2b. QC QSIprep
            # -------------------------------------------
            if workflow.get("run_qsiprep_qc"):
                print("[QSIPREP-QC]")
                dependencies = [job_id for job_id in [qsiprep_job_id] if job_id is not None]
                qc_qsiprep_job_id = qc_qsiprep.run_participant_qc(
                    config,
                    subject=subject,
                    session=session,
                    job_ids=dependencies
                )
                qc_qsiprep_job_ids.append(qc_qsiprep_job_id)

            # -------------------------------------------
            # 3a. QSIrecon
            # -------------------------------------------
            if workflow.get("run_qsirecon"):
                print("[QSIRECON]")
                dependencies = [job_id for job_id in [freesurfer_job_id, qsiprep_job_id] if job_id is not None]
                qsirecon_job_id = run_qsirecon(
                    config,
                    subject=subject,
                    session=session,
                    job_ids=dependencies
                )
            else:
                qsirecon_job_id = None
            # -------------------------------------------
            # 3b. QC QSIrecon
            # -------------------------------------------
            if workflow.get("run_qsirecon_qc"):
                print("[QSIRECON-QC]")
                dependencies = [job_id for job_id in [qsirecon_job_id] if job_id is not None]
                qc_qsirecon_job_id = qc_qsirecon.run_participant_qc(
                    config,
                    subject=subject,
                    session=session,
                    job_ids=dependencies
                )
                qc_qsirecon_job_ids.append(qc_qsirecon_job_id)

            # -------------------------------------------
            # 4a fMRIPrep
            # -------------------------------------------
            if workflow.get("run_fmriprep"):
                print("[FMRIPREP]")
                dependencies = [job_id for job_id in [freesurfer_job_id] + fmriprep_sub_job_ids if job_id is not None]
                fmriprep_job_id = run_fmriprep(
                    config,
                    subject=subject,
                    session=session,
                    job_ids=dependencies
                )
                fmriprep_sub_job_ids.append(fmriprep_job_id)
            else:
                fmriprep_job_id = None
            # -------------------------------------------
            # 4b QC fMRIPrep
            # -------------------------------------------
            if workflow.get("run_fmriprep_qc"):
                print("[FMRIPREP-QC]")
                dependencies = [job_id for job_id in [fmriprep_job_id] if job_id is not None]
                qc_fmriprep_job_id = qc_fmriprep.run_participant_qc(
                    config,
                    subject=subject,
                    session=session,
                    job_ids=dependencies
                )
                qc_fmriprep_job_ids.append(qc_fmriprep_job_id)

            # -------------------------------------------
            # 5a. XCP-D
            # -------------------------------------------
            if workflow.get("run_xcp_d"):
                print("[XCP-D]")
                dependencies = [job_id for job_id in [fmriprep_job_id] if job_id is not None]
                xcpd_job_id = run_xcpd(
                    config,
                    subject=subject,
                    session=session,
                    job_ids=dependencies
                )
            else:
                xcpd_job_id = None
            # -------------------------------------------
            # 5b QC XCP-D
            # -------------------------------------------
            if workflow.get("run_xcpd_qc"):
                print("[XCPD-QC]")
                dependencies = [job_id for job_id in [xcpd_job_id] if job_id is not None]
                qc_xcpd_job_id = qc_xcpd.run_participant_qc(
                    config,
                    subject=subject,
                    session=session,
                    job_ids=dependencies
                )
            else:
                qc_xcpd_job_id = None
            qc_xcpd_job_ids.append(qc_xcpd_job_id)

        print("\n✅ Workflow submission complete for subject:", subject)

    # -------------------------------------------
    # 6. QC FREESURFER
    # -------------------------------------------
    if workflow.get("run_freesurfer_qc"):
        print("[QC-FREESURFER]")
        dependencies = [job_id for job_id in freesurfer_job_ids if job_id is not None]
        qc_freesurfer.run(
            config,
            job_ids=dependencies
        )

    # -------------------------------------------------------
    # 7. GROUP-LEVEL QC
    # -------------------------------------------------------
    if workflow.get("run_group_qc"):
        print(f"\n================ Group-level QC ================\n")
        #
        # # QC group-level for raw data
        # # -------------------------------------------
        # print(f"[MRIQC-GROUP] (raw data)")
        # dependencies = [job_id for job_id in mriqc_job_ids if job_id is not None]
        # run_mriqc_group(
        #     config,
        #     input_dir=BIDS_DIR,
        #     data_type="raw",
        #     job_ids=dependencies
        # )

        # # QC group-level for qsiprep data
        # # -------------------------------------------
        # print(f"[QSIPREP-GROUP-QC]")
        # dependencies = [job_id for job_id in qc_qsiprep_job_ids if job_id is not None]
        # qc_qsiprep.run_group_qc(config, job_ids=dependencies)

        # QC group-level for qsirecon data
        # -------------------------------------------
        print(f"[QSIRECON-GROUP-QC]")
        dependencies = [job_id for job_id in qc_qsirecon_job_ids if job_id is not None]
        qc_qsirecon.run_group_qc(config, job_ids=dependencies)

        # # QC group-level for fmriprep data
        # # -------------------------------------------
        # print(f"[FMRIPREP-GROUP-QC]")
        # dependencies = [job_id for job_id in qc_fmriprep_job_ids if job_id is not None]
        # qc_fmriprep.run_group_qc(config, job_ids=dependencies)
        #
        # # MRIQC group-level for xcp_d data
        # # -------------------------------------------
        # print(f"[XCPD-GROUP-QC]")
        # dependencies = [job_id for job_id in qc_xcpd_job_ids if job_id is not None]
        # qc_xcpd.run_group_qc(config, job_ids=dependencies)


if __name__ == "__main__":
    main()
