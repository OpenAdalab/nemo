# fMRIPrep + XCP-D Pipeline Documentation

This pipeline processes BIDS-formatted neuroimaging data using fMRIPrep 25.2 followed by XCP-D post-processing, implemented via Singularity containers.

## Prerequisites

- Singularity installed
- BIDS-compliant dataset
- Sufficient storage space for derivatives
- Access to fMRIPrep 25.2.2 and XCP-D 0.12.0 containers

## Pipeline Structure

1. **fMRIPrep Processing**
    - Version: 25.2.2
    - Input: BIDS dataset
    - Output: fMRIPrep derivatives

2. **XCP-D Post-processing**
    - Version: 0.12.0
    - Input: fMRIPrep derivatives
    - Output: Processed functional connectivity data

## Usage

```bash
# Run fMRIPrep
singularity run --cleanenv \
     fmriprep_25.2.2.sif \
     /path/to/bids \
     /path/to/output \
     participant

# Run XCP-D
singularity run --cleanenv \
     xcpd_0.12.0.sif \
     /path/to/fmriprep/output \
     /path/to/xcpd/output \
     participant
```

## Outputs

- `/derivatives/fmriprep/`: Standard fMRIPrep outputs
- `/derivatives/xcpd/`: XCP-D post-processing results

## References

- [fMRIPrep Documentation](https://fmriprep.org)
- [XCP-D Documentation](https://xcpengine.readthedocs.io)