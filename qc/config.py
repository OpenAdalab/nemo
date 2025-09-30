DIR_INPUTS = "/scratch/lhashimoto/nemo_database/imaging_data"
DIR_FREESURFER = "/scratch/apaysserand/freesurfer"
FREESURFER_STDOUT = DIR_FREESURFER + "/stdout"
FREESURFER_OUTPUTS = DIR_FREESURFER + "/outputs"
FREESURFER_FSQC = DIR_FREESURFER + "/fsqc"

def print_paths():
    """
    Print paths to have access to them in a shell script
    """
    paths = {
        "DIR_INPUTS": DIR_INPUTS,
        "DIR_FREESURFER": DIR_FREESURFER,
        "FREESURFER_STDOUT": FREESURFER_STDOUT,
        "FREESURFER_OUTPUTS": FREESURFER_OUTPUTS
    }
    for key, value in paths.items():
        print(f"{key}={value}")

if __name__ == "__main__":
    print_paths()
