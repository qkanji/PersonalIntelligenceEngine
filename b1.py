"""
Phase 1b — Convert exported PDFs to PNG images and upload to GCS.
=================================================================
Runs locally on Windows after 1_extract_onenote.py has produced the
notebooks_pdf/ folder.

For each page in the structure:
  1. Open the PDF with pypdfium2
  2. Render every PDF page at 300 DPI as a lossless PNG
  3. Save into a per-page folder:  input_images/<notebook>/<section>/<page>/p0001.png …
  4. Upload the whole tree + a corrected structure.json to GCS
  5. Publish a Pub/Sub message so the orchestrator knows there is work

Usage
-----
    $env:GOOGLE_APPLICATION_CREDENTIALS = "path\\to\\service-account.json"

    python 1b_pdf_to_images.py --user-email you@example.com
    python 1b_pdf_to_images.py --user-email you@example.com --notebooks-dir notebooks_pdf --bucket my-bucket
"""

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
DPI = 300
LOCAL_IMAGE_DIR = Path("input_images")  # temp local staging area


# ── Helpers ──────────────────────────────────────────────────────────────────

def sanitize(s: str) -> str:
    """Replace characters that are unsafe for folder/file names."""
    return re.sub(r'[<>:"/\\|?*]', "_", s).strip().rstrip(".")


def windows_basename(path: str) -> str:
    """Extract filename from a Windows path, works on either OS."""
    return path.replace("\\", "/").split("/")[-1]


def fmt(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}m"
    return f"{seconds / 3600:.1f}h"


# ── PDF → PNG rendering ─────────────────────────────────────────────────────

def _render_one(args: tuple) -> tuple[str, int]:
    """
    Top-level (picklable) worker function for ProcessPoolExecutor.
    args = (pdf_path_str, output_dir_str, dpi)
    Returns (output_dir_str, num_images).
    """
    import pypdfium2 as pdfium  # import inside worker process
    pdf_path_str, output_dir_str, dpi = args
    output_dir = Path(output_dir_str)
    output_dir.mkdir(parents=True, exist_ok=True)
    doc = pdfium.PdfDocument(pdf_path_str)
    scale = dpi / 72.0
    count = len(doc)
    for i in range(count):
        page = doc[i]
        bitmap = page.render(scale=scale, rotation=0)
        pil_img = bitmap.to_pil()
        out_path = output_dir / f"p{i + 1:04d}.png"
        pil_img.save(str(out_path), format="PNG")
        page.close()
    doc.close()
    return output_dir_str, count


def render_pdf_to_pngs(pdf_path: Path, output_dir: Path) -> int:
    """
    Render every page of *pdf_path* at DPI resolution and save as
    p0001.png, p0002.png, … in *output_dir*.

    Returns the number of images created.
    """
    _, count = _render_one((str(pdf_path), str(output_dir), DPI))
    return count


# ── GCS upload ───────────────────────────────────────────────────────────────

def upload_tree_to_gcs(
    local_root: Path,
    bucket_name: str,
    gcs_prefix: str,
) -> int:
    """
    Upload every file under *local_root* to gs://<bucket_name>/<gcs_prefix>/…
    Returns the number of files uploaded.
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    count = 0

    files = list(local_root.rglob("*"))
    files = [f for f in files if f.is_file()]

    for local_file in tqdm(files, desc="Uploading to GCS", unit="file"):
        rel = local_file.relative_to(local_root).as_posix()
        blob_name = f"{gcs_prefix}/{rel}"
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(str(local_file))
        count += 1

    return count


def upload_blob(bucket_name: str, blob_name: str, data: str):
    """Upload a string as a GCS blob."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(data, content_type="application/json")


# ── Pub/Sub notification ─────────────────────────────────────────────────────

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


# ── Main pipeline ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Convert exported PDFs to PNGs and upload to GCS."
    )
    parser.add_argument("--user-email", required=True, help="User email for GCS folder")
    parser.add_argument("--notebooks-dir", default=DEFAULT_NOTEBOOKS_DIR, help="Path to notebooks_pdf/")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET, help="GCS bucket name")
    parser.add_argument("--pubsub-topic", default=DEFAULT_PUBSUB_TOPIC, help="Pub/Sub topic name")
    parser.add_argument("--gcp-project", default="personal-intelligence-engine", help="GCP project ID (auto-detected if omitted)")
    parser.add_argument("--workers", type=int, default=os.cpu_count(), help=f"Parallel render workers (default: all CPU cores = {os.cpu_count()})")
    args = parser.parse_args()

    notebooks_dir = Path(args.notebooks_dir)
    if not notebooks_dir.is_dir():
        print(f"[ERROR] Not a directory: {notebooks_dir.resolve()}")
        sys.exit(1)

    # Detect GCP project
    gcp_project = args.gcp_project
    if not gcp_project:
        gcp_project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
        if not gcp_project:
            # Try to detect from the service account credentials
            cred_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            if cred_file and os.path.exists(cred_file):
                with open(cred_file) as f:
                    gcp_project = json.load(f).get("project_id")
        if not gcp_project:
            print("[ERROR] Cannot determine GCP project ID. Use --gcp-project or set GCP_PROJECT env var.")
            sys.exit(1)

    user_email = args.user_email
    bucket_name = args.bucket

    print("=" * 60)
    print("Phase 1b: PDF → PNG → GCS Upload")
    print(f"  Notebooks dir : {notebooks_dir.resolve()}")
    print(f"  User email    : {user_email}")
    print(f"  GCS bucket    : {bucket_name}")
    print(f"  DPI           : {DPI}")
    print(f"  Workers       : {args.workers}")
    print("=" * 60)

    overall_start = time.time()
    total_images = 0
    total_pages = 0

    # Process each notebook folder
    for nb_item in sorted(notebooks_dir.iterdir()):
        if not nb_item.is_dir():
            continue

        structure_file = nb_item / "_structure.json"
        if not structure_file.exists():
            print(f"\n⚠ Skipping {nb_item.name}: no _structure.json")
            continue

        with open(structure_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        notebook_name = data.get("notebook", nb_item.name)
        pages = data.get("pages", [])
        print(f"\n📚 {notebook_name}: {len(pages)} page(s)")

        # Build a filename→local-path map for resolving Windows paths
        filename_map: dict[str, Path] = {}
        for root, _, files in os.walk(nb_item):
            for file in files:
                if file.endswith(".pdf"):
                    filename_map[file] = Path(root) / file

        # ── Build the full task list for this notebook ─────────────────────
        # Each task: (pdf_path, local_page_dir, page_metadata)
        render_tasks: list[tuple] = []
        page_meta_list: list[dict] = []

        for page in pages:
            pdf_filename = windows_basename(page.get("path", ""))
            pdf_path = filename_map.get(pdf_filename)

            if not pdf_path or not pdf_path.exists():
                print(f"    ⚠ PDF not found: {pdf_filename}")
                continue

            page_name = page["name"]
            section = page.get("section", "Uncategorized")
            order = page.get("order", 0)

            page_folder_name = f"{order:03d}_{sanitize(page_name)}"
            local_page_dir = (
                LOCAL_IMAGE_DIR
                / sanitize(notebook_name)
                / sanitize(section.replace("/", os.sep))
                / page_folder_name
            )

            render_tasks.append((str(pdf_path), str(local_page_dir), DPI))
            page_meta_list.append({
                "page": page,
                "page_folder_name": page_folder_name,
                "local_page_dir": local_page_dir,
                "page_name": page_name,
                "section": section,
                "order": order,
            })

        if not render_tasks:
            continue

        # ── Parallel render ────────────────────────────────────────────────
        print(f"  Rendering {len(render_tasks)} PDF(s) with {args.workers} worker(s)...")
        dir_to_num_imgs: dict[str, int] = {}

        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(_render_one, task): task for task in render_tasks}
            with tqdm(total=len(render_tasks), desc="  Rendering", unit="page") as pbar:
                for future in as_completed(futures):
                    out_dir_str, num_imgs = future.result()
                    dir_to_num_imgs[out_dir_str] = num_imgs
                    total_images += num_imgs
                    total_pages += 1
                    pbar.update(1)

        # ── Build updated structure entries ───────────────────────────────
        gcs_structure_pages = []
        for meta in page_meta_list:
            out_dir_str = str(meta["local_page_dir"])
            num_imgs = dir_to_num_imgs.get(out_dir_str, 0)
            section = meta["section"]
            page_folder_name = meta["page_folder_name"]

            gcs_page_folder = (
                f"{user_email}/input_images/"
                f"{sanitize(notebook_name)}/"
                f"{sanitize(section.replace(chr(47), '_'))}/"
                f"{page_folder_name}"
            )

            gcs_structure_pages.append({
                "name": meta["page_name"],
                "section": section,
                "order": meta["order"],
                "notebook": notebook_name,
                "gcs_folder": gcs_page_folder,
                "num_images": num_imgs,
            })

        # Write corrected structure.json locally
        gcs_structure = {
            "notebook": notebook_name,
            "pages": gcs_structure_pages,
        }
        local_structure = LOCAL_IMAGE_DIR / sanitize(notebook_name) / "_structure.json"
        local_structure.parent.mkdir(parents=True, exist_ok=True)
        with open(local_structure, "w", encoding="utf-8") as f:
            json.dump(gcs_structure, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Rendered {total_images} PNG(s) across {total_pages} page(s)")
    print(f"Rendering took {fmt(time.time() - overall_start)}")

    # Upload everything to GCS
    print(f"\nUploading to gs://{bucket_name}/{user_email}/input_images/...")
    upload_start = time.time()
    num_uploaded = upload_tree_to_gcs(LOCAL_IMAGE_DIR, bucket_name, f"{user_email}/input_images")
    print(f"Uploaded {num_uploaded} file(s) in {fmt(time.time() - upload_start)}")

    # Publish Pub/Sub notification
    print("\nPublishing job notification...")
    publish_job_notification(gcp_project, args.pubsub_topic, user_email, bucket_name)

    total_time = time.time() - overall_start
    print(f"\n✅ Done in {fmt(total_time)}")
    print(f"   Images are at: gs://{bucket_name}/{user_email}/input_images/")


if __name__ == "__main__":
    main()
