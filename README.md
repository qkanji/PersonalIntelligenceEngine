# Personal Intelligence Engine (PIE)

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Next.js](https://img.shields.io/badge/Next-black?style=for-the-badge&logo=next.js&logoColor=white)
![React](https://img.shields.io/badge/react-%2320232a.svg?style=for-the-badge&logo=react&logoColor=%2361DAFB)
![Google Cloud](https://img.shields.io/badge/GoogleCloud-%234285F4.svg?style=for-the-badge&logo=google-cloud&logoColor=white)
![RunPod](https://img.shields.io/badge/RunPod-3F0F4E.svg?style=for-the-badge&logo=runpod&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-%23412991.svg?style=for-the-badge&logo=openai&logoColor=white)
![Pinecone](https://img.shields.io/badge/Pinecone-white?style=for-the-badge&logo=pinecone&logoColor=black)

**A distributed local-to-cloud RAG pipeline that extracts handwritten OneNote notebooks, orchestrates GPU-accelerated OCR via pre-built Docker containers on spot instances, and serves vector-embedded notes to an AI chat interface.**

![Demo 1](demo_images/demo1.png)
![Demo 2](demo_images/demo2.png)
![Demo 3](demo_images/demo3.png)

## Features & Architecture

- **COM-Bound Local Extraction:** Microsoft Graph API fails to OCR Apple Pencil ink or raw drawing layers. To bypass this, the pipeline uses the Windows COM API against the OneNote 2016 desktop client to programmatically export individual pages as high-fidelity PDFs, which are subsequently rasterized into PNGs and pushed to Google Cloud Storage (GCS).
- **Spot Instance Orchestration:** Uses a free-tier Google Cloud Platform `e2-micro` VM as an orchestrator. It listens to a Pub/Sub queue and dynamically provisions RunPod Community Cloud 4090 Spot Instances to execute high-throughput containerized OCR tasks.
- **Containerized Inference (Zero Cold-Start Waste):** The worker environment is baked into a custom Docker image containing PyTorch, CUDA bindings, and vLLM. The orchestrator instructs RunPod to pull this image and injects all required environment variables directly into the container's `cmd` execution payload. This completely eliminates expensive runtime setup latency (installing dependencies/model weights) during spot instance boots.
- **Fault-Tolerant Vision-Language Processing:** The containerized worker utilizes vLLM streaming to evaluate the community-quantized `lovedheart/Qwen3.5-9B-FP8` model, translating handwritten PNGs to Markdown. By deploying a pre-quantized FP8 model, the container aggressively maximizes memory efficiency and inference throughput on the allocated 4090s. It writes `.md` files to GCS sequentially. If a spot instance is preempted, the GCP orchestrator detects the termination via the RunPod API, respawns the pod, and resumes the exact state until a `done.json` marker is emitted.
- **Vector Retrieval System:** Processed Markdown is embedded locally with OpenAI's `text-embedding-3-small` and upserted to Pinecone.
- **Next.js Frontend:** A React web application utilizing Vercel's AI SDK to stream responses from `gpt-5-nano`, augmented by the Pinecone retrieval chain, with full Math/KaTeX parsing support.

## Tech Stack

- **Extraction:** Windows PowerShell COM API, Python `win32com`, `pypdfium2`
- **Orchestration:** Google Cloud Storage (GCS), GCP Pub/Sub, RunPod API
- **Cloud Worker:** Docker, PyTorch (cu126), vLLM, `lovedheart/Qwen3.5-9B-FP8`
- **Retrieval:** OpenAI API (`text-embedding-3-small`), Pinecone GRPC
- **Frontend:** Next.js (App Router), React, Tailwind CSS, Vercel AI SDK

## Scope & Limitations

This infrastructure was engineered as a targeted solution for processing personal high school exam notes.

- **Work in Progress (WIP):** This project is actively in development. Because it is highly unabstracted and constrained, components like the Next.js frontend are exclusively run via local development servers (`npm run dev`) and are not hardened for production deployment.
- **Data Structure:** It intentionally ignores the `_Content Library` section group specific to standard Class Notebooks to avoid duplicating reference material against personal student notes.
- **Single-Tenant Architecture:** It relies on strict local directories and hardcoded bucket structures for a single authorized user (`qayim.kanji@ashbury.ca`). The web application is explicitly designed for personal use, hardcoding greetings ("Hi Qayim") and personal avatars into the component tree.
- **OS Constraint:** The local extraction sequence requires physical Windows hardware with the Microsoft OneNote 2016 desktop application installed.

---

## Architecture Flow

```mermaid
graph TD
    subgraph Local Environment [Windows Desktop]
        A[OneNote 2016] -->|COM API| B[1_extract_onenote.py]
        B -->|PDFs| C[b1.py: PDF to PNG]
    end

    subgraph Google Cloud Platform
        C -->|Upload Directory| D[(GCS Bucket)]
        C -->|Publish Event| E[Pub/Sub Queue]
        E -->|Listen| F[e2-micro Orchestrator]
    end

    subgraph RunPod [GPU Spot Instances]
        F -->|Provision & Inject Env Vars| G[Docker Container RTX 4090]
        G -->|Pull PNGs| D
        G -->|vLLM / Qwen3.5-9B-FP8| H[Process Markdown]
        H -->|Write .md & done.json| D
        F -.->|Polled Health Checks & Restart| G
    end

    subgraph Local Computer [Local Vector Indexing]
        D -->|Download .md| I[embed_from_gcs.py]
        I -->|OpenAI text-embedding-3-small| J[(Pinecone Vector DB)]
    end

    subgraph Web App [Next.js RAG Loop]
        K[Chat UI] -->|User Prompt| L[Vercel AI SDK]
        L -->|Semantic Filter| J
        J -->|Context Documents| M[gpt-5-nano]
        M -->|Stream Response| K
    end
```

## Local Setup

**Please reference `SETUP.md` for exhaustive instructions on securely configuring the required environment variables and API keys prior to execution.**

1.  **Extract Data Pipeline:** Dump the Windows notebook tree to PDFs based on COM API interactions:
    ```powershell
    python 1_extract_onenote.py
    ```
2.  **Stage to Cloud:** Render those PDFs to PNGs and stage them in GCS while publishing to the Pub/Sub orchestrator:
    ```powershell
    python b1.py --user-email "you@example.com"
    ```
    _(The remote GCP orchestrator takes over here, booting the RunPod Docker container. Wait until `done.json` populates in your GCS bucket.)_
3.  **Embed:** Pull the finalized `.md` cloud output, batch process the tokens with `tiktoken`, and populate your Pinecone index:
    ```powershell
    python embed_from_gcs.py
    ```
4.  **Start Server:** Boot the Next.js chat interface:
    ```powershell
    cd webapp
    npm run dev
    ```
