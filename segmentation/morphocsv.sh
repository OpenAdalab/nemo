#Created by Andréa Paysserand 15/07/2025
#!/bin/bash
###########################################################
# Execute any FreeSurfer command using Singularity
# Usage: ./run_freesurfer_usefull_commands.sh <subject_id>
###########################################################

# Set the path to config.py
CONFIG_FILE="./config.py"
# Read paths from config.py and export them as environment variables
eval $(PYTHONPATH=$CONFIG_DIR python3 -c 'import config; config.print_paths()')

export SUBJECTS_DIR=$FREESURFER_OUTPUTS 
echo $SUBJECTS_DIR
export FREESURFER_DIR=$DIR_FREESURFER
echo $FREESURFER_DIR

subjects=$(ls $FREESURFER_DIR/outputs | grep -v fsaverage | tr '\n' ' ')
echo $subjects

## Extract aseg volumes (subcortical structures)
singularity exec -B $FREESURFER_DIR/outputs:/output -B $FREESURFER_DIR/license:/license \
  --env FS_LICENSE=/license/license.txt --env SUBJECTS_DIR=/output /scratch/lhashimoto/freesurfer-7.4.1.sif \
  bash -c "source /usr/local/freesurfer/SetUpFreeSurfer.sh && \
  asegstats2table --subjects $subjects --tablefile /output/aseg_volumes.csv"

## Extract cortical thickness (left hemisphere)
singularity exec -B $FREESURFER_DIR/outputs:/output -B $FREESURFER_DIR/license:/license \
  --env FS_LICENSE=/license/license.txt --env SUBJECTS_DIR=/output /scratch/lhashimoto/freesurfer-7.4.1.sif \
  bash -c "source /usr/local/freesurfer/SetUpFreeSurfer.sh && \
  aparcstats2table --subjects $subjects --hemi lh --meas thickness --tablefile /output/lh_thickness.csv"

## Extract cortical thickness (right hemisphere)
singularity exec -B $FREESURFER_DIR/outputs:/output -B $FREESURFER_DIR/license:/license \
  --env FS_LICENSE=/license/license.txt --env SUBJECTS_DIR=/output /scratch/lhashimoto/freesurfer-7.4.1.sif \
  bash -c "source /usr/local/freesurfer/SetUpFreeSurfer.sh && \
  aparcstats2table --subjects $subjects --hemi rh --meas thickness --tablefile /output/rh_thickness.csv"

## Extract cortical surface area (left hemisphere)
singularity exec -B $FREESURFER_DIR/outputs:/output -B $FREESURFER_DIR/license:/license \
  --env FS_LICENSE=/license/license.txt --env SUBJECTS_DIR=/output /scratch/lhashimoto/freesurfer-7.4.1.sif \
  bash -c "source /usr/local/freesurfer/SetUpFreeSurfer.sh && \
  aparcstats2table --subjects $subjects --hemi lh --meas area --tablefile /output/lh_area.csv"

## Extract cortical surface area (right hemisphere)
singularity exec -B $FREESURFER_DIR/outputs:/output -B $FREESURFER_DIR/license:/license \
  --env FS_LICENSE=/license/license.txt --env SUBJECTS_DIR=/output /scratch/lhashimoto/freesurfer-7.4.1.sif \
  bash -c "source /usr/local/freesurfer/SetUpFreeSurfer.sh && \
  aparcstats2table --subjects $subjects --hemi rh --meas area --tablefile /output/rh_area.csv"

## Extract cortical curvature (left hemisphere)
singularity exec -B $FREESURFER_DIR/outputs:/output -B $FREESURFER_DIR/license:/license \
  --env FS_LICENSE=/license/license.txt --env SUBJECTS_DIR=/output /scratch/lhashimoto/freesurfer-7.4.1.sif \
  bash -c "source /usr/local/freesurfer/SetUpFreeSurfer.sh && \
  aparcstats2table --subjects $subjects --hemi lh --meas meancurv --tablefile /output/lh_curv.csv"

## Extract cortical curvature (right hemisphere)
singularity exec -B $FREESURFER_DIR/outputs:/output -B $FREESURFER_DIR/license:/license \
  --env FS_LICENSE=/license/license.txt --env SUBJECTS_DIR=/output /scratch/lhashimoto/freesurfer-7.4.1.sif \
  bash -c "source /usr/local/freesurfer/SetUpFreeSurfer.sh && \
  aparcstats2table --subjects $subjects --hemi rh --meas meancurv --tablefile /output/rh_curv.csv"
