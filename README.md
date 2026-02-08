# Personal Intelligence Engine - OneNote RAG System

A local RAG (Retrieval-Augmented Generation) system that uses OneNote notebooks as the primary knowledge base for study and learning. Built for high school students to query their course content stored in OneNote.

## System Requirements

- **OS**: Windows 11
- **Python**: 3.10+
- **OneNote**: Desktop App installed
- **GPU**: NVIDIA GPU with CUDA 12.9 (optional, for faster processing)
- **RAM**: 32GB recommended (for large notebooks)
- **Storage**: ~5GB for models (downloaded on first run)

## Features

- 📚 **Page-by-Page Export**: Preserves notebook structure with metadata
- 🤖 **AI-Powered OCR**: Uses marker-pdf with deep learning models for text, tables, and handwriting
- ⚡ **GPU Acceleration**: Automatic CUDA support for faster processing
- 🔍 **Vector Search**: ChromaDB for efficient semantic search
- 💬 **Chat Interface**: Query your notes with AI assistance (Phase 5)

## Project Phases

### Phase 1: OneNote Extraction
Export OneNote notebooks as individual PDF pages with structure preserved.

**For Cloud/SharePoint Notebooks** (recommended):
1. Export `.onepkg` files from SharePoint/OneDrive OneNote
2. Import locally into OneNote Desktop (File → Open → Import)
3. Run the extraction:
   ```powershell
   python 1_extract_onenote.py
   ```

**Note**: Direct export from SharePoint notebooks isn't supported by Microsoft's COM API.

### Phase 2: PDF to Markdown Conversion
Convert PDF pages to structured Markdown using marker-pdf.

```powershell
python 2_ocr_process.py
```

**What it does**:
- Loads marker-pdf models (Surya OCR, layout detection, table recognition)
- Processes each page with GPU acceleration
- Extracts text, images, tables, and handwritten content
- Creates Markdown files with full metadata
- Shows progress with time estimates

**Output**: One `.md` file per page in `notebooks_md/`

### Phase 3-4: Embeddings & Vector Storage
Generate embeddings and store in ChromaDB.

```powershell
python 3_generate_embeddings.py
```

**Models**:
- **GPU Mode**: BGE-M3 (better quality, multilingual)
- **CPU Mode**: all-MiniLM-L6-v2 (faster, English-focused)

### Phase 5: Chat Interface
Query your notebooks using natural language.

```powershell
python 5_chat.py
```

Retrieves relevant content and sends to LLM for answers.

## Project Structure

```
PersonalIntelligenceEngine/
├── notebooks_pdf/              # Exported PDFs (page-by-page)
│   └── [Notebook Name]/
│       ├── _structure.json     # Metadata & page order
│       └── [Section]/
│           └── 000_PageName.pdf
├── notebooks_md/               # Converted Markdown files
├── chroma_db/                  # Vector embeddings (ChromaDB)
├── phase1_extract/             # OneNote export modules
│   ├── discovery.py            # Notebook discovery
│   ├── export.py               # Export orchestration
│   ├── structure.py            # XML parsing
│   ├── batch_export.py         # Batched PDF export
│   └── powershell.py           # PowerShell utilities
├── phase2_ocr/                 # PDF processing modules
│   ├── marker_engine.py        # marker-pdf wrapper
│   └── utils.py                # Helper functions
├── 1_extract_onenote.py        # Phase 1: Export notebooks
├── 2_ocr_process.py            # Phase 2: PDF → Markdown
├── 3_generate_embeddings.py    # Phase 3-4: Embeddings (TODO)
├── 5_chat.py                   # Phase 5: Chat interface (TODO)
├── setup.py                    # Dependency installer
└── requirements.txt            # Python dependencies
```

## Getting Started

### 1. Setup Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

### 2. Install Dependencies
```powershell
pip install -r requirements.txt
```

**Or** use the automated installer:
```powershell
python setup.py
```

This will:
- Detect CUDA availability
- Install marker-pdf with PyTorch (GPU or CPU)
- Install sentence-transformers and ChromaDB
- Configure for optimal performance

### 3. Extract Notebooks (Phase 1)
```powershell
python 1_extract_onenote.py
```

**For SharePoint/Cloud Notebooks**:
1. Export as `.onepkg` from OneNote Online
2. Import into OneNote Desktop App
3. Run the extraction script

### 4. Convert to Markdown (Phase 2)
```powershell
python 2_ocr_process.py
```

First run downloads ~2GB of AI models. Progress shows:
- Pages processed
- Time elapsed
- Estimated time remaining

### 5. Generate Embeddings (Phase 3-4)
```powershell
python 3_generate_embeddings.py
```
*(Coming soon)*

### 6. Start Chatting (Phase 5)
```powershell
python 5_chat.py
```
*(Coming soon)*

## Technical Details

### Phase 2: marker-pdf Processing

**Models Used**:
- **Surya OCR**: Text recognition (supports handwriting)
- **Layout Detection**: Identifies columns, tables, headers
- **Table Recognition**: Extracts table structure
- **OCR Error Detection**: Improves accuracy

**Performance**:
- **GPU** (RTX 3050): ~15-30 seconds per page
- **CPU**: ~1-2 minutes per page

**Output Format**:
```markdown
---
source_pdf: C:\...\page.pdf
notebook: Science Notebook
section: Chemistry/Atoms
page: Atomic Structure
order: 5
---

# Atomic Structure

[Extracted content with formatting preserved]
```

### Why Local?

- ✅ **Free**: No API costs
- ✅ **Private**: Your data stays on your computer
- ✅ **Offline**: Works without internet
- ✅ **Fast**: GPU acceleration when available
