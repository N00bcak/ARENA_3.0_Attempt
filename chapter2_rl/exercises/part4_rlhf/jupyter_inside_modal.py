# ## Overview
#
# Quick snippet showing how to connect to a Jupyter notebook server running inside a Modal container,
# especially useful for exploring the contents of Modal Volumes.
# This uses [Modal Tunnels](https://modal.com/docs/guide/tunnels#tunnels-beta)
# to create a tunnel between the running Jupyter instance and the internet.

import os
from pathlib import Path
import subprocess
import time
from typing import Optional

import modal
import modal.gpu


# == Configuration Section ==
JUPYTER_TOKEN: str = "BLAH_BLAH_BLAH-BLAHDY_BLAH-BLAHH"  # Change me to something non-guessable!

IDENTIFIER: str = "recap-chuenyang"  # Change me to a user identifier
TIMEOUT: int = 10_000  # Default timeout for the Jupyter server in seconds

# Specify the GPU configuration if you want to use a GPU for your Jupyter server.
# Else, you can set `GPU` to `None` to run the Jupyter server with just a CPU.
# Example:
# GPU: Optional[modal.gpu._GPUConfig] = modal.gpu.T4(1)  # GPU type(count)
GPU: Optional[modal.gpu._GPUConfig] = modal.gpu.A100()

# You can mount local files into the container, which is useful for exploring
# the contents of a Modal Volume or for running Jupyter notebooks that are stored locally.
# If you want to mount local files, set `MOUNT_LOCAL_FILES` to True.
MOUNT_LOCAL_FILES: bool = True
MOUNT_DESTINATION: str = "/root"  # Where to mount the local files in the container

# Note that mounted local files aren't saved to the Volume,
# so if you want to keep them across sessions, you should copy them to the Volume manually.

# If you want some files to persist across Jupyter sessions, you can use a Modal Volume.
# This is useful for storing notebooks, datasets, or other files you want to keep.
# If you want to use a Volume, set `CREATE_VOLUME` to True.
CREATE_VOLUME: bool = False  # Whether to create a new Volume or use an existing one
CACHE_DIR: str = "/root/mount"

# From a volume, you can download files to your local machine
# using the `modal volume download` command, e.g.:
# `modal volume get modal-recap-mount-kgreyy <filename>`

# == End of Configuration Section ==


image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git")
    .pip_install(
        "jupyter",
    )
)
if MOUNT_LOCAL_FILES:
    image = image.add_local_dir(
        Path(".").resolve(),
        remote_path=MOUNT_DESTINATION,
    )


app = modal.App(name=f"RECAP-jupyter-{IDENTIFIER}", image=image)

if CREATE_VOLUME:
    volume = modal.Volume.from_name(
        f"modal-recap-mount-{IDENTIFIER}", create_if_missing=True
    )
    volumes = {CACHE_DIR: volume}
else:
    volumes = {}

# This is all that's needed to create a long-lived Jupyter server process in Modal
# that you can access in your Browser through a secure network tunnel.
# This can be useful when you want to interactively engage with Volume contents
# without having to download it to your host computer.


@app.function(max_containers=1, timeout=TIMEOUT, volumes=volumes, gpu=GPU)
def run_jupyter(timeout: int):
    jupyter_port = 8888
    print("Running Jupyter now...")
    with modal.forward(jupyter_port) as tunnel:
        jupyter_process = subprocess.Popen(
            [
                "jupyter",
                "notebook",
                "--no-browser",
                "--allow-root",
                "--ip=0.0.0.0",
                f"--port={jupyter_port}",
                "--NotebookApp.allow_origin='*'",
                "--NotebookApp.allow_remote_access=1",
            ],
            env={**os.environ, "JUPYTER_TOKEN": JUPYTER_TOKEN},
        )

        print(f"Jupyter available at => {tunnel.url}/doc")

        try:
            end_time = time.time() + timeout
            while time.time() < end_time:
                time.sleep(5)
            print(f"Reached end of {timeout} second timeout period. Exiting...")
        except KeyboardInterrupt:
            print("Exiting...")
        except Exception as e:
            print(e)
        finally:
            jupyter_process.kill()


@app.local_entrypoint()
def main(timeout: int = TIMEOUT):
    # seed_volume.remote()
    # Run the Jupyter Notebook server
    run_jupyter.remote(
        timeout=timeout,
    )
