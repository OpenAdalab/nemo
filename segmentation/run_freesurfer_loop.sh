#!/bin/bash
###########################################################
# Execute FreeSurfer segmentation with T1 and T2 only on selected cases using Singularity
# Usage: ./run_freesurfer_selectedcases.sh
###########################################################

# Set the path to config.py
CONFIG_FILE="./config.py"
# Read paths from config.py and export them as environment variables
eval $(PYTHONPATH=$CONFIG_DIR python3 -c 'import config; config.print_paths()')

# Read subject IDs from subjects_list.txt
while read subject_id; do
    # Remove possible whitespace
    subject_id=$(echo "$subject_id" | xargs)
    # Skip empty lines
    [ -z "$subject_id" ] && continue

    # Vérifier si le sujet a déjà été traité
    if [ -d "$FREESURFER_OUTPUTS/$subject_id" ]; then
        echo "Skipping subject already processed: $subject_id"
    else
        echo "Processing subject: $subject_id"
        sbatch ./segmentation/run_freesurfer.slurm "$subject_id"
        echo ""
        echo ""
    fi
done < subjects_list.txt