import toml
import os
import subprocess
import re
import numpy as np
from venv import logger
from datetime import datetime
from pathlib import Path
import nibabel as nib
import warnings
import json
warnings.filterwarnings("ignore")


def load_config(config_file):
    """Load arguments from a JSON config file."""
    if not os.path.exists(config_file):
        return {}
    with open(config_file, "r") as f:
        return toml.load(f)


def get_subjects(input_dir, specified_subjects=None):
    """
    Retrieve the list of subjects from the input directory or use the specified list.

    Parameters
    ----------
    input_dir : str
        Path to the input directory containing the dataset in BIDS format.
    specified_subjects : list or None
        List of subjects to process. If None, all subjects in the input directory are retrieved.

    Returns
    -------
    list
        List of subjects.
    """
    if specified_subjects:
        return [f"sub-{sub}" if not sub.startswith("sub-") else sub for sub in specified_subjects]

    return sorted(
        d for d in os.listdir(input_dir) if d.startswith("sub-") and os.path.isdir(os.path.join(input_dir, d)))


def get_sessions(input_dir, subject, specified_sessions=None):
    """
    Retrieve the list of sessions for a given subject or use the specified list.

    Parameters
    ----------
    input_dir : str
        Path to the input directory containing the dataset in BIDS format.
    subject : str
        Subject identifier (e.g., "sub-01").
    specified_sessions : list or None
        List of sessions to process. If None, all sessions in the subject directory are retrieved.

    Returns
    -------
    list
        List of sessions.
    """
    subject_path = os.path.join(input_dir, subject)
    if specified_sessions:
        return [f"ses-{ses}" if not ses.startswith("ses-") else ses for ses in specified_sessions]

    return sorted(
        d for d in os.listdir(subject_path) if d.startswith("ses-") and os.path.isdir(os.path.join(subject_path, d)))


def get_tasks(session):
    """
    Load the list of BIDS tasks for a given session from a JSON bids filter.

    Parameters
    ----------
    session : str
        Session identifier used to build the bids filter filename; the function
        will look for `bids_filters/bids_filter_{session}.json` next to this file.

    Returns
    -------
    list
        List of task names (strings). If the JSON contains a single string the
        function converts it to a list.

    Notes
    -----
    Expects the JSON structure to contain a `bold` key with a `task` field,
    for example: {"bold": {"task": "rest"}} or {"bold": {"task": ["rest", "task2"]}}.
    """
    # Read bids_filter file to get the list of tasks to consider
    bids_filter_path = Path(__file__).resolve().parent / "bids_filters" / f"bids_filter_{session}.json"
    if not bids_filter_path.is_file():
        raise FileNotFoundError(f"BIDS filter file {bids_filter_path} not found.")
    with open(bids_filter_path, 'r') as f:
        bids_filter_content = json.load(f)
    tasks = bids_filter_content["bold"]["task"]
    # Convert a single string into a list
    if isinstance(tasks, str):
        tasks = [tasks]
    return tasks


def subject_exists(input_dir, subject):
    """
    Check if the subject directory exists in the input directory.

    """
    return (Path(input_dir) / subject).exists()


def has_anat(input_dir, subject):
    """
    Check if the subject has anatomical data.

    """
    return any((Path(input_dir) / subject).glob("**/anat/*T1w.nii*"))


def has_dwi(input_dir, subject):
    """
    Check if the subject has diffusion-weighted imaging (DWI) data.

    """
    return any((Path(input_dir) / subject).glob("**/dwi/*dwi.nii*"))


def has_func_fmap(input_dir, subject):
    """
    Check if the subject has functional MRI data along with field maps.

    """
    return any((Path(input_dir) / subject).glob("**/func/*bold.nii*")) and any(
        (Path(input_dir) / subject).glob("**/fmap/*"))


def submit_job(cmd):
    """
    Submits a SLURM job using the provided command and returns the job ID.

    Parameters
    ----------
    cmd : str
        The command to submit the SLURM job, typically using `sbatch`.

    Returns
    -------
    str or None
        The SLURM job ID if the submission is successful, or None if the submission fails.

    Notes
    -----
    - The function executes the `sbatch` command using the `subprocess.run` method.
    - It captures the output of the command to extract the job ID.
    - If the command fails or the job ID cannot be extracted, the function returns None.
    - The function prints messages to indicate the success or failure of the job submission.
    """
    try:
        # Execute the sbatch command and capture the output
        result = subprocess.run(cmd, shell=True, check=True, text=True, capture_output=True)
        output = result.stdout.strip()

        # Parse the output to extract the job ID
        if output.startswith("Submitted batch job"):
            job_id = output.split()[-1]
            print(f"SLURM job successfully submitted: ID {job_id}")
            return job_id
        else:
            print("Unable to retrieve the SLURM job ID.")
            return None
    except subprocess.CalledProcessError as e:
        # Handle errors during the job submission process
        print(f"Error while submitting the SLURM job: {e}")
        return None


def count_dirs(directory):
    """
    Count the number of directories recursively inside the given directory

    """
    if not os.path.isdir(directory):
        return 0
    return sum(len(dirs) for _, dirs, _ in os.walk(directory))


def count_files(directory):
    """
    Count the number of files recursively inside the given directory

    """
    if os.path.isdir(directory):
        return sum([len(files) for _, _, files in os.walk(directory)])
    else:
        return 0


def extract_runtime(content):
    """
    Extract runtime (in hours) from log file content.

    Searches for timestamps matching the pattern ``YYMMDD-HH:MM:SS`` inside the given
    text, parses the first and last occurrences, and returns the elapsed time in hours.

    Parameters
    ----------
    content : str
        Log file content as a single string.

    """
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
    runtime_hours = runtime.total_seconds() / 3600.0  # Convert in hours

    return runtime_hours


def read_log(config, subject, session, runtype):
    """
    Read SLURM stdout log(s) for a given subject/session/runtype and determine
    whether the pipeline finished successfully and how long it ran.

    Parameters
    ----------
    config : dict
        Configuration dictionary containing at least the key
        `config["common"]["derivatives"]` pointing to the derivatives' directory.
    subject : str
        Subject identifier (e.g. "sub-01").
    session : str
        Session identifier (e.g. "ses-01").
    runtype : str
        Pipeline name used to build stdout filename prefix (e.g. "fmriprep",
        "xcpd", "qsiprep", "qsirecon", "mriqc").

    Returns
    -------
    tuple
        A tuple (finished_status, runtime_hours):
        - finished_status : str
            "Success" if the expected success string is found in any matching
            stdout file, otherwise "Error".
        - runtime_hours : float
            Elapsed runtime in hours extracted from the first and last
            timestamp occurrences in the log (0 if not found or on error).
    """
    finished_status = "Error"
    runtime = 0

    DERIVATIVES_DIR = config["common"]["derivatives"]
    stdout_dir = f"{DERIVATIVES_DIR}/{runtype}/stdout"

    # Check that 'runtype' finished without error
    if not os.path.exists(stdout_dir):
        return finished_status, runtime

    prefix = f"{runtype}_{subject}_{session}"
    stdout_files = [f for f in os.listdir(stdout_dir) if (f.startswith(prefix) and f.endswith('.out'))]
    if not stdout_files:
        return finished_status, runtime

    if runtype == "fmriprep":
        success_string = "fMRIPrep finished successfully"
    elif runtype == "xcpd":
        success_string = "XCP-D finished successfully"
    elif runtype == "qsiprep":
        success_string = "QSIPrep finished successfully"
    elif runtype == "qsirecon":
        success_string = "QSIRecon finished successfully"
    elif runtype == "mriqc":
        success_string = "MRIQC finished successfully"
    else:
        success_string = 'finished successfully'

    for file in stdout_files:
        file_path = os.path.join(stdout_dir, file)
        with open(file_path, 'r') as f:
            content = f.read()
            if success_string in content:
                finished_status = "Success"
                try:
                    runtime = extract_runtime(content)
                except ValueError as e:
                    print(e)

    return finished_status, runtime


def load_any_image(path: Path) -> np.ndarray:
    """
    Load an image with nibabel, handling both NIfTI and GIFTI formats.

    Parameters
    ----------
    path : Path
        Path to the .nii(.gz) or .gii file.

    Returns
    -------
    img : nibabel image object
        Loaded image object.
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    img = nib.load(str(path))  # type: ignore

    if isinstance(img, nib.gifti.gifti.GiftiImage):
        logger.info(f"Detected GIFTI surface file: {path.name}")
    elif isinstance(img, (nib.Nifti1Image, nib.Nifti2Image)):  # type: ignore
        logger.info(f"Detected NIfTI volumetric file: {path.name}")
    else:
        raise TypeError(f"Unsupported file type: {type(img)}")

    return img


def dice(a, b):
    """
    Compute dice similarity coefficient between two binary masks.

    Parameters
    ----------
    a : np.ndarray
        First binary mask array.
    b : np.ndarray
        Second binary mask array.

    Returns
    -------
    float
        Dice similarity coefficient.
    """
    a = a.astype(bool)
    b = b.astype(bool)
    inter = np.logical_and(a, b).sum()
    s = a.sum() + b.sum()
    return (2 * inter / s) if s > 0 else np.nan


def resample(low_res_image, high_res_image):
    """
    Resample a lower-resolution 3D image to match the shape of a higher-resolution image.

    Parameters
    ----------
    low_res_image : numpy.ndarray
        Source image array to be resampled (expected 3D).
    high_res_image : numpy.ndarray
        Reference image whose shape defines the target voxel grid.

    Returns
    -------
    numpy.ndarray
        Resampled image with the same shape as `high_res_image`.
    """
    from scipy.ndimage import zoom

    target_shape = high_res_image.shape  # Cible : la résolution de l'image de plus haute résolution

    # Calculer les facteurs de zoom pour chaque dimension
    zoom_factors = [target_shape[i] / low_res_image.shape[i] for i in range(3)]

    # Rééchantillonner image1 pour qu'elle ait la même taille que image2
    return zoom(low_res_image, zoom_factors, mode='nearest')


def mutual_information(image1, image2, bins=64):
    """
    Compute mutual information (in bits) between two images.

    Parameters
    ----------
    image1 : numpy.ndarray
        First input image. Values will be normalized to the range [0, 1]
        using the image's own min/max.
    image2 : numpy.ndarray
        Second input image. Must be comparable to image1 (same shape is typical).
    bins : int, optional
        Number of bins used to estimate the joint histogram (default 64).

    Returns
    -------
    float
        Estimated mutual information (log base 2). If histograms are degenerate
        (e.g. constant images) the computed value may be 0. Note that the
        function normalizes each image by (max - min) without guarding against
        zero range; calling code should ensure inputs are not constant or handle
        the potential division by zero.
    """
    # Normaliser les images entre 0 et 1
    image1 = (image1 - image1.min()) / (image1.max() - image1.min())
    image2 = (image2 - image2.min()) / (image2.max() - image2.min())

    # Aplatir les images 3D en 1D
    flat_image1 = image1.ravel()
    flat_image2 = image2.ravel()

    # Calculer l'histogramme conjoint
    joint_hist, _, _ = np.histogram2d(flat_image1, flat_image2, bins=bins, range=[[0, 1], [0, 1]])

    # Calculer les histogrammes marginaux
    hist1, _ = np.histogram(flat_image1, bins=bins, range=[0, 1])
    hist2, _ = np.histogram(flat_image2, bins=bins, range=[0, 1])

    # Normaliser les histogrammes
    joint_hist = joint_hist / joint_hist.sum()
    hist1 = hist1 / hist1.sum()
    hist2 = hist2 / hist2.sum()

    # Calculer l'information mutuelle
    mi = 0
    for i in range(bins):
        for j in range(bins):
            if joint_hist[i, j] > 0 and hist1[i] > 0 and hist2[j] > 0:
                mi += joint_hist[i, j] * np.log2(joint_hist[i, j] / (hist1[i] * hist2[j]))

    return mi
