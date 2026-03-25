# Personal Intelligence Engine (PIE)

## Motivation & Use Case

The primary goal of PIE is to build a highly effective RAG (Retrieval-Augmented Generation) system to help me study for exams using my actual school notes. General LLMs have no context of the specific curriculums or methods taught in class, and simply feeding an entire 2 GB PDF of notebook exports into a prompt is impossible or wildly impractical.
This project also serves as a strong technical AI showcase for my application to the Waterloo Software Engineering (SE) program.
_Note on architecture constraint:_ I could not simply use the Microsoft Graph API to fetch my student notes smoothly because of strict school account restrictions. This necessitated building the local extraction phase via Windows PowerShell COM APIs to pull the notes cleanly before sending them to the cloud.

## Project Plan & Overview

PIE is a comprehensive multi-stage application that extracts notes from local OneNote notebooks, processes them using cost-effective RunPod spot instances (4090 GPUs), and serves them via a Python backend and React frontend to create a local-personal RAG (Retrieval-Augmented Generation) assistant.

The primary processing strategy involves exporting local notes to PDFs, uploading them to GCP, triggering a cloud Orchestrator to spin up a dynamic worker pod, completing inference tasks like OCR, and indexing the results to build a chat intelligence database.

## Where We Are Currently At

- **Docker Image Optimization Phase: COMPLETED.** The Docker image was successfully stripped down from ~46GB to ~5GB to accommodate a 15 Mbps upload bottleneck. Models (e.g., Qwen 3.5 9B) are now dynamically downloaded at boot from HuggingFace, heavily reducing cold-start image bloat.
- **RunPod Compute Stabilization: COMPLETED.** Configured the infrastructure to provision `COMMUNITY` Spot Instances ($0.20/hr, 4090 GPUs). The `Dockerfile` relies on a `CUDA 12.6.2` base image paired with PyTorch `2.10.0 (cu126)`. To maximize instance availability, `orchestrator/runpod_client.py` uses an `allowedCudaVersions` policy of `["12.6", "12.8", "13.0"]`.
- **OneNote Parsing & Deduplication: IN PROGRESS.** We are currently optimizing the `phase1_extract/structure.py` tree traversal to prevent overwriting similarly named pages, specifically filtering out the `_Content Library` section group to only index Student notes and save on total extraction/processing time (approx 3 hours vs 6 hours).

## Architecture & Code Map

- **`Dockerfile`**: Minimal inference environment built on `nvidia/cuda:12.6.2-base-ubuntu22.04`. Contains `vllm==0.17.1` and `torch==2.10.0`.
- **`worker/`** (e.g., `worker.py`): The remote GPU code running inside RunPod. Downloads HuggingFace models upon boot, downloads user PDFs from GCP Bucket, runs Optical Character Recognition (OCR), and writes Markdown parsed notes back.
- **`orchestrator/`** (e.g., `runpod_client.py`, `config.py`): The traffic control application. Spawns, tracks, and cleans up dynamic RunPod instances. Checks Pub/Sub message queues to pass data jobs.
- **`phase1_extract/`** (e.g., `export.py`, `structure.py`): Local module executing Windows PowerShell COM APIs to dump a Microsoft OneNote digital hierarchy into structured offline PDFs.
- **`b1.py` / `push_note.py`**: Intermediary scripts bridging Phase 1 Extracted content to the Cloud by transferring content to GCS buckets and signaling GCP Pub/Sub.
- **`backend/`**: Python FastAPI/Flask stack managing chat memory, retrieval chains, and semantic search routing.
- **`frontend/`**: Vite-based React + TypeScript project running the primary interaction UI.

## Build and Developer Environment

- **Python Setup**: Local components run inside a Python `.venv` containing Windows specific modules (`pywin32`) for COM interaction.
- **Docker Build**: Requires strict version constraints. Example deployment flow:
  `docker build -t qkanji/pie-worker-gpu:cu126 .`
  `docker push qkanji/pie-worker-gpu:cu126`
- **Secrets Management**: Credentials (RunPod API, GCP Auth) pass dynamically through `config.py` using OS Environment variables.

## Project Conventions & Pitfalls

- **HuggingFace Cache**: Avoid baking models into the `Dockerfile`. Always rely on `worker.py` runtime downloads. RunPod connection speed on Community networks regularly peaks over 1Gbps, making runtime model caching vastly cheaper than slow massive Docker registry pushes.
- **vLLM Pre-Compiled C++ Extensions**: `vllm==0.17.1` is strictly pinned. Attempting to build against CUDA 13.0 base containers drops critical `.so` files needed by pip. Stick to `12.6` base.
- **Path Duplication**: OneNote pages frequently share names (e.g., `Untitled` or `01_Notes`). Always use strictly generated unique identifiers or concatenated structure paths when saving them or parsing to avoid overwriting files in the flattening process.
- **Link, don't embed**: All references to model versions, bucket addresses, or image tags MUST read from `config.py` rather than being hardcoded into the pipeline strings.
