import json
import os
import pandas as pd
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parent.parent))
from _outlierDetection import outlierDetection_normalized, outlierTable, readAsegStats
import utils
import re
import csv
import numpy as np


def read_log(log_file):
    """
    Reads and parses a FreeSurfer log file to extract runtime and Euler number information.

    Parameters
    ----------
    log_file : str
        Path to the FreeSurfer log file.

    Returns
    -------
    tuple
        A tuple containing:
        - finished_status (str): "Success" if the process finished without error, otherwise "Error".
        - runtime (str): The runtime in hours, or "Not found" if unavailable.
        - eno_before_lh (float): Euler number before topological correction for the left hemisphere.
        - eno_before_rh (float): Euler number before topological correction for the right hemisphere.
        - eno_after_lh (float): Euler number after topological correction for the left hemisphere.
        - eno_after_rh (float): Euler number after topological correction for the right hemisphere.
    """

    if not os.path.exists(log_file):
        return None, None, None, None, None, None

    finished_pattern = re.compile(r"finished without error")
    runtime_pattern = re.compile(r"#@#%# recon-all-run-time-hours (\d+\.\d+)")
    topo_before_pattern_lh = re.compile(r"#@# Fix Topology lh.*?before topology correction, eno=([^\(]+)", re.DOTALL)
    topo_before_pattern_rh = re.compile(r"#@# Fix Topology rh.*?before topology correction, eno=([^\(]+)", re.DOTALL)
    topo_after_pattern_lh = re.compile(r"#@# Fix Topology lh.*?after topology correction, eno=([^\(]+)", re.DOTALL)
    topo_after_pattern_rh = re.compile(r"#@# Fix Topology rh.*?after topology correction, eno=([^\(]+)", re.DOTALL)

    # Read log file
    with open(log_file, 'r') as file:
        log_content = file.read()

    # Check if "finished without error" is present
    finished_status = "Success" if finished_pattern.search(log_content) else "Error"

    # Extract runtime
    runtime_match = runtime_pattern.search(log_content)
    runtime = runtime_match.group(1) if runtime_match else "Not found"

    # Extract Euler number before topological correction
    topo_match = topo_before_pattern_lh.search(log_content)
    eno_before_lh = topo_match.group(1) if topo_match else np.nan
    topo_match = topo_before_pattern_rh.search(log_content)
    eno_before_rh = topo_match.group(1) if topo_match else np.nan

    # Extract Euler number after topological correction
    topo_match = topo_after_pattern_lh.search(log_content)
    eno_after_lh = topo_match.group(1) if topo_match else np.nan
    topo_match = topo_after_pattern_rh.search(log_content)
    eno_after_rh = topo_match.group(1) if topo_match else np.nan

    return finished_status, runtime, eno_before_lh, eno_before_rh, eno_after_lh, eno_after_rh


def convert_radians_to_degrees(df):
    """
    Converts rotation angles from radians to degrees in a given DataFrame.

    Parameters
    ----------
    df : pandas.DataFrame
        A DataFrame containing columns 'rot_tal_x', 'rot_tal_y', and 'rot_tal_z'
        with rotation angles in radians.

    Returns
    -------
    pandas.DataFrame
        The input DataFrame with three new columns:
        - 'rot_tal_x_deg': Rotation angle in degrees for 'rot_tal_x'.
        - 'rot_tal_y_deg': Rotation angle in degrees for 'rot_tal_y'.
        - 'rot_tal_z_deg': Rotation angle in degrees for 'rot_tal_z'.
    """

    df["rot_tal_x_deg"] = df["rot_tal_x"].apply(lambda x: x * 180 / 3.14)
    df["rot_tal_y_deg"] = df["rot_tal_y"].apply(lambda x: x * 180 / 3.14)
    df["rot_tal_z_deg"] = df["rot_tal_z"].apply(lambda x: x * 180 / 3.14)
    return df


def normalize_aseg_volumes(freesurfer_dir, subjects_sessions, columns_to_extract,
                           ETIV='aseg.EstimatedTotalIntraCranialVol'):
    """
    Normalizes aseg volumes by the Estimated Total Intracranial Volume (ETIV) for a list of subjects/sessions.

    Parameters
    ----------
    freesurfer_dir : str
        Path to the FreeSurfer directory containing subject_session data.
    subjects_sessions : list of str
        List of subject/session identifiers.
    columns_to_extract : list of str
        List of column names to extract for quality control (QC).
    ETIV : str, optional
        Column name for the Estimated Total Intracranial Volume (default is 'aseg.EstimatedTotalIntraCranialVol').

    Returns
    -------
    pandas.DataFrame
        A DataFrame containing the extracted QC columns for all subjects/sessions.
    """

    df_qc = []
    for sub_sess in subjects_sessions:
        # Read aseg file
        aseg_stats_file = f"{freesurfer_dir}/{sub_sess}/stats/aseg.stats"
        aseg_stats = readAsegStats(aseg_stats_file)
        df_aseg = pd.DataFrame([aseg_stats])

        # Normalize volumes
        df_aseg_norm = df_aseg.drop(columns=columns_to_extract)
        df_aseg_norm = df_aseg_norm.div(df_aseg[ETIV], axis=0)
        aseg_norm = f"{freesurfer_dir}/{sub_sess}/stats/aseg_stats_norm.csv"
        df_aseg_norm.to_csv(aseg_norm, index=False)
        print(f"Normalized aseg volumes saved in {aseg_norm}")

        # Extract columns for QC
        df_sub = df_aseg[columns_to_extract].copy()
        df_sub.loc[0, 'subject'] = sub_sess
        df_qc.append(df_sub)

    return pd.concat(df_qc, ignore_index=True)


def calculate_outliers(freesurfer_dir, subjects_sessions, outlier_dir, outlier_params):

    """
    Adapted from fsqc.fsqcMain.py (line 2726).
    Compute outliers for each subject compared to the sample for the following values :
    - aseg volumes normalized by ETIV
    - aparc cortical thickness
    - hypothalamus substructures volume (optional)
    - hippocampus and amygdala substructures volume (optional)

    The comparison against normative values is not used because default normative values are not normalized by brain
    size. However, it would be possible to use custom normative values to give as a dictionary to the function and
    uncomment the n_outlier_norms line The function outlierDetection_normalized is also adapted from the original
    function. This one reads the normalized aseg stats from the csv files (aseg_stats_norm.csv).

    Parameters
    ----------
    freesurfer_dir : str
        Path to the FreeSurfer directory containing subject_session data.
    subjects_sessions : list of str
        List of subject/session identifiers.
    outlier_dir : str
        Path to the directory where outlier results will be saved.
    outlier_params : dict
        Dictionary of parameters for outlier detection, including:
        - 'min_no_subjects' (int): Minimum number of subjects required for analysis.
        - 'hypothalamus' (bool): Whether to include hypothalamus substructures in the analysis.
        - 'hippocampus' (bool): Whether to include hippocampus substructures in the analysis.
        - 'hippocampus_label' (str): Label for hippocampus substructures.
        - 'fastsurfer' (bool): Whether to use FastSurfer outputs.
        - 'outlierDict' (dict or None): Custom dictionary of outlier thresholds.

    Returns
    -------
    tuple
        A tuple containing:
        - df_group_stats (pandas.DataFrame): Group statistics for aparc/aseg metrics.
        - df_outliers (pandas.DataFrame): Outlier counts for each subject/session.
    """
    print("---------------------------------------")
    print("Running outlier detection")
    print("")

    # determine outlier-table and get data
    if outlier_params['outlierDict'] is None:
        outlierDict = outlierTable()
    else:
        outlierDict = dict()
        with open(outlierDict, newline="") as csvfile:
            outlierCsv = csv.DictReader(csvfile, delimiter=",")
            for row in outlierCsv:
                outlierDict.update(
                    {
                        row["label"]: {
                            "lower": float(row["lower"]),
                            "upper": float(row["upper"]),
                        }
                    }
                )

    # process
    (
        df_group_stats,
        n_outlier_sample_nonpar,
        n_outlier_sample_param,
        n_outlier_norms,
    ) = outlierDetection_normalized(
        subjects_sessions,
        freesurfer_dir,
        outlier_dir,
        outlierDict,
        min_no_subjects=outlier_params['min_no_subjects'],
        hypothalamus=outlier_params['hypothalamus'],
        hippocampus=outlier_params['hippocampus'],
        hippocampus_label=outlier_params['hippocampus_label'],
        fastsurfer=outlier_params['fastsurfer'],
    )

    # create a dictionary from outlier module output
    outlierDict = dict()
    for sub_sess in subjects_sessions:
        outlierDict.update(
            {
                sub_sess: {
                    "n_outlier_sample_nonpar_normalized": n_outlier_sample_nonpar[sub_sess],
                    "n_outlier_sample_param_normalized": n_outlier_sample_param[sub_sess],
                    # "n_outlier_norms": n_outlier_norms[sub_sess],  # valeurs de référence non normalisées par ETIV
                }
            }
        )

    # Convert outlierDict into a dataframe
    df_outliers = pd.DataFrame(outlierDict).T.reset_index()
    df_outliers = df_outliers.rename(columns={'index': 'subject'})

    return df_group_stats, df_outliers


def compute_metrics(config, subjects_sessions):
    """
    Computes various quality control (QC) metrics for FreeSurfer outputs, including log verification,
    volume normalization, and outlier detection.
    Note : Note that a minimum of 5 supplied subjects is required for running outlier analyses,
    otherwise NaNs will be returned.

    Parameters
    ----------
    config : dict
        Configuration dictionary containing paths and QC parameters.
    subjects_sessions : list of str
        List of subject/session identifiers to process.

    Returns
    -------
    None
        The function performs QC computations and saves the results to CSV files in the specified output directory.
    """

    common = config["common"]
    fsqc = config["fsqc"]
    DERIVATIVES_DIR = common["derivatives"]

    print("\n---------------------------------------")
    print("Running log verification")
    cols = ["subject",
            "Number of folders generated",
            "Number of files generated",
            "Finished without error",
            "Processing time (hours)",
            "Euler number before topo correction LH",
            "Euler number after topo correction RH",
            "Euler number before topo correction LH",
            "Euler number after topo correction RH"]
    frames = []
    print(subjects_sessions)
    for sub_sess in subjects_sessions:
        print(sub_sess)
        output_dir = f"{DERIVATIVES_DIR}/freesurfer/outputs/{sub_sess}"
        log_file = f"{output_dir}/scripts/recon-all.log"
        info = read_log(log_file)
        dir_count = utils.count_dirs(output_dir)
        file_count = utils.count_files(output_dir)
        frames.append([sub_sess, dir_count, file_count] + list(info))
    logs = pd.DataFrame(frames, columns=cols)
    fsqc_results = pd.read_csv(f"{DERIVATIVES_DIR}/qc/freesurfer/outputs/fsqc-results.csv")
    qc = pd.merge(logs, fsqc_results, on="subject", how="left")

    # Convert radians to degrees
    qc = convert_radians_to_degrees(qc)

    # Normalize ASEG volumes by ETIV
    print("\n---------------------------------------")
    print("Running volume normalization")
    columns_to_extract = ['aseg.EstimatedTotalIntraCranialVol',
                          'aseg.BrainSegVol_to_eTIV', 'aseg.MaskVol_to_eTIV', 'aseg.lhSurfaceHoles',
                          'aseg.rhSurfaceHoles', 'aseg.SurfaceHoles']
    vols = normalize_aseg_volumes(f"{DERIVATIVES_DIR}/freesurfer/outputs", subjects_sessions, columns_to_extract)
    qc = pd.merge(qc, vols, on="subject", how="left")

    # Calculate outliers and save new group aparc/aseg statistics
    outlier_dir = f"{DERIVATIVES_DIR}/qc/freesurfer/outliers"
    outlier_params = {
        'min_no_subjects': 5,
        'hypothalamus': fsqc["qc_hypothalamus"],
        'hippocampus': fsqc["qc_hippocampus"],
        'hippocampus_label': fsqc["qc_hippocampus_label"],
        'fastsurfer': False,
        'outlierDict': None
    }
    df_group_stats, df_outliers = calculate_outliers(f"{DERIVATIVES_DIR}/freesurfer/outputs", subjects_sessions, outlier_dir, outlier_params)
    df_group_stats.reset_index(inplace=True)
    path_to_group_stats = f"{DERIVATIVES_DIR}/qc/freesurfer/group_aparc-aseg.csv"
    df_group_stats.to_csv(path_to_group_stats, index=False)
    qc = pd.merge(qc, df_outliers, on="subject", how="left")

    path_to_final_qc = f"{DERIVATIVES_DIR}/qc/freesurfer/group_qc.csv"
    qc.to_csv(path_to_final_qc, index=False)
    print(f"QC saved in {path_to_final_qc}\n")

    print("FreeSurfer Quality Check terminated successfully.")

    return None


def generate_bash_script(config, subjects_sessions, path_to_script):
    """
    Generates a BASH script to run FreeSurfer QC and other quality control processes.

    """

    common = config["common"]
    fsqc = config["fsqc"]
    DERIVATIVES_DIR = common["derivatives"]

    module_export = (
        f'\nmodule purge\n'
        f'module load userspace/all\n'
        f'module load singularity\n'
        f'module load python3/3.12.0\n'
        f'source {common["python_env"]}/bin/activate\n'
    )

    subjects_sessions_str = " ".join(subjects_sessions)

    # Call to FSQC container
    singularity_command = (
        f'\napptainer exec \\\n'
        # f'    --writable-tmpfs --cleanenv \\\n'
        f'    -B {DERIVATIVES_DIR}/freesurfer/outputs:/data:ro \\\n'
        f'    -B {DERIVATIVES_DIR}/qc/freesurfer:/out \\\n'
        f'    {fsqc["fsqc_container"]} \\\n'
        f'    xvfb-run /app/fsqc/run_fsqc \\\n'
        f'    --subjects_dir /data \\\n'
        f'    --output_dir /out/outputs \\\n'
        # f'    --subjects {subjects_sessions_str}  \\\n'
    )
    if fsqc["qc_screenshots"]:
        singularity_command += f'      --screenshots \\\n'

    if fsqc["qc_surfaces"]:
        singularity_command += f'      --surfaces \\\n'

    if fsqc["qc_skullstrip"]:
        singularity_command += f'      --skullstrip \\\n'

    if fsqc["qc_fornix"]:
        singularity_command += f'      --fornix \\\n'

    if fsqc["qc_hypothalamus"]:
        singularity_command += f'      --hypothalamus \\\n'

    if fsqc["qc_hippocampus"]:
        singularity_command += f'      --hippocampus \\\n'

    if fsqc["qc_outlier"]:
        singularity_command += f'      --outlier \\\n'

    if fsqc["qc_skip_existing"]:
        singularity_command += f'      --skip-existing \\\n'

    # Call to python scripts for the rest of QC
    python_command = (
        f'\npython3 anat/qc_freesurfer.py '
        f"'{json.dumps(config)}' {','.join(subjects_sessions)}"
    )

    # Add permissions for shared ownership of the output directory
    ownership_sharing = f'\nchmod -Rf 771 {DERIVATIVES_DIR}/qc/freesurfer\n'

    # Write the complete BASH script to the specified file
    with open(path_to_script, 'w') as f:
        f.write(module_export + singularity_command + python_command + ownership_sharing)


def run(config, job_ids=None):
    """
    Runs the FreeSurfer Quality Control (QC) pipeline.

    This function sets up the necessary directories, generates a BASH script for QC processes,
    and submits the QC job to the system. The QC includes FreeSurfer outputs verification,
    volume normalization, and outlier detection. The job can be submitted with dependencies
    on other jobs if `job_ids` are provided.

    Parameters
    ----------
    config : dict
        Configuration dictionary containing paths and QC parameters.
    job_ids : list of str, optional
        List of job IDs that the current job depends on. The QC job will start only after these jobs are completed.

    Returns
    -------
    None
        The function sets up the QC pipeline and submits the job to the system.
    """

    """
    Run FreeSurfer QC
    Note that FSQC must run on interactive mode to be able to display (and save) graphical outputs
    """

    common = config["common"]
    fsqc = config["fsqc"]
    DERIVATIVES_DIR = common["derivatives"]

    # Create output (derivatives) directories
    os.makedirs(f"{DERIVATIVES_DIR}/qc/freesurfer", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/qc/freesurfer/outputs", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/qc/freesurfer/stdout", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/qc/freesurfer/scripts", exist_ok=True)
    os.makedirs(f"{DERIVATIVES_DIR}/qc/freesurfer/outliers", exist_ok=True)

    # List all subjects and sessions in FreeSurfer BIDS output directory
    subjects_sessions = utils.get_subjects(f"{DERIVATIVES_DIR}/freesurfer/outputs")

    path_to_script = f"{DERIVATIVES_DIR}/qc/freesurfer/scripts/qc_group.sh"
    generate_bash_script(config, subjects_sessions, path_to_script)

    cmd = (f'\nsrun --job-name=fsqc --ntasks=1 '
           f'--partition={fsqc["partition"]} '
           f'--mem={fsqc["requested_mem"]} '
           f'--time={fsqc["requested_time"]} '
           f'--out={DERIVATIVES_DIR}/qc/freesurfer/stdout/qc_freesurfer_%j.out '
           f'--err={DERIVATIVES_DIR}/qc/freesurfer/stdout/qc_freesurfer_%j.err ')

    if job_ids:
        cmd += f'--dependency=afterok:{":".join(job_ids)} '

    cmd += f'sh {path_to_script} &'

    os.system(cmd)
    print(f"[QC-FREESURFER] Submitting (background) task on interactive node\n")
    print(f"[QC-FREESURFER] - FSQC\n")
    print(f"[QC-FREESURFER] - Parcel Volume Normalization\n")
    print(f"[QC-FREESURFER] - Outlier Detection")
    return


if __name__ == "__main__":

    import sys
    config = json.loads(sys.argv[1])
    subjects_sessions = sys.argv[2].split(',')
    compute_metrics(config, subjects_sessions)
