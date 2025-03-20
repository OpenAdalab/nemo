#!/bin/bash

# Set the path to config.py
CONFIG_FILE="./config.py"
# Read paths from config.py and export them as environment variables
eval $(PYTHONPATH=$CONFIG_DIR python3 -c 'import config; config.print_paths()')

input_list=$(ls -d $DIR_INPUTS/sub*)

for s in $input_list
do
    # Vérifier si le sujet est sub-1054001 ou sub-1054002
    #if [[ "$s" == "sub-1054001" ]]; then
    #if [[ "$s" == "sub-1054001" || "$s" == "sub-1054057" || "$s" == "sub-1054092" ]]; then
    #    echo "Skipping subject: $s"
    #    continue  # Passer à l'itération suivante de la boucle

	echo $s

	## Run FreeSurfer segmentation
	#sbatch ./segmentation/run_freesurfer.slurm $s

	## Run FreeSurfer usefull commands
	#sh ./segmentation/run_freesurfer_usefull_commands.sh $s

	## Copy FreeSurfer logs
	cp $DIR_FREESURFER/logs/$s.log $DIR_FREESURFER/outputs/$s/scripts/recon-all.log

	echo ""
	echo ""

    #fi
done