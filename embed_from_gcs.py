import os
import uuid
import tiktoken
from google.cloud import storage
from openai import OpenAI
from pinecone.grpc import PineconeGRPC as Pinecone

# --- Configuration ---
# Ensure you have your environment variables set before running:
# - GOOGLE_APPLICATION_CREDENTIALS (path to your GCP service account JSON key)
# - OPENAI_API_KEY
# - PINECONE_API_KEY
# - GCS_BUCKET_NAME (e.g., "pie-data")
# - GCS_PREFIX (e.g., "qayim.kanji@ashbury.ca/output_md/")
# - PINECONE_INDEX_NAME (e.g., "pie-index-openai")
# - USER_EMAIL (e.g., "qayim.kanji@ashbury.ca")
BUCKET_NAME = os.environ["GCS_BUCKET_NAME"]
PREFIX = os.environ["GCS_PREFIX"]
PINECONE_INDEX_NAME = os.environ["PINECONE_INDEX_NAME"]
USER_EMAIL = os.environ["USER_EMAIL"]
EMBEDDING_MODEL = "text-embedding-3-small"
MAX_TOKENS = 500
OVERLAP = 50

def chunk_text(text: str, max_tokens: int = MAX_TOKENS, overlap: int = OVERLAP) -> list[str]:
    """Splits text into token-sized chunks with slight overlap."""
    encoder = tiktoken.get_encoding("cl100k_base")
    tokens = encoder.encode(text)
    
    chunks = []
    i = 0
    while i < len(tokens):
        chunk_tokens = tokens[i : i + max_tokens]
        chunk_text = encoder.decode(chunk_tokens)
        chunks.append(chunk_text)
        i += max_tokens - overlap
    return chunks

def main():
    # Initialize clients
    gcs_client = storage.Client()
    openai_client = OpenAI() # Assumes OPENAI_API_KEY is an environment variable
    pc = Pinecone()          # Assumes PINECONE_API_KEY is an environment variable

    # Get Pinecone index
    index = pc.Index(PINECONE_INDEX_NAME)
    bucket = gcs_client.bucket(BUCKET_NAME)
    
    # List all markdown files in the specified GCS folder
    blobs = bucket.list_blobs(prefix=PREFIX)
    md_blobs = [blob for blob in blobs if blob.name.endswith(".md")]
    
    print(f"Found {len(md_blobs)} markdown files in gs://{BUCKET_NAME}/{PREFIX}")

    for blob in md_blobs:
        print(f"Processing {blob.name}...")
        # Download text content
        content = blob.download_as_text()
        if not content.strip():
            continue
            
        # Optional: Extract notebook name or title from the file path for metadata
        file_name = os.path.basename(blob.name)
        
        # Chunk the text
        chunks = chunk_text(content, MAX_TOKENS, OVERLAP)
        
        for i, chunk in enumerate(chunks):
            # Generate OpenAI embedding
            response = openai_client.embeddings.create(
                input=[chunk],
                model=EMBEDDING_MODEL,
                dimensions=512
            )
            embedding_vector = response.data[0].embedding
            
            # Prepare metadata (needed for RAG filtering later in the webapp)
            metadata = {
                "user_email": USER_EMAIL,
                "source_file": file_name,
                "text": chunk,
                "chunk_index": i
            }
            
            # Upsert into Pinecone
            chunk_id = f"{file_name}-chunk-{i}-{uuid.uuid4().hex[:8]}"
            
            index.upsert(
                vectors=[
                    {
                        "id": chunk_id,
                        "values": embedding_vector,
                        "metadata": metadata
                    }
                ]
            )
            
        print(f"Upserted {len(chunks)} chunks for {file_name}")

if __name__ == "__main__":
    main()
