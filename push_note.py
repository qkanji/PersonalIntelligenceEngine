import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pypdfium2 as pdfium
from google.cloud import pubsub_v1, storage
from tqdm import tqdm

# ── Config defaults ──────────────────────────────────────────────────────────
DEFAULT_NOTEBOOKS_DIR = "notebooks_pdf"
DEFAULT_BUCKET = "pie-data"
DEFAULT_PUBSUB_TOPIC = "rag-jobs-pending"
DPI = 150
LOCAL_IMAGE_DIR = Path("input_images")  # temp local staging area


def publish_job_notification(
    project_id: str,
    topic_name: str,
    user_email: str,
    bucket_name: str,
):
    """
    Publish a message to trigger the orchestrator.
    """
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic_name)
    payload = json.dumps({
        "user_email": user_email,
        "bucket_prefix": f"gs://{bucket_name}/{user_email}/",
    }).encode("utf-8")
    future = publisher.publish(topic_path, data=payload)
    message_id = future.result()
    print(f"Published Pub/Sub message: {message_id}")

if __name__ == "__main__":
    project_id = os.environ["GCP_PROJECT"]
    topic_name = os.environ.get("PUBSUB_TOPIC", "rag-jobs-pending")
    user_email = os.environ["USER_EMAIL"]
    bucket_name = os.environ["GCS_BUCKET"]
    publish_job_notification(project_id, topic_name, user_email, bucket_name)