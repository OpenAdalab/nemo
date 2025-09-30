# Auteur: Lucile Hashimoto (Adalab) modified by Andréa Paysserand (INT)
# Date: 2025
import os
import glob
import csv
import re
import numpy as np
from config2 import FREESURFER_FSQC, FREESURFER_OUTPUTS

def extract_info_from_log(log_file):
    """
    Uses regex to extract information from the log file such as the runtime, the number of Euler number before and after topological correction
    """
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

def count_dirs_in_directory(directory):
    """
    Count the number of directories in a given directory (non-recursively)
    """
    return sum([1 for item in os.listdir(directory) if os.path.isdir(os.path.join(directory, item))])

def count_files_in_directory(directory):
    """
    Count the number of files in a given directory
    """
    return sum([len(files) for _, _, files in os.walk(directory)])

def check_log_and_generate_csv_multi(outputs_dirs, output_csv):
    """
    Scan recon-all log files for each subject in multiple freesurfer output directories and save information in a CSV file.
    """
    seen_subjects = set()
    with open(output_csv, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        # Set header
        writer.writerow([
            "Subject",
            "Number of folders generated",
            "Number of files generated",
            "Finished without error",
            "Processing time (hours)",
            "Euler number before topo correction LH",
            "Euler number after topo correction RH",
            "Euler number before topo correction LH",
            "Euler number after topo correction RH"
        ])
        for freesurfer_dir in outputs_dirs:
            subj_list = glob.glob(os.path.join(freesurfer_dir, "sub-*"))
            subj_list = [os.path.basename(x) for x in subj_list]
            for subj in subj_list:
                if subj in seen_subjects:
                    continue  # Skip duplicates
                seen_subjects.add(subj)
                log_file = os.path.join(freesurfer_dir, subj, "scripts", "recon-all.log")
                print(log_file)
                if os.path.exists(log_file):
                    info = extract_info_from_log(log_file)
                    dir_count = count_dirs_in_directory(os.path.join(freesurfer_dir, subj))
                    file_count = count_files_in_directory(os.path.join(freesurfer_dir, subj))
                    writer.writerow([subj, dir_count, file_count] + list(info))
                else:
                    print(f"Le fichier log pour le sujet {subj} n'existe pas dans {freesurfer_dir}.")

if __name__ == "__main__":
    # Ensure FREESURFER_OUTPUTS is a list
    outputs_dirs = FREESURFER_OUTPUTS if isinstance(FREESURFER_OUTPUTS, list) else [FREESURFER_OUTPUTS]
    output_csv = os.path.join(FREESURFER_FSQC, "check_log.csv")
    check_log_and_generate_csv_multi(outputs_dirs, output_csv)
    print(f"Logs information have been saved in {output_csv}.")
