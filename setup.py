"""
Setup script for OneNote RAG System.
Installs required dependencies based on CUDA availability.
"""

import subprocess
import sys


def check_cuda_available():
    """Check if CUDA is available on the system."""
    try:
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def install_package(package):
    """Install a package using pip."""
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])


def main():
    """Main setup function."""
    print("=" * 50)
    print("OneNote RAG System - Setup")
    print("=" * 50)

    cuda_available = check_cuda_available()
    print(f"\nCUDA Available: {cuda_available}")

    # Install base dependencies
    print("\n[1/4] Installing base dependencies...")
    base_packages = [
        "pywin32>=306",
        "Pillow>=10.0.0",
        "tqdm>=4.66.0",
    ]
    for pkg in base_packages:
        print(f"  Installing {pkg}...")
        install_package(pkg)

    # Install PyTorch (GPU or CPU)
    print("\n[2/4] Installing PyTorch...")
    if cuda_available:
        print("  Installing PyTorch with CUDA 12.9 support...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "torch", "--index-url",
            "https://download.pytorch.org/whl/cu129"
        ])
    else:
        print("  Installing PyTorch CPU version...")
        install_package("torch")

    # Install marker-pdf
    print("\n[3/4] Installing marker-pdf...")
    print("  Installing marker-pdf (includes Surya OCR)...")
    install_package("marker-pdf>=1.0.0")

    # Install embedding and vector DB packages
    print("\n[4/4] Installing embedding and vector DB packages...")
    install_package("sentence-transformers>=2.2.0")
    install_package("chromadb>=0.4.0")

    print("\n" + "=" * 50)
    print("Setup complete!")
    print("=" * 50)

    if cuda_available:
        print("\nGPU Mode: marker-pdf with CUDA + BGE-M3 embeddings")
    else:
        print("\nCPU Mode: marker-pdf CPU + all-MiniLM-L6-v2 embeddings")

    print("\nNext step: Run 'python 1_extract_onenote.py' to extract notebooks")


if __name__ == "__main__":
    main()
