import csv
import os
import pandas as pd
from fsqc.outlierDetection import readAsegStats, readAparcStats
from outlierDetection2 import outlierDetection_normalized, outlierTable
from config2 import FREESURFER_FSQC, FREESURFER_OUTPUTS, DIR_FREESURFER


def load_fsqc_results(fsqc_results_path):
    return pd.read_csv(fsqc_results_path)


def load_check_log(check_log_path):
    df_check_log = pd.read_csv(check_log_path)
    return df_check_log.rename(columns={"Subject": "subject"})


def merge_dataframes(df1, df2):
    return pd.merge(df1, df2, on="subject", how="left")


def convert_radians_to_degrees(df):
    """
    Convert radians to degrees for rotation angles.
    Save results in new columns.
    """
    df["rot_tal_x_deg"] = df["rot_tal_x"].apply(lambda x: x * 180 / 3.14159)
    df["rot_tal_y_deg"] = df["rot_tal_y"].apply(lambda x: x * 180 / 3.14159)
    df["rot_tal_z_deg"] = df["rot_tal_z"].apply(lambda x: x * 180 / 3.14159)
    return df


def normalize_aseg_volumes(subjects, subject_dir_map, columns_to_exclude, columns_to_skip):
    """
    Extract ETIV value for each subject.
    Normalize ASEG volumes by EstimatedTotalIntraCranialVol and save it in a csv file.

    :param subjects:
    :param subjects_dir:
    :param columns_to_exclude: columns that are not volumes
    :param columns_to_skip: basically ETIV column and other columns to merge in the final dataframe
    :return:
    """
    df_etiv = pd.DataFrame()
    for subject in subjects:
        path_aseg_stats = os.path.join(subject_dir_map[subject], subject, "stats", "aseg.stats")
        aseg_stats = readAsegStats(path_aseg_stats)
        df_aseg = pd.DataFrame([aseg_stats])
        df_subj = pd.DataFrame()
        df_subj['subject'] = [subject]
        df_subj[columns_to_skip] = df_aseg[columns_to_skip]
        df_etiv = pd.concat([df_etiv, df_subj])
        df_aseg_norm = df_aseg.copy()
        df_aseg_norm = df_aseg_norm.drop(columns=columns_to_exclude)
        df_aseg_norm = df_aseg_norm.drop(columns=columns_to_skip)
        df_aseg_norm = df_aseg_norm.div(df_aseg['aseg.EstimatedTotalIntraCranialVol'], axis=0)
        df_aseg_norm.to_csv(os.path.join(subjects_dir_map[subject], subject, "stats", "aseg_stats_norm.csv"), index=False)
    return df_etiv


def calculate_outliers(subjects, subject_dir_map, outlier_outdir, outlier_params):
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

    :param subjects:
    :param subjects_dir:
    :param outlier_outdir:
    :param outlier_params:
    :return:
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
        subjects,
        subjects_dir_map,
        outlier_outdir,
        outlierDict,
        min_no_subjects=outlier_params['min_no_subjects'],
        hypothalamus=outlier_params['hypothalamus'],
        hippocampus=outlier_params['hippocampus'],
        hippocampus_label=outlier_params['hippocampus_label'],
        fastsurfer=outlier_params['fastsurfer'],
    )

    # create a dictionary from outlier module output
    outlierDict = dict()
    for subject in subjects:
        outlierDict.update(
            {
                subject: {
                    "n_outlier_sample_nonpar_normalized": n_outlier_sample_nonpar[subject],
                    "n_outlier_sample_param_normalized": n_outlier_sample_param[subject],
                    # "n_outlier_norms": n_outlier_norms[subject],  # valeurs de référence non normalisées par ETIV
                }
            }
        )

    # Convert outlierDict into a dataframe
    df_outliers = pd.DataFrame(outlierDict).T.reset_index()
    df_outliers = df_outliers.rename(columns={'index': 'subject'})

    return df_group_stats, n_outlier_sample_nonpar, n_outlier_sample_param, n_outlier_norms


if __name__ == "__main__":
 # Find all subjects and their parent directories
    subjects = []
    subject_dir_map = {}
    for parent_dir in FREESURFER_OUTPUTS:
        for subj in os.listdir(parent_dir):
            subj_path = os.path.join(parent_dir, subj)
            if os.path.isdir(subj_path):
                subjects.append(subj)
                subject_dir_map[subj] = parent_dir
    fsqc_results_path = os.path.join(FREESURFER_FSQC, "fsqc-results.csv")
    check_log_path = os.path.join(DIR_FREESURFER, "check_log.csv")
    group_statistics_path = os.path.join(FREESURFER_FSQC, "group_stats.csv")
    fsqc_complete_path = os.path.join(FREESURFER_FSQC, "fsqc-results-complete.csv")
    subjects_dir = FREESURFER_OUTPUTS
    outliers_dir = os.path.join(FREESURFER_FSQC, "outliers")
    outlier_params = {
        'min_no_subjects': 5,
        'hypothalamus': False,
        'hippocampus': False,
        'hippocampus_label': None,
        'fastsurfer': False,
        'outlierDict': None
    }
    columns_to_exclude = ['aseg.BrainSegVol_to_eTIV', 'aseg.MaskVol_to_eTIV', 'aseg.lhSurfaceHoles',
                          'aseg.rhSurfaceHoles', 'aseg.SurfaceHoles']
    columns_to_skip = ['aseg.EstimatedTotalIntraCranialVol']

    # Load FSQC results
    df_fsqc = load_fsqc_results(fsqc_results_path)
    # Load log check results
    df_check_log = load_check_log(check_log_path)
    # Merge dataframes
    df = merge_dataframes(df_fsqc, df_check_log)
    # Convert radians to degrees
    df = convert_radians_to_degrees(df)
    # Normalize ASEG volumes by ETIV
    subjects = df['subject'].tolist()
    df_etiv = normalize_aseg_volumes(subjects, subjects_dir_map, columns_to_exclude, columns_to_skip)
    # Calculate outliers and save new group aparc/aseg statistics
    df_group_stats, df_outliers = calculate_outliers(subjects, subjects_dir_map, outliers_dir, outlier_params)
    df_group_stats.reset_index(inplace=True)
    df_group_stats.to_csv(group_statistics_path, index=False)
    # Merge QC dataframes
    df = merge_dataframes(df, df_etiv)
    df = merge_dataframes(df, df_outliers)
    df.to_csv(fsqc_complete_path, index=False)
    print(f"Fichier {fsqc_complete_path} généré avec succès.")

