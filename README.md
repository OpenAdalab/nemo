# nemo


The `nemo` repository is designed to facilitate the pre- and post-processing of MR imaging data. It supports workflows 
for anatomical, diffusion, and functional MRI data, leveraging widely used neuroimaging tools and adhering to the BIDS 
(Brain Imaging Data Structure) format.

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
- **Quality Control (QC)**: Automated QC pipelines for each processing step and raw data.

## Prerequisites
### Software Requirements
- **Python**: Version 3.12 with the following libraries:
  - `toml`
  - `pandas`
  - `numpy`
  - `nibabel`
  - `scipy`
- **Singularity Containers**:
  - [FreeSurfer 7.4.1](https://hub.docker.com/r/freesurfer/freesurfer)
  - [fsqc 2.1.4](https://hub.docker.com/r/deepmi/fsqcdocker)
  - [QSIPrep 1.1.1](https://hub.docker.com/r/pennlinc/qsiprep/)
  - [QSIRecon 1.1.1](https://hub.docker.com/r/pennlinc/qsirecon/)
  - [fMRIPrep 25.2.2](https://hub.docker.com/r/nipreps/fmriprep) (or >25.2.0) LTS
  - [XCP-D 0.12.0](https://hub.docker.com/r/pennlinc/xcp_d/)
  - [MRIQC 24.0.2](https://hub.docker.com/r/nipreps/mriqc/)

To setup the environment do
````commandline
module load userspace/all
module load python3/3.12.0
python3.12 -m venv /path/to/env/
source /path/to/env/bin/activate
cd /path/to/this/repository/
pip3 install -r requirements.txt
````
or
````commandline
pip3 install numpy==2.2.1 pandas==2.2.3 scipy==1.15.0 nibabel==5.3.2 toml
````

To pull container images, please adapt the `config/containers.toml` configuration file and run the following command
````commandline
python3 pull_singularity_images.py --config config/containers.toml
````
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
- Workflow parameters.
- SLURM job parameters for each container.

Each container also has its own specific configuration file located in the config/ directory, which must be reviewed 
and adjusted before running the workflow.

## Usage
1. **Prepare the Configuration File**:
   - Update `config/config.toml` with the appropriate paths, subjects, sessions, slurm options and workflow options.
   Note that some arguments are set in this file that cannot be set into the container-specific configuration files.
   - Review and customize the container-specific configuration files in the `config/` directory if needed.
   Note that suggested arguments have been adapted to the MR protocol defined above. 
   Make sure to keep the original copy of the default config files.

2. **Activate the Python Environment**:

From the connection front (no need to connect to a node)
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
processing each step in batch mode (except for the Freesurfer QC as well as some additional Python processes 
for QC which run in interactive mode as background tasks).\
The configuration is automatically saved with datetime.\
Scripts are generated and saved for each subject/session.\
Steps are scheduled according to a predefined order, 
and dependencies between steps are managed automatically by SLURM to ensure proper execution.\
At the beginning of each step a sanity check verifies that the previous step terminated successfully.\
Intermediate files are saved in a 'work' directory. This folder can be deleted manually to save disk space.

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

## Notes

- **Anatomical Processing**: The `recon-all` algorithm is used for segmentation due to its proven reliability and ability to 
leverage T2-weighted images for improved surface reconstruction.
- **Diffusion Processing**: Runtime may vary depending on available resources and can ba hard to predict. 
Errors may occur  which are not handle properly and nypipe just continues to hang indefinitely. 
In that case, it is recommended to stop the job and re-run it. For that reason, 
it is essential to keep intermediate files until the process has finished successfully.
- **Functional Processing**: Ensure that only resting-state fMRI tasks are processed and that the BIDS dataset 
and filter files are consistent.
- **QC**: Group-level MRIQC requires all subject-level results to be aggregated in the same folder. 
A few additional QC indicators are extracted for each type of derivatives, such as Status, runtime duration, etc. 

For more details about each pipeline, refer to their respective documentation:
- [FreeSurfer](https://surfer.nmr.mgh.harvard.edu/)
- [fsqc](https://github.com/Deep-MI/fsqc)
- [QSIprep](https://qsiprep.readthedocs.io/)
- [QSIrecon](https://qsirecon.readthedocs.io/)
- [fMRIPrep](https://fmriprep.org/)
- [XCP-D](https://xcp-d.readthedocs.io/)
- [MRIQC](https://mriqc.readthedocs.io/)

## License
This repository is distributed under the Eclipse License. See LICENSE for details.
