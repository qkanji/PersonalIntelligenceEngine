"""
Orchestrator — runs on e2-micro, manages RunPod GPU pods.

Two background threads:
  - Pub/Sub pull thread  : polls rag-jobs-pull every PUBSUB_PULL_INTERVAL
                           seconds; launches a RunPod 4090 pod per job.
  - Health-check thread  : every HEALTH_CHECK_INTERVAL seconds checks
                           RunPod status and done.json in GCS; terminates
                           completed or stale pods.

No HTTP server — pull-based design needs none.
"""

import json
import signal
import sys
import threading
import time

from . import config
from .runpod_client import create_pod, get_pod_status, terminate_pod

# ── In-memory registry of active pods ────────────────────────────────────────
# { pod_id: { "user_email": str, "started": float, "bucket_prefix": str } }
_active_pods: dict[str, dict] = {}
_lock = threading.Lock()

# ── Lazy-initialised GCS client (avoids re-creating on every health check) ───
_gcs_client = None


def _get_gcs_client():
    global _gcs_client
    if _gcs_client is None:
        from google.cloud import storage
        _gcs_client = storage.Client()
    return _gcs_client


# ── Shared helper: launch a pod for a job ────────────────────────────────────

def _launch_pod(user_email: str, bucket_prefix: str) -> str | None:
    """
    Spin up a RunPod worker pod for *user_email*.
    Returns the pod ID, or None if a pod for that user is already running.
    """
    with _lock:
        for info in _active_pods.values():
            if info["user_email"] == user_email:
                print(f"[orchestrator] Pod already running for {user_email}, skipping")
                return None

    fetch_cmd = f"curl -fsSL '{config.WORKER_SCRIPT_URL}' -o /tmp/worker.py"

    # Quote each dep so version specifiers like >=0.8 aren't interpreted
    # as shell redirection inside the bash -c string.
    deps_quoted = " ".join(f"'{d}'" for d in config.WORKER_DEPS.split())

    # Each stage echoes a sentinel so we can see exactly where a failure occurs
    # in container logs. stderr is merged into stdout (2>&1) so pip errors surface.
    startup_cmd = " && ".join([
        "echo '[PIE] stage: pip install'",
        f"pip install --no-cache-dir {deps_quoted} 2>&1",
        "echo '[PIE] stage: fetch worker'",
        fetch_cmd,
        "echo '[PIE] stage: run worker'",
        "python3 -u /tmp/worker.py 2>&1",
    ])

    env_vars = {
        "USER_EMAIL":          user_email,
        "GCS_BUCKET":          config.GCS_BUCKET,
        "PINECONE_API_KEY":    config.PINECONE_API_KEY,
        "PINECONE_INDEX":      config.PINECONE_INDEX,
        "RUNPOD_API_KEY":      config.RUNPOD_API_KEY,
        "GCP_SA_KEY_JSON_B64": config.GCP_SA_KEY_JSON_B64,
    }

    pod_name = f"rag-worker-{user_email.split('@')[0][:12]}-{int(time.time()) % 100000}"

    try:
        pod_id = create_pod(
            name=pod_name,
            env_vars=env_vars,
            docker_command=startup_cmd,
        )
    except Exception as e:
        print(f"[orchestrator] Failed to create pod: {e}")
        return None

    with _lock:
        _active_pods[pod_id] = {
            "user_email": user_email,
            "started": time.time(),
            "bucket_prefix": bucket_prefix,
        }

    print(f"[orchestrator] Launched pod {pod_id} for {user_email}")
    return pod_id


# ── Pub/Sub pull thread ───────────────────────────────────────────────────

def _pubsub_pull_loop():
    """
    Repeatedly pull from the Pub/Sub Pull subscription and launch pods.
    Runs in a background daemon thread.
    """
    from google.cloud import pubsub_v1
    subscriber = pubsub_v1.SubscriberClient()
    sub_path = subscriber.subscription_path(config.GCP_PROJECT, config.PUBSUB_SUBSCRIPTION)
    print(f"[pubsub] Polling subscription: {sub_path} every {config.PUBSUB_PULL_INTERVAL}s")

    while True:
        try:
            response = subscriber.pull(
                request={"subscription": sub_path, "max_messages": 10},
                timeout=10,
            )
            ack_ids = []
            for msg in response.received_messages:
                try:
                    payload = json.loads(msg.message.data.decode("utf-8"))
                    user_email = payload.get("user_email", "")
                    bucket_prefix = payload.get("bucket_prefix", "")
                    if user_email:
                        _launch_pod(user_email, bucket_prefix)
                    else:
                        print(f"[pubsub] Message missing user_email, skipping")
                    ack_ids.append(msg.ack_id)
                except Exception as e:
                    print(f"[pubsub] Bad message: {e}")
                    ack_ids.append(msg.ack_id)  # ack anyway to avoid redelivery loop

            if ack_ids:
                subscriber.acknowledge(
                    request={"subscription": sub_path, "ack_ids": ack_ids}
                )
        except Exception as e:
            # 504 Deadline Exceeded is normal when the subscription has no messages
            if "504" not in str(e) and "Deadline Exceeded" not in str(e):
                print(f"[pubsub] Pull error: {e}")

        time.sleep(config.PUBSUB_PULL_INTERVAL)

# ── Health endpoint ──────────────────────────────────────────────────────────

# ── Background health-check thread ──────────────────────────────────────────

def _check_done_marker(user_email: str) -> bool:
    """Check if gs://<bucket>/<user_email>/done.json exists."""
    try:
        client = _get_gcs_client()
        bucket = client.bucket(config.GCS_BUCKET)
        blob = bucket.blob(f"{user_email}/done.json")
        return blob.exists()
    except Exception:
        return False


def _health_check_loop():
    """Periodically check pods and clean up completed/stale ones."""
    while True:
        time.sleep(config.HEALTH_CHECK_INTERVAL)

        with _lock:
            snapshot = dict(_active_pods)

        pods_to_remove: list[str] = []

        for pod_id, info in snapshot.items():
            user_email = info["user_email"]
            elapsed = time.time() - info["started"]

            # 1. Check if the worker wrote done.json
            if _check_done_marker(user_email):
                print(f"[health] Pod {pod_id} ({user_email}): done.json found, terminating")
                try:
                    terminate_pod(pod_id)
                except Exception as e:
                    print(f"[health] Failed to terminate {pod_id}: {e}")
                pods_to_remove.append(pod_id)
                continue

            # 2. Check RunPod status
            status = get_pod_status(pod_id)
            if status in ("EXITED", "TERMINATED", "UNKNOWN"):
                print(f"[health] Pod {pod_id} ({user_email}): status={status}, removing from tracker")
                pods_to_remove.append(pod_id)
                continue

            # 3. Stale guard — if a pod has been running > 2 hours, kill it
            max_runtime = 2 * 3600
            if elapsed > max_runtime:
                print(f"[health] Pod {pod_id} ({user_email}): exceeded {max_runtime}s, force-terminating")
                try:
                    terminate_pod(pod_id)
                except Exception as e:
                    print(f"[health] Failed to terminate {pod_id}: {e}")
                pods_to_remove.append(pod_id)
                continue

            # Pod is still running normally
            mins = elapsed / 60
            print(f"[health] Pod {pod_id} ({user_email}): RUNNING for {mins:.0f}m")

        # Remove completed/stale pods from the registry
        if pods_to_remove:
            with _lock:
                for pid in pods_to_remove:
                    _active_pods.pop(pid, None)


# ── Entrypoint ───────────────────────────────────────────────────────────────

def start():
    """Start both daemon threads and block the main thread until interrupted."""
    puller = threading.Thread(target=_pubsub_pull_loop, daemon=True, name="pubsub-puller")
    puller.start()
    print(f"[orchestrator] Pub/Sub pull thread started (subscription={config.PUBSUB_SUBSCRIPTION})")

    checker = threading.Thread(target=_health_check_loop, daemon=True, name="health-check")
    checker.start()
    print(f"[orchestrator] Health-check thread started (interval={config.HEALTH_CHECK_INTERVAL}s)")

    # Keep the main thread alive; exit cleanly on Ctrl-C or SIGTERM
    def _shutdown(signum, frame):
        print("[orchestrator] Shutting down")
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("[orchestrator] Interrupted")


if __name__ == "__main__":
    start()
