#!/bin/bash
###########################################################
# Execute FreeSurfer segmentation with T1 and T2 only on new cases using Singularity
# Usage: ./run_freesurfer_newcases.sh
###########################################################

# Set the path to config.py
CONFIG_FILE="./config.py"
# Read paths from config.py and export them as environment variables
eval $(PYTHONPATH=$CONFIG_DIR python3 -c 'import config; config.print_paths()')

input_list=$(ls -d $DIR_INPUTS/sub*)

#cd /scratch/lhashimoto
for s in $input_list
do
    # Vérifier si le sujet a déjà été traité
    if [ -d "$FREESURFER_OUTPUTS/$s" ]; then
        echo "Skipping subject already processed: $s"
    else
		echo "Processing subject: $s"
		sbatch ./segmentation/run_freesurfer.slurm $s
		echo ""
		echo ""
	fi
done
