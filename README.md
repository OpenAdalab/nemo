# nemo


The `nemo` repository is designed to facilitate the pre- and post-processing of MR imaging data. It supports workflows for anatomical, diffusion, and functional MRI data, leveraging widely used neuroimaging tools and adhering to the BIDS (Brain Imaging Data Structure) format.

## Supported MR Protocols
The repository is tailored for MR data acquired with the following sequences:
- T1-weighted (1.0x1.0x1.0 mm³)
- T2-weighted (1.0x1.0x1.0 mm³)
- Diffusion-weighted imaging (DWI) with AP/PA phase encoding (1.8x1.8x1.8 mm³, 109 volumes)
- Resting-state functional MRI (rs-fMRI)
- B0 Fieldmaps

Data are considered as cross-sectional.\
Multiple sessions are possible.

## Repository Features
- **Anatomical Processing**: Segmentation using FreeSurfer.
- **Diffusion Processing**: Structural connectome estimation using QSIprep and QSIrecon.
- **Functional Processing**: Functional connectome estimation using fMRIPrep and XCP-D.
- **Quality Control (QC)**: Automated QC pipelines for each processing step.

## Prerequisites
### Software Requirements
- **Python**: Version 3.12 with the following libraries:
  - `toml`
  - `pandas`
  - `numpy`
  - `nibabel`
  - `scipy`
- **Singularity Containers**:
  - FreeSurfer 7.4.1
  - fsqc 2.1.4
  - QSIprep 1.0.2
  - QSIrecon 1.1.1
  - fMRIPrep 25.2.2 (or 25.2.0 lts)
  - XCP-D 0.12.0
  - MRIQC 24.0.2

### Data Organization
Raw data must follow the BIDS format. Example structure:
```
dataset/\
├─ sub-01/\
│  ├─ ses-01/\
│  │  ├─ anat/\
│  │  │  ├─sub-01_ses-01_T1w.nii.gz\
│  │  │  ├─sub-01_ses-01_T2w.nii.gz\
│  │  ├─ dwi/\
│  │  │  ├─sub-01_ses-01_dir-AP_run-01_dwi.nii.gz\
│  │  │  ├─sub-01_ses-01_dir-AP_run-01_dwi.bval\
│  │  │  ├─sub-01_ses-01_dir-AP_run-01_dwi.bvec\
│  │  │  ├─sub-01_ses-01_dir-PA_run-01_dwi.nii.gz\
│  │  │  ├─sub-01_ses-01_dir-PA_run-01_dwi.bval\
│  │  │  └─sub-01_ses-01_dir-PA_run-01_dwi.bvec\
│  │  ├─ fmap/\
│  │  │  ├─sub-01_ses-01_dir-AP_epi.nii.gz\
│  │  │  └─sub-01_ses-01_dir-PA_epi.nii.gz\
│  │  └─ func/\
│  │  │  ├─sub-01_ses-01_task-rest_bold.nii.gz\
│  │  │  └─sub-01_ses-01_task-rest_sbref.nii.gz\
```

## Configuration
The repository uses a centralized configuration file (`config/config.toml`) to define:
- Paths to input/output directories.
- List of subjects and sessions to process.
- Workflow steps to execute.
- SLURM job parameters for each container.

## Usage
1. **Prepare the Configuration File**:
   - Update `config/config.toml` with the appropriate paths, subjects, sessions, slurm options and workflow options.
   Note that some arguments are set in this file that cannot be set into the container-specific configuration files.
   - Review and customize the container-specific configuration files in the `config/` directory if needed.
   Note that suggested arguments have been adapted to the MR protocol defined above. 
   Make sure to keep the original copy of the default config files.

2. **Activate the Python Environment**:
   ```bash
   module load userspace/all
   module load python3/3.12.0
   source /path/to/your/python/virtual/env/bin/activate
   ```
3. Run the workflow: 
```
python3 run_workflow.py --config /path/to/your/config.toml
```
The workflow will submit jobs to the SLURM scheduler, 
processing each step in batch mode (except for the Freesurfer QC which runs 
in interactive mode as a background task).\
The configuration is automatically saved with datetime.\
Scripts are generated and saved for each subject/session.\
Steps are scheduled according to a predefined order, 
and dependencies between steps are managed automatically by SLURM to ensure proper execution.\
At the beginning of each step a sanity check verifies that the previous step terminated successfully.

## Outputs
Processed data will be saved in the derivatives/ directory, organized by pipeline:
```
derivatives/
├─ freesurfer/
├─ qsiprep/
├─ qsirecon/
├─ fmriprep/
├─ xcpd/
└─ qc/
```
Intermediate files are saved in a 'work' directory. This folder can be deleted manually to save disk space.

## Notes

Some tips and explanations can be found bellow.
However, for more details about each pipeline, refer to their respective documentation:
- [FreeSurfer](https://surfer.nmr.mgh.harvard.edu/)
- [fsqc](https://github.com/Deep-MI/fsqc)
- [QSIprep](https://qsiprep.readthedocs.io/)
- [QSIrecon](https://qsirecon.readthedocs.io/)
- [fMRIPrep](https://fmriprep.org/)
- [XCP-D](https://xcp-d.readthedocs.io/)
- [MRIQC](https://mriqc.readthedocs.io/)


### anat
Choice has been made to use "recon-all" for anatomical segmentation. The reason is that results have been proven 
to be of good quality in many studies, while CNN-versions of FastSurfer are quite new.
Also, this historical algorithm uses the T2 contrast to improve white and pial surface reconstruction, which can be 
crucial on infant data.

### dwi
Runtime is hardly predictable, as several jobs are ran in parallel. Each job starts as soon as previous jobs are 
finished and the individual runtime depends on the number of available processors at that moment.

In some cases, errors occur which are not handle properly and nypipe just continues to hang indefinitely. 
In that case, it is recommended to stop the job and re-run it (sometimes several times). For that reason, 
it is essential to save intermediate files on disk.

## func
Sequence filtering : keep only resting state fMRI tasks for the processing. Make sure your BIDS dataset is well organized, and also that the bids_filter file is in accordance with your dataset (especially the task name).

A few additional parameters have been set in the config files. Beware that the parameters used in command line will overwrite those defined in the config files and that some parameters are mandatory in command line (like the output spaces).

MRIQC can be ran both on a subject-session and group level. However, the group level MRIQC expects the folder containing all the MRIQC derivatives from subject-session level jobs, overwise, it will return a "no data found" error. And all it does is aggregate the subject-level results. 

## QC
A few QC indicators are extracted for each type of derivatives, such as Status, runtime duration, etc. 
These are additional parameters, but be sure to also check the MRIQC outputs for each derivatives. 

**File system**
Data must be organized according to the BIDS format (https://bids.neuroimaging.io/index.html). The derivatives are also organized according to the BIDS derivatives specification. An example of the expected file structure is given below:

dataset/
├─ derivatives/
│  ├─ freesurfer
│  │  ├─ sub-01/
│  │  │  ├─ ses-01/
│  │  │  │  ├─ label/
│  │  │  │  ├─ mri/
│  │  │  │  ├─ surf/
│  ├─ fsqc
│  │  ├─ fornix/
│  │  ├─ metrics/
│  │  ├─ screenshots/
│  │  │  ├─ sub-01/
│  ├─ sub-01/ (contient tous les derivatives des BIDS app ? ou alors séparés ? Oui ça permet de tester plusieurs versions pour chaque container)
│  │  ├─ anat/ (average across sessions)
│  │  ├─ figures/
│  │  ├─ log/
│  │  ├─ ses-01/
│  │  │  ├─ anat/
│  │  │  ├─ dwi/
│  │  │  ├─ fmap/
│  │  │  └─ func/


project/
├── config/
│   ├── config.json                # Fichier de configuration général
│   ├── freesurfer_config.json     # Configuration spécifique à FreeSurfer
│   ├── qsiprep_config.json        # Configuration spécifique à QSIprep
│   ├── qsirecon_config.json       # Configuration spécifique à QSIrecon
│   ├── fmriprep_config.json       # Configuration spécifique à fMRIPrep
│   ├── xcpd_config.json           # Configuration spécifique à XCP-D
│   └── qc_config.json             # Configuration spécifique au QC
├── scripts/
│   ├── run_freesurfer.py          # Script principal pour FreeSurfer
│   ├── run_qsiprep.py             # Script principal pour QSIprep
│   ├── run_qsirecon.py            # Script principal pour QSIrecon
│   ├── run_fmriprep.py            # Script principal pour fMRIPrep
│   ├── run_xcpd.py                # Script principal pour XCP-D
│   ├── qc_freesurfer.py           # QC pour FreeSurfer
│   ├── qc_qsiprep.py              # QC pour QSIprep
│   ├── qc_qsirecon.py             # QC pour QSIrecon
│   ├── qc_fmriprep.py             # QC pour fMRIPrep
│   ├── qc_xcpd.py                 # QC pour XCP-D
│   └── qc_group.py                # QC de groupe final
├── utils/
│   ├── __init__.py                # Initialisation du module utils
│   ├── slurm_utils.py             # Fonctions utilitaires pour soumettre des jobs SLURM
│   ├── file_utils.py              # Fonctions pour gérer les fichiers et dossiers
│   ├── config_utils.py            # Fonctions pour charger et gérer les configurations
│   └── qc_utils.py                # Fonctions utilitaires pour les étapes de QC
├── logs/                          # Dossier pour les fichiers de log
│   ├── freesurfer/
│   ├── qsiprep/
│   ├── qsirecon/
│   ├── fmriprep/
│   ├── xcpd/
│   └── qc/
├── outputs/                       # Dossier pour les résultats finaux
│   ├── freesurfer/
│   ├── qsiprep/
│   ├── qsirecon/
│   ├── fmriprep/
│   ├── xcpd/
│   └── qc/
└── main_workflow.py               # Script principal pour exécuter tout le workflow
```