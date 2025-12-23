# subjects indices from 1 to 11
subs = range(1,12)

# global parameters
sing_version = '0.19.0'
clean_workdir = '' # '' or ' --clean-workdir'
requested_mem = 70 # in Gb (integer)
requested_time = 48 # in hours (integer)

# generate 'sub-xxx_qsirecon.sh' scripts
for sub in subs:

    header = \
'''#!/bin/bash
#SBATCH -J qsr{0:03}
#SBATCH -p kepler
#SBATCH -A b347
#SBATCH --gres=gpu:2
#SBATCH --nodes=1
#SBATCH --mem={1}gb
#SBATCH --cpus-per-task=16
#SBATCH --time={2}:00:00
#SBATCH -e /scratch/mgilson/braint/derivatives/qsirecon/sbatch_outputs/sub-{0:03}_%N_%j_%a.err
#SBATCH -o /scratch/mgilson/braint/derivatives/qsirecon/sbatch_outputs/sub-{0:03}_%N_%j_%a.out
#SBATCH --mail-type=BEGIN,END
#SBATCH --mail-user=matthieu.gilson@univ-amu.fr
'''.format(sub, requested_mem, requested_time)

    module_directory = \
'''
#module purge
#module load userspace/all
#module load singularity

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
        -w /out/temp_wf_qsirecon {2}  \\
        --fs-license-file /data/code/freesurfer/license.txt \\
        --recon-only --recon-spec mrtrix_multishell_msmt_ACT-hsvs \\
        --recon-input /out/qsiprep \\
        --denoise-method dwidenoise \\
        --anat-modality T1w \\
        --freesurfer-input /data/derivatives/fmriprep/sourcedata/freesurfer 
'''.format(sub, sing_version, clean_workdir)

    ownership_sharing = \
'''
chmod -Rf 771 $BIDS_ROOT_DIR
chgrp -Rf 347 $BIDS_ROOT_DIR

echo "FINISHED OK"
'''
    
    file_content = header + module_directory + singularity_command + ownership_sharing
    
    file_dir = './'
    file_name = 'sub-{0:03}_qsirecon.slurm'.format(sub)
    
    with open(file_dir+file_name, 'w') as f:
        f.write(file_content)
