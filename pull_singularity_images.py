#!/usr/bin/env python3
"""
Pull Apptainer/Singularity images

This script:
  • Detects whether 'apptainer' or 'singularity' is available
  • Pulls images from DockerHub using the detected tool
  • Stores them in the container directory specified in config
  • Skips downloads if images already exist
  • Optionally inspects images after pull

Author: HR
Date: 2025-10-24
"""

import subprocess
import shutil
from pathlib import Path
import sys
import utils


# ========================
# HELPER FUNCTIONS
# ========================
def detect_container_tool() -> str:
    """Detect whether Apptainer or Singularity is installed."""
    if shutil.which("apptainer"):
        print("[SETUP] Using Apptainer as container runtime.")
        return "apptainer"
    elif shutil.which("singularity"):
        print("[SETUP] Using Singularity as container runtime.")
        return "singularity"
    else:
        sys.exit(
            "[SETUP] ERROR: Neither Apptainer nor Singularity found.\n"
            "Please install Apptainer with:\n"
            "  sudo add-apt-repository -y ppa:apptainer/ppa && sudo apt update && sudo apt install -y apptainer"
        )


def run_command(cmd: list[str]):
    """Run a shell command and stream output."""
    print(f"\n[SETUP] RUNNING {' '.join(cmd)}")
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout: # type: ignore
        print(f"[{cmd[0]}] {line.strip()}")
    process.wait()
    if process.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")


def pull_image(tool: str, name: str, version: str, repo: str, out_dir: Path):
    """Pull the image using Apptainer or Singularity."""
    sif_name = f"{name}_{version}.sif"
    sif_path = out_dir / sif_name
    docker_uri = f"docker://{repo}:{version}"

    if sif_path.exists():
        print(f"[SETUP] SKIP: {sif_name} already exists at {sif_path}")
        return sif_path

    print(f"[SETUP] INFO: Pulling {sif_name} from {docker_uri}")
    cmd = [tool, "pull", str(sif_path), docker_uri]
    run_command(cmd)

    # Inspect metadata (optional)
    print(f"\n[SETUP] INFO: Inspecting {sif_name}:")
    inspect_cmd = [tool, "inspect", str(sif_path)]
    subprocess.run(inspect_cmd, check=True)
    return sif_path


def main(config_file):
    # -------------------------------
    # Load configuration
    # -------------------------------
    if not config_file:
        config_file = f"{Path(__file__).parent}/config/containers.toml"
    config = utils.load_config(config_file)

    tool = detect_container_tool()

    CONTAINER_DIR = Path(config["directory"])
    CONTAINER_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[SETUP] Downloading containers")

    containers = config["containers"]

    for software, data in containers.items():
        repo = data["docker_repo"]
        versions = data["versions"]
        for version in versions:
            pull_image(tool, software, version, repo, CONTAINER_DIR)

    print("\n[SETUP] ✅ All requested container images are present and verified.")
    print(f"[SETUP] 📁 Location: {CONTAINER_DIR.resolve()}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pull Apptainer/Singularity images.")
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to TOML containers configuration file."
    )
    args = parser.parse_args()

    main(config_file=args.config)
