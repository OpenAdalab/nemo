"""
Adapted from fsqc.outlierDetection.py (line 2726).
    Compute outliers for each subject compared to the sample for the following values :
    - aseg volumes normalized by ETIV
    - aparc cortical thickness
    - hypothalamus substructures volume (optional)
    - hippocampus and amygdala substructures volume (optional)
Modified parts are identified with ########. It concerns:
- The aseg.stats file which is read as a csv file instead of a dictionary (line 79)
- The morphometric values are saved in a dataframe (line 203)
"""

from fsqc.outlierDetection import readAparcStats, readHippocampusStats, readHypothalamusStats, outlierTable


# ------------------------------------------------------------------------------
# main function
def outlierDetection_normalized(
    subjects,
    subjects_dir_map,
    output_dir,
    outlierDict=None,
    min_no_subjects=10,
    hypothalamus=False,
    hippocampus=False,
    hippocampus_label=None,
    fastsurfer=False,
):
    """
    Evaluate outliers in aseg.stats, [lr]h.aparc, and optional hypothalamic/hippocampal values.

    Parameters
    ----------
    subjects : list
        List of subject IDs.
    subjects_dir : str
        Path to the FreeSurfer subjects directory.
    output_dir : str
        Path to the output directory for saving results.
    outlierDict : dict
        Dictionary containing outlier thresholds for different measures.
    min_no_subjects : int, optional
        Minimum number of subjects required for analysis.
    hypothalamus : bool, optional
        Flag to include hypothalamic values in the analysis.
    hippocampus : bool, optional
        Flag to include hippocampal values in the analysis.
    hippocampus_label : str or None, optional
        Label to identify the hippocampus (e.g., "Hippocampus").
    fastsurfer : bool, optional
        Flag to use FastSurfer instead of FreeSurfer output files.

    Returns
    -------
    tuple
        A tuple containing three dictionaries:

        - outlierSampleNonparNum
        - outlierSampleParamNum
        - outlierNormsNum
    """
    # imports

    import csv
    import os

    import numpy as np
    import pandas as pd

    # create a dictionary with all data from all subjects, and create a list of all available keys

    regions = dict()

    all_regions_keys = list()

    for subject in subjects:

        # aseg
        ########## MODIFIED TO READ A CSV FILE INSTEAD OF A DICTIONNARY  #########
        path_aseg_stats = os.path.join(subject_dir_map[subject], subject, "stats", "aseg_stats_norm.csv")
        # aseg_stats = readAsegStats(path_aseg_stats)
        aseg_stats = pd.read_csv(path_aseg_stats)
        aseg_stats = aseg_stats.to_dict(orient='records')[0]
        ##########################################################################
        regions[subject] = aseg_stats.copy()
        all_regions_keys.extend(list(aseg_stats.keys()))

        # aparc
        if fastsurfer is True:
            path_aparc_stats = os.path.join(
                subjects_dir, subject, "stats", "lh.aparc.DKTatlas.mapped.stats"
            )
        else:
            path_aparc_stats = os.path.join(
                subjects_dir, subject, "stats", "lh.aparc.stats"
            )
        aparc_header, aparc_stats, aparc_thickness = readAparcStats(
            path_aparc_stats, hemi="lh"
        )
        regions[subject].update(aparc_thickness)
        all_regions_keys.extend(list(aparc_thickness.keys()))

        if fastsurfer is True:
            path_aparc_stats = os.path.join(
                subject_dir_map[subject], subject, "stats", "rh.aparc.DKTatlas.mapped.stats"
            )
        else:
            path_aparc_stats = os.path.join(
                subject_dir_map[subject], subject, "stats", "rh.aparc.stats"
            )
        aparc_header, aparc_stats, aparc_thickness = readAparcStats(
            path_aparc_stats, hemi="rh"
        )
        regions[subject].update(aparc_thickness)
        all_regions_keys.extend(list(aparc_thickness.keys()))

        # hypothalamus

        if hypothalamus is True:
            path_hypothalamus_stats = os.path.join(
                subject_dir_map[subject], subject, "mri", "hypothalamic_subunits_volumes.v1.csv"
            )
            if os.path.exists(path_hypothalamus_stats):
                hypothalamus_stats = readHypothalamusStats(path_hypothalamus_stats)
                regions[subject].update(hypothalamus_stats)
                all_regions_keys.extend(list(hypothalamus_stats.keys()))

        # hippocampus + amygdala

        if hippocampus is True and hippocampus_label is not None:
            path_hippocampus_stats = os.path.join(
                subjects_dir,
                subject,
                "mri",
                "lh.hippoSfVolumes-" + hippocampus_label + ".txt",
            )
            if os.path.exists(path_hippocampus_stats):
                hippocampus_stats = readHippocampusStats(
                    path_hippocampus_stats, hemi="lh", prefix="hippocampus"
                )
                regions[subject].update(hippocampus_stats)
                all_regions_keys.extend(list(hippocampus_stats.keys()))

            path_hippocampus_stats = os.path.join(
                subject_dir_map[subject],
                subject,
                "mri",
                "rh.hippoSfVolumes-" + hippocampus_label + ".txt",
            )
            if os.path.exists(path_hippocampus_stats):
                hippocampus_stats = readHippocampusStats(
                    path_hippocampus_stats, hemi="rh", prefix="hippocampus"
                )
                regions[subject].update(hippocampus_stats)
                all_regions_keys.extend(list(hippocampus_stats.keys()))

            path_hippocampus_stats = os.path.join(
                subject_dir_map[subject],
                subject,
                "mri",
                "lh.amygNucVolumes-" + hippocampus_label + ".txt",
            )
            if os.path.exists(path_hippocampus_stats):
                hippocampus_stats = readHippocampusStats(
                    path_hippocampus_stats, hemi="lh", prefix="amygdala"
                )
                regions[subject].update(hippocampus_stats)
                all_regions_keys.extend(list(hippocampus_stats.keys()))

            path_hippocampus_stats = os.path.join(
                subject_dir_map[subject],
                subject,
                "mri",
                "rh.amygNucVolumes-" + hippocampus_label + ".txt",
            )
            if os.path.exists(path_hippocampus_stats):
                hippocampus_stats = readHippocampusStats(
                    path_hippocampus_stats, hemi="rh", prefix="amygdala"
                )
                regions[subject].update(hippocampus_stats)
                all_regions_keys.extend(list(hippocampus_stats.keys()))

    # sort keys

    all_regions_keys = set(all_regions_keys)

    all_regions_keys = (
            sorted(list(filter(lambda x: "aseg." in x, list(all_regions_keys))))
            + sorted(list(filter(lambda x: "aparc." in x, list(all_regions_keys))))
            + sorted(list(filter(lambda x: "hippocampus." in x, list(all_regions_keys))))
            + sorted(list(filter(lambda x: "amygdala." in x, list(all_regions_keys))))
            + sorted(list(filter(lambda x: "hypothalamus." in x, list(all_regions_keys))))
    )

    # compare individual data against sample statistics (if more than min_no_subjects cases)

    outlierSampleNonpar = dict()
    outlierSampleParam = dict()

    outlierSampleNonparNum = dict()
    outlierSampleParamNum = dict()

    ########### MODIFIED TO SAFE DATAFRAME WITH GROUP MORPHOMETRIC VALUES #################
    df = pd.DataFrame.from_dict(regions).transpose()
    # Put the subject's name in the first column
    df.index.name = "subject"
    ##########################################################################

    if len(subjects) >= min_no_subjects:
        # compute means, sd, medians, and quantiles based on sample
        iqr = np.percentile(df, 75, axis=0) - np.percentile(df, 25, axis=0)

        sample_nonpar_lower = dict(
            zip(df.columns, np.percentile(df, 25, axis=0) - 1.5 * iqr)
        )
        sample_nonpar_upper = dict(
            zip(df.columns, np.percentile(df, 75, axis=0) + 1.5 * iqr)
        )

        sample_param_lower = dict(np.mean(df, axis=0) - 2 * np.std(df, axis=0))
        sample_param_upper = dict(np.mean(df, axis=0) + 2 * np.std(df, axis=0))

        # compare individual data against sample statistics

        for subject in regions:
            nonparDict = dict()
            paramDict = dict()

            for key in regions[subject]:
                if (regions[subject][key] < sample_nonpar_lower[key]) or (
                        regions[subject][key] > sample_nonpar_upper[key]
                ):
                    nonparDict.update({key: True})
                else:
                    nonparDict.update({key: False})

                if (regions[subject][key] < sample_param_lower[key]) or (
                        regions[subject][key] > sample_param_upper[key]
                ):
                    paramDict.update({key: True})
                else:
                    paramDict.update({key: False})

            outlierSampleNonpar.update({subject: nonparDict})
            outlierSampleParam.update({subject: paramDict})

            outlierSampleNonparNum.update({subject: np.sum(list(nonparDict.values()))})
            outlierSampleParamNum.update({subject: np.sum(list(paramDict.values()))})

    else:
        for subject in regions:
            nonparDict = dict()
            paramDict = dict()

            for key in regions[subject]:
                nonparDict.update({key: np.nan})
                paramDict.update({key: np.nan})

            outlierSampleNonpar.update({subject: nonparDict})
            outlierSampleParam.update({subject: paramDict})

            outlierSampleNonparNum.update({subject: np.nan})
            outlierSampleParamNum.update({subject: np.nan})

    # compare individual data against normative values

    outlierNorms = dict()

    outlierNormsNum = dict()

    for subject in regions:
        normsDict = dict()

        for key in regions[subject]:
            # no prefixes in outlier table
            if key.startswith("aseg."):
                outlierKey = key.replace("aseg.", "")
            elif key.startswith("aparc."):
                outlierKey = key.replace("aparc.", "")
            elif key.startswith("hippocampus."):
                outlierKey = key.replace("hippocampus.", "")
            elif key.startswith("amygdala."):
                outlierKey = key.replace("amygdala.", "")
            elif key.startswith("hypothalamus."):
                outlierKey = key.replace("aseg.", "")

            if outlierKey in outlierDict:
                if (regions[subject][key] < outlierDict[outlierKey]["lower"]) or (
                        regions[subject][key] > outlierDict[outlierKey]["upper"]
                ):
                    normsDict.update({key: True})
                else:
                    normsDict.update({key: False})

            else:
                normsDict.update({key: np.nan})

        outlierNorms.update({subject: normsDict})

        outlierNormsNum.update({subject: np.nansum(list(normsDict.values()))})

    # write to csv files

    regionsFieldnames = ["subject"]
    regionsFieldnames.extend(all_regions_keys)

    with open(os.path.join(output_dir, "all.regions.stats.norm"), "w") as datafile:
        csvwriter = csv.DictWriter(
            datafile,
            fieldnames=regionsFieldnames,
            delimiter=",",
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL,
        )
        csvwriter.writeheader()
        for subject in sorted(list(regions.keys())):
            tmp = regions[subject]
            tmp.update({"subject": subject})
            csvwriter.writerow(tmp)

    with open(
            os.path.join(output_dir, "all.outliers.sample.nonpar.stats.norm"), "w"
    ) as datafile:
        csvwriter = csv.DictWriter(
            datafile,
            fieldnames=regionsFieldnames,
            delimiter=",",
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL,
        )
        csvwriter.writeheader()
        for subject in sorted(list(outlierSampleNonpar.keys())):
            tmp = outlierSampleNonpar[subject]
            tmp.update({"subject": subject})
            csvwriter.writerow(tmp)

    with open(
            os.path.join(output_dir, "all.outliers.sample.param.stats.norm"), "w"
    ) as datafile:
        csvwriter = csv.DictWriter(
            datafile,
            fieldnames=regionsFieldnames,
            delimiter=",",
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL,
        )
        csvwriter.writeheader()
        for subject in sorted(list(outlierSampleParam.keys())):
            tmp = outlierSampleParam[subject]
            tmp.update({"subject": subject})
            csvwriter.writerow(tmp)

    with open(os.path.join(output_dir, "all.outliers.norms.stats.norm"), "w") as datafile:
        csvwriter = csv.DictWriter(
            datafile,
            fieldnames=regionsFieldnames,
            delimiter=",",
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL,
        )
        csvwriter.writeheader()
        for subject in sorted(list(outlierNorms.keys())):
            tmp = outlierNorms[subject]
            tmp.update({"subject": subject})
            csvwriter.writerow(tmp)

    # return

    return df, outlierSampleNonparNum, outlierSampleParamNum, outlierNormsNum
