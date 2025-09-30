#!/bin/bash
#SBATCH -J freesurfer
#SBATCH -p skylake
#SBATCH -n 1
#SBATCH -t 9:00:00
#SBATCH -o /scratch/apaysserand/freesurfer/stdout/%x_%j.out
#SBATCH -e /scratch/apaysserand/freesurfer/stdout/%x_%j.err
#SBATCH --mail-type=BEGIN,END
#SBATCH --mail-user=andrea.paysserand@univ-amu.fr

# chargement des modules
module purge
module load userspace/all

# déplacement sur le répertoire de travail

sh /scratch/apaysserand/code/nemo/segmentation/run_freesurfer.sh $1
