import os
import re
from datetime import datetime
import pandas as pd
import utils


def extract_runtime(content):
    # Expression régulière pour capturer les timestamps
    timestamp_pattern = r"\d{6}-\d{2}:\d{2}:\d{2}"

    # Trouver tous les timestamps dans le fichier
    timestamps = re.findall(timestamp_pattern, content)

    if not timestamps:
        return 0

    # Convertir les timestamps en objets datetime
    first_timestamp = datetime.strptime(timestamps[0], "%y%m%d-%H:%M:%S")
    last_timestamp = datetime.strptime(timestamps[-1], "%y%m%d-%H:%M:%S")

    # Calculer le runtime
    runtime = last_timestamp - first_timestamp

    return runtime


def read_log(config, subject, session):

    finished_status = "Error"
    runtime = 0

    DERIVATIVES_DIR = config["common"]["derivatives"]
    stdout_dir = f"{DERIVATIVES_DIR}/qsiprep/stdout"

    # Check that QSIprep finished without error
    if not os.path.exists(stdout_dir):
        return finished_status, runtime

    prefix = f"qsiprep_{subject}_{session}"
    stdout_files = [f for f in os.listdir(stdout_dir) if (f.startswith(prefix) and f.endswith('.out'))]
    if not stdout_files:
        return finished_status, runtime

    for file in stdout_files:
        file_path = os.path.join(stdout_dir, file)
        with open(file_path, 'r') as f:
            content = f.read()
            if 'QSIPrep finished successfully!' in content:
                finished_status = "Success"
                try:
                    runtime = extract_runtime(content)
                except ValueError as e:
                    print(e)

    return finished_status, runtime


def generate_bash_script(config, subjects_sessions, path_to_script):

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
        f'\napptainer run \\\n'
        f'    --writable-tmpfs --cleanenv \\\n'
        f'    -B {DERIVATIVES_DIR}/freesurfer:/data:ro \\\n'
        f'    -B {DERIVATIVES_DIR}/qc/fsqc:/out \\\n'
        f'    {fsqc["fsqc_container"]} \\\n'
        f'      --subjects_dir /data \\\n'
        f'      --output_dir /out \\\n'
        f'      --subjects {subjects_sessions_str}  \\\n'
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
    ownership_sharing = f'\nchmod -Rf 771 {DERIVATIVES_DIR}/qc/fsqc\n'

    # Write the complete BASH script to the specified file
    with open(path_to_script, 'w') as f:
        f.write(module_export + singularity_command + python_command + ownership_sharing)


def run(config, subjects_sessions, job_ids=None):

    # todo: Check si QC + MRIQC processed (ligne dans le csv final ?)
    if is_already_processed(config, subject, session):
        return None

    DERIVATIVES_DIR = config["common"]["derivatives"]

    # Create output (derivatives) directories
    os.makedirs(f"{DERIVATIVES_DIR}/qc/qsiprep", exist_ok=True)
    # os.makedirs(f"{DERIVATIVES_DIR}/qc/qsiprep/stdout", exist_ok=True)
    # os.makedirs(f"{DERIVATIVES_DIR}/qc/qsiprep/scripts", exist_ok=True)
    # os.makedirs(f"{DERIVATIVES_DIR}/qc/qsiprep/outliers", exist_ok=True)

    path_to_script = f"{DERIVATIVES_DIR}/qc/qsiprep/scripts/qsiprep.slurm"
    generate_bash_script(config, subjects_sessions, path_to_script)

    # todo: Dans le script slurm :
    # - appeler MRIQC pour qsiprep individuel
    # - appeler python pour le calcul des autres métriques et combinaison des valeurs dans un tableau unique

    cols = ["subject",
            "session",
            "Finished without error",
            "Processing time (hours)",
            "Number of folders generated",
            "Number of files generated"]
    frames = []
    for sub_sess in subjects_sessions:
        subject = sub_sess.split('_')[0]
        session = sub_sess.split('_')[1]
        # todo: move read_log to utils
        finished_status, runtime = read_log(config, subject, session)
        dir_count = utils.count_dirs(f"{DERIVATIVES_DIR}/qsiprep/{subject}/{session}")
        file_count = utils.count_files(f"{DERIVATIVES_DIR}/qsiprep/{subject}/{session}")
        frames.append([subject, session, finished_status, runtime, dir_count, file_count])

        # Extract values, mean, max, std of metrics from qsiprep outputs :
        # - confounds_timeseries
        # - image_qc
        # put values in frames
    qc = pd.DataFrame(frames, columns=cols)

    path_to_qc = f"{DERIVATIVES_DIR}/qc/qsiprep/qc.csv"
    qc.to_csv(path_to_qc, index=False)

    print(f"QC saved in {path_to_qc}\n")

    print("QSIprep Quality Check terminated successfully.")

