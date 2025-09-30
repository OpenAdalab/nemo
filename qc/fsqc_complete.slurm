#!/bin/bash
#SBATCH -J fsqc
#SBATCH -p skylake
#SBATCH -n 1
#SBATCH -t 9:00:00
#SBATCH --mail-type=BEGIN,END
#SBATCH --mail-user=andrea.paysserand@univ-amu.fr

source /home/apaysserand/anaconda3/etc/profile.d/conda.sh
conda activate nemo
python3 /scratch/apaysserand/code/nemo/qc/qc_complete.py
