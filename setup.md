# Personal Intelligence Engine (PIE) Setup

To successfully deploy and run both the Next.js web application and the RunPod OCR worker, you need to configure the correct environment variables across the project.

## 1. Webapp (`webapp/.env.local`)

Create a `.env.local` file inside the `webapp/` directory. These are used by the Vercel Next.js serverless functions to perform embeddings and execute the LLM.

```env
# OpenAI for text-embedding-3-small and gpt-5-nano
OPENAI_API_KEY="sk-..."

# Pinecone for Vector Database Storage (RAG)
PINECONE_API_KEY="pcsk_..."
PINECONE_INDEX_NAME="YOUR_PINECONE_INDEX"

# Filtering metrics to link queries to specific user content
USER_EMAIL="user@example.com"
```

## 2. Infrastructure Deployment Scripts (Python Root)

If you are running `push_note.py`, `orchestrator/main.py`, or `webapp/scripts/embed_from_gcs.py`, your terminal environment must have the following variables assigned before execution:

```bash
# General
GCP_PROJECT="your-google-cloud-project-id"
GCS_BUCKET="your-gcs-bucket-name"
USER_EMAIL="user@example.com"

# For GCP Pub/Sub triggers
PUBSUB_TOPIC="your-pubsub-topic"

# For GCS Authentication (if running locally outside Google Cloud)
GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account.json"

# For explicitly embedding and pushing local files to Pinecone
GCS_PREFIX="user@example.com/output_md/"
PINECONE_INDEX_NAME="YOUR_PINECONE_INDEX"
OPENAI_API_KEY="sk-..."
PINECONE_API_KEY="pcsk_..."
```

## 3. RunPod Worker (Orchestrator Injection)

When the orchestrator automatically provisions a Spot Instance on RunPod, it dynamically passes these environment variables into the Docker container.

Configure these in your Orchestrator's `.env` or system environment:

```bash
# RunPod Management
RUNPOD_API_KEY="your-runpod-api-key"

# The worker needs to read PDFs and output Markdown to this bucket:
GCS_BUCKET="your-gcs-bucket-name"

# (Optional dependencies mapping to specific GPU network setups)
HUGGING_FACE_HUB_TOKEN="hf_..."
```

_Note: The RunPod worker handles GPU OCR (Qwen 3.5) exclusively. It uploads raw Markdown files back to GCS. The `embed_from_gcs.py` script then asynchronously pulls them down to embed using OpenAI and upserts them to Pinecone._
