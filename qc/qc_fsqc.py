# Auteur: Lucile Hashimoto (Adalab)
# Date: 2025

import fsqc
from config import FREESURFER_OUTPUTS, FREESURFER_FSQC

## Run FSQC on a single subject
# fsqc.run_fsqc(subjects_dir=FREESURFER_OUTPUTS,
#               output_dir=FREESURFER_FSQC,
#               subjects=['sub-1054001'],
#               screenshots=True,
#               surfaces=True,
#               skullstrip=True,
#               fornix=True,
#               hypothalamus=False,
#               hippocampus=False,
#               # hippocampus_label="T1.v21",
#               shape=False,  # Requires to run freesurfer commands which is too complicated via singularity
#               outlier=True,
# )

#Run FSQC on a list of subjects
#subjects = [
#    'sub-1054023', 'sub-1054109', 'sub-1054107', 'sub-1054021', 'sub-1054083', 'sub-1054030', 'sub-1054060',
#    'sub-1054018', 'sub-1054096', 'sub-1054072', 'sub-1054013', 'sub-1054082', 'sub-1054085', 'sub-1054116',
#    'sub-1054100', 'sub-1054106', 'sub-1054027', 'sub-1054004', 'sub-1054038', 'sub-1054081', 'sub-1054101',
#    'sub-1054094', 'sub-1054020', 'sub-1054119', 'sub-1054056', 'sub-1054055', 'sub-1054086', 'sub-1054068',
#    'sub-1054024', 'sub-1054073', 'sub-1054045', 'sub-1054110', 'sub-1054057', 'sub-1054102', 'sub-1054015',
#    'sub-1054093', 'sub-1054088', 'sub-1054111', 'sub-1054080', 'sub-1054028'
#]

#fsqc.run_fsqc(
#    subjects_dir=FREESURFER_OUTPUTS,
#    output_dir=FREESURFER_FSQC,
#   subjects=subjects, 
#    screenshots=True,
#    surfaces=True,
#    skullstrip=True,
#    fornix=True,
#    hypothalamus=False,
#    hippocampus=False,
#    shape=False,
#    outlier=True,
#    skip_existing=False
#)

## Run FSQC on all single subjects (one by one, no skipping individual processing)
fsqc.run_fsqc(
    subjects_dir=FREESURFER_OUTPUTS,
    output_dir=FREESURFER_FSQC,
    screenshots=True,
    surfaces=True,
    skullstrip=True,
    fornix=True,
    hypothalamus=False,
    hippocampus=False,
    shape=False,
    outlier=True,
    skip_existing=False
)

## Run FSQC on all subjects (group_only = true might skip individual processing and do the group level only ?)
#fsqc.run_fsqc(subjects_dir=FREESURFER_OUTPUTS,
#              output_dir=FREESURFER_FSQC,
#              group_only=True,
#              screenshots_html=True,
#              surfaces_html=True,
#              skullstrip_html=True,
#              fornix_html=True,
#              hypothalamus_html=False,
#              hippocampus_html=False,
#              # hippocampus_label="T1.v21",
#              shape=False,  # Requires to run freesurfer commands which is too complicated via singularity
#              outlier=True,
#              )

# Test FSQC uniquement sur la segmentation de l'hippo-amygdale
# fsqc.run_fsqc(subjects_dir=FREESURFER_OUTPUTS,
#               output_dir=FREESURFER_FSQC,
#               subjects=['sub-1054001'],
#               screenshots=False,
#               surfaces=False,
#               skullstrip=False,
#               fornix=False,
#               hypothalamus=False,
#               hippocampus=True,
#               hippocampus_label="CA",  # specify label for hippocampus segmentation files (default: T1.v21). The
#               # full filename is then [lr]h.hippoAmygLabels-<LABEL>.FSvoxelSpace.mgz
#               shape=False,  # Requires to run freesurfer commands which is too complicated via singularity
#               outlier=False,
#               skip_existing=False
# )

# subjects = ['sub-1054079','sub-1054002','sub-1054089','sub-1054051','sub-1054049','sub-1054012','sub-1054029',
# 'sub-1054043','sub-1054017','sub-1054026','sub-1054087','sub-1054054','sub-1054025','sub-1054042','sub-1054016',
# 'sub-1054090','sub-1054001','sub-1054092','sub-1054022','sub-1054047','sub-1054050','sub-1054036','sub-1054070',
# 'sub-1054067','sub-1054040','sub-1054046','sub-1054048','sub-1054091','sub-1054053','sub-1054034','sub-1054032',
# 'sub-1054069','sub-1054033','sub-1054078','sub-1054011','sub-1054019','sub-1054063','sub-1054061','sub-1054041',
# 'sub-1054003','sub-1054071','sub-1054037','sub-1054084','sub-1054059','sub-1054031','sub-1054075','sub-1054014',
# 'sub-1054062','sub-1054064','sub-1054074','sub-1054065','sub-1054052','sub-1054010','sub-1054023','sub-1054021',
# 'sub-1054083','sub-1054030','sub-1054060','sub-1054018','sub-1054072','sub-1054013','sub-1054082','sub-1054085',
# 'sub-1054027','sub-1054004','sub-1054038','sub-1054081','sub-1054020','sub-1054056','sub-1054055','sub-1054086',
# 'sub-1054068','sub-1054024','sub-1054073','sub-1054045','sub-1054057','sub-1054015','sub-1054088','sub-1054080',
# 'sub-1054028']
