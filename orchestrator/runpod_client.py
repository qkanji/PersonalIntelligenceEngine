"""
Thin wrapper around the RunPod REST API for on-demand GPU pod management.

Docs: https://docs.runpod.io/api-reference/pods/POST/pods
"""

import requests

from . import config

_BASE = "https://rest.runpod.io/v1"


def _headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.RUNPOD_API_KEY}",
    }


# ── Public API ───────────────────────────────────────────────────────────────

def create_pod(
    name: str,
    env_vars: dict[str, str],
    docker_command: str | None = None,
) -> str:
    """
    Create an interruptible (spot) GPU pod and return its ID.

    Parameters
    ----------
    name : str
        Human-readable pod name (max 191 chars).
    env_vars : dict
        Key-value pairs injected as env vars inside the container.
    docker_command : str | None
        Optional shell command passed as dockerStartCmd (bash -c "...").

    Returns
    -------
    Pod ID string.
    """
    body: dict = {
        "name": name,
        "imageName": config.RUNPOD_IMAGE,
        "gpuTypeIds": [config.RUNPOD_GPU_TYPE],
        "cloudType": config.RUNPOD_CLOUD_TYPE,
        "interruptible": True,
        "containerDiskInGb": config.RUNPOD_CONTAINER_DISK,
        "minVCPUPerGPU": 4,
        "minRAMPerGPU": 16,
        "volumeInGb": 1,
        "env": env_vars,  # REST API takes a plain {key: value} dict
        "allowedCudaVersions": ["12.6", "12.8", "13.0"],
    }

    if docker_command:
        # dockerStartCmd overrides CMD; wrap in bash so shell features work
        body["dockerStartCmd"] = ["bash", "-c", docker_command]

    resp = requests.post(f"{_BASE}/pods", headers=_headers(), json=body, timeout=30)
    if not resp.ok:
        print(f"[runpod] create_pod failed {resp.status_code}: {resp.text}")
        resp.raise_for_status()
    pod = resp.json()
    print(f"[runpod] Full create response: {pod}")
    print(f"[runpod] Created pod '{pod.get('name')}' → id={pod.get('id')} desiredStatus={pod.get('desiredStatus')} machine={pod.get('machine')}")
    return pod["id"]


def terminate_pod(pod_id: str) -> None:
    """Terminate (delete) a pod by ID."""
    resp = requests.delete(f"{_BASE}/pods/{pod_id}", headers=_headers(), timeout=30)
    if not resp.ok:
        print(f"[runpod] terminate_pod failed {resp.status_code}: {resp.text}")
        resp.raise_for_status()
    print(f"[runpod] Terminated pod {pod_id}")


def get_pod_status(pod_id: str) -> str:
    """
    Return the runtime status of a pod.

    Possible values: RUNNING, EXITED, TERMINATED.
    Returns "UNKNOWN" if the pod is not found or the request fails.
    """
    try:
        resp = requests.get(f"{_BASE}/pods/{pod_id}", headers=_headers(), timeout=30)
        if resp.status_code == 404:
            print(f"[runpod] get_pod_status: pod {pod_id} not found (404)")
            return "UNKNOWN"
        if not resp.ok:
            print(f"[runpod] get_pod_status failed {resp.status_code}: {resp.text}")
            return "UNKNOWN"
        data = resp.json()
        print(f"[runpod] get_pod_status {pod_id}: {data}")
        return data.get("desiredStatus", "UNKNOWN")
    except Exception as e:
        print(f"[runpod] get_pod_status exception: {e}")
        return "UNKNOWN"
