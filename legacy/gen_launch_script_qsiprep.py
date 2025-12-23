# subjects indices from 1 to 11
subs = range(1,12)

# global parameters
sing_version = '0.20.0'
clean_workdir = '' # '' or ' --clean-workdir'
requested_mem = 70 # in Gb (integer)
requested_time = 48 # in hours (integer)

# generate 'sub-xxx_qsiprep.sh' scripts
for sub in subs:

    header = \
'''#!/bin/bash
#SBATCH -J qsp{0:03}
#SBATCH -p kepler
#SBATCH -A b347
#SBATCH --gres=gpu:2
#SBATCH --nodes=1
#SBATCH --mem={1}gb
#SBATCH --cpus-per-task=16
#SBATCH --time={2}:00:00
#SBATCH -e /scratch/mgilson/braint/derivatives/qsiprep/sbatch_outputs/sub{0:03}_%N_%j_%a.err
#SBATCH -o /scratch/mgilson/braint/derivatives/qsiprep/sbatch_outputs/sub-{0:03}_%N_%j_%a.out
#SBATCH --mail-type=BEGIN,END
#SBATCH --mail-user=julien.sein@univ-amu.fr
'''.format(sub, requested_mem, requested_time)

    module_directory = \
'''
module purge
module load userspace/all
module load singularity

# directories
BIDS_ROOT_DIR=/scratch/mgilson/braint

cd $BIDS_ROOT_DIR
'''

    singularity_command = \
'''
# singularity command
singularity run --cleanenv -B $BIDS_ROOT_DIR:/data,$BIDS_ROOT_DIR/derivatives:/out \\
   --nv $BIDS_ROOT_DIR/code/singularity/qsiprep-{1}.sif /data /out \\
        participant --participant-label {0:03} \\
        -w /out/temp_wf_qsiprep {2} --output-resolution 1.2 \\
        --fs-license-file /data/code/freesurfer/license.txt \\
        --eddy-config /data/code/qsiprep/eddy_params.json \\
        --b0-threshold 50 --unringing-method mrdegibbs \\
        --denoise-method dwidenoise \\
        --anat-modality T1w \\
        --distortion-group-merge average 
'''.format(sub, sing_version, clean_workdir)

    ownership_sharing = \
'''
chmod -Rf 771 $BIDS_ROOT_DIR
chgrp -Rf 347 $BIDS_ROOT_DIR

echo "FINISHED OK"
'''
    
    file_content = header + module_directory + singularity_command + ownership_sharing
    
    file_dir = './'
    file_name = 'sub-{0:03}_qsiprep.slurm'.format(sub)
    
    with open(file_dir+file_name, 'w') as f:
        f.write(file_content)
