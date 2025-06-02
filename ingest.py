#!/usr/bin/env python3
import os
import glob
from typing import List, Dict, Any
from multiprocessing import Pool
from tqdm import tqdm

# Import constants from our new constants.py
from constants import (
    PERSIST_DIRECTORY,
    SOURCE_DIRECTORY,
    EMBEDDINGS_MODEL_NAME,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    # Import CHROMA_SETTINGS
)

# LangChain Document Loaders
from langchain_community.document_loaders import (
    CSVLoader,
    EverNoteLoader,
    PyMuPDFLoader, # Prefer PyMuPDFLoader for PDFs
    TextLoader,
    UnstructuredEmailLoader,
    UnstructuredEPubLoader,
    UnstructuredHTMLLoader,
    UnstructuredMarkdownLoader,
    UnstructuredODTLoader,
    UnstructuredPowerPointLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredFileLoader, # General fallback loader
)

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma.vectorstores import Chroma
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain.docstore.document import Document # For type hinting


# Custom document loaders (Keep if you need custom logic for certain file types)
class MyElmLoader(UnstructuredEmailLoader):
    """Wrapper to fallback to text/plain when default does not work"""
    def load(self) -> List[Document]:
        try:
            try:
                doc = UnstructuredEmailLoader.load(self)
            except ValueError as e:
                if 'text/html content not found in email' in str(e):
                    self.unstructured_kwargs["content_source"]="text/plain"
                    doc = UnstructuredEmailLoader.load(self)
                else:
                    raise
        except Exception as e:
            # Add file_path to exception message
            raise type(e)(f"{self.file_path}: {e}") from e
        return doc


# Map file extensions to document loaders and their arguments
# Prefer PyMuPDFLoader for PDFs
LOADER_MAPPING = {
    ".csv": (CSVLoader, {}),
    ".doc": (UnstructuredWordDocumentLoader, {}),
    ".docx": (UnstructuredWordDocumentLoader, {}),
    ".enex": (EverNoteLoader, {}),
    ".eml": (MyElmLoader, {}),
    ".epub": (UnstructuredEPubLoader, {}),
    ".html": (UnstructuredHTMLLoader, {}),
    ".htm": (UnstructuredHTMLLoader, {}), # Added .htm for consistency
    ".md": (UnstructuredMarkdownLoader, {}),
    ".odt": (UnstructuredODTLoader, {}),
    ".pdf": (PyMuPDFLoader, {}), # Changed to PyMuPDFLoader
    ".ppt": (UnstructuredPowerPointLoader, {}),
    ".pptx": (UnstructuredPowerPointLoader, {}),
    ".txt": (TextLoader, {"encoding": "utf8"}),
    # Add more mappings for other file extensions and loaders as needed
}

def load_single_document(file_path: str) -> Document:
    ext = "." + file_path.rsplit(".", 1)[-1].lower() # Ensure lowercase extension
    if ext in LOADER_MAPPING:
        loader_class, loader_args = LOADER_MAPPING[ext]
        try:
            loader = loader_class(file_path, **loader_args)
            return loader.load()[0]
        except Exception as e:
            print(f"Warning: Could not load {file_path} with {loader_class.__name__}: {e}. Trying UnstructuredFileLoader as fallback.")
            # Fallback to UnstructuredFileLoader if specific loader fails
            try:
                return UnstructuredFileLoader(file_path).load()[0]
            except Exception as fe:
                raise ValueError(f"Failed to load {file_path} even with fallback UnstructuredFileLoader: {fe}") from fe
    else:
        # Fallback to UnstructuredFileLoader for unknown types or if no specific loader
        print(f"Warning: No specific loader for {ext}. Trying UnstructuredFileLoader for {file_path}.")
        try:
            return UnstructuredFileLoader(file_path).load()[0]
        except Exception as fe:
            raise ValueError(f"Failed to load {file_path} with UnstructuredFileLoader: {fe}") from fe


def load_documents(source_dir: str, ignored_files: List[str] = []) -> List[Document]:
    """
    Loads all documents from the source documents directory, ignoring specified files
    """
    all_files = []
    # Collect all files that match any supported extension
    for ext in LOADER_MAPPING:
        all_files.extend(
            glob.glob(os.path.join(source_dir, f"**/*{ext}"), recursive=True)
        )
    # Also include files that might be handled by UnstructuredFileLoader by default
    # You might need to adjust this if you have many non-document files in source_dir
    # For now, let's stick to LOADER_MAPPING extensions primarily.
    # If you want to allow all files, use:
    # all_files = glob.glob(os.path.join(source_dir, f"**/*"), recursive=True)

    filtered_files = [file_path for file_path in all_files if file_path not in ignored_files]

    documents = []
    if not filtered_files:
        print("No new documents to load from source directory.")
        return []

    # Use multiprocessing Pool for parallel loading with tqdm
    # Ensure this is safe when run from FastAPI background tasks.
    # For very small numbers of files, direct iteration might be simpler.
    # For now, keep Pool as it's in your original code.
    with Pool(processes=os.cpu_count()) as pool:
        with tqdm(total=len(filtered_files), desc='Loading documents', ncols=80) as pbar:
            for i, doc in enumerate(pool.imap_unordered(load_single_document, filtered_files)):
                if doc: # Only append if document was successfully loaded
                    documents.append(doc)
                pbar.update()

    print(f"Loaded {len(documents)} documents.")
    return documents


def process_documents(document_paths: List[str] = None) -> List[Document]:
    """
    Load specific documents (if paths are provided) or all from SOURCE_DIRECTORY,
    then split them into chunks.
    """
    if document_paths:
        # Load only the specified documents
        print(f"Processing {len(document_paths)} new document(s)...")
        documents = []
        for path in tqdm(document_paths, desc='Loading new documents', ncols=80):
            try:
                documents.append(load_single_document(path))
            except ValueError as e:
                print(f"Error loading {path}: {e}")
                # Optionally remove the problematic file or log extensively
                os.remove(path) # Delete problematic file to prevent re-attempts
                print(f"Removed problematic file: {path}")
        if not documents:
            print("No documents successfully loaded for processing.")
            return []
    else:
        # Load all documents from source directory (original ingest.py behavior)
        print(f"Loading documents from {SOURCE_DIRECTORY}")
        documents = load_documents(SOURCE_DIRECTORY)
        if not documents:
            print("No documents to load from source directory.")
            return []

    print(f"Splitting {len(documents)} document(s) into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    texts = text_splitter.split_documents(documents)
    print(f"Split into {len(texts)} chunks of text (max. {CHUNK_SIZE} tokens each)")
    return texts

def does_vectorstore_exist() -> bool:
    """
    Checks if vectorstore exists at PERSIST_DIRECTORY.
    """
    if os.path.exists(os.path.join(PERSIST_DIRECTORY, 'index')):
        # Check for specific ChromaDB files (might vary by ChromaDB version)
        if os.path.exists(os.path.join(PERSIST_DIRECTORY, 'chroma-collections.parquet')) and \
           os.path.exists(os.path.join(PERSIST_DIRECTORY, 'chroma-embeddings.parquet')):
            # Check if there are some index files indicating a non-empty DB
            list_index_files = glob.glob(os.path.join(PERSIST_DIRECTORY, 'index/*.bin'))
            list_index_files += glob.glob(os.path.join(PERSIST_DIRECTORY, 'index/*.pkl'))
            if len(list_index_files) > 0: # At least some files should exist
                return True
    return False

# --- Core Ingestion Function for API ---
def ingest_documents(new_document_paths: List[str] = None) -> Dict[str, Any]:
    """
    Main ingestion function. Creates or updates the vector store.
    Args:
        new_document_paths (List[str], optional): List of paths to new documents
                                                to ingest. If None, all documents
                                                in SOURCE_DIRECTORY are ingested
                                                (or updated).
    Returns:
        Dict: A dictionary containing success/error message and number of chunks.
    """
    try:
        # Create embeddings
        print(f"Initializing embeddings with {EMBEDDINGS_MODEL_NAME}...")
        embeddings = HuggingFaceEmbeddings(model_name=EMBEDDINGS_MODEL_NAME, model_kwargs={'device': 'cpu'})
        print("Embeddings initialized.")

        db = None
        texts_to_add = []
        ingested_count = 0

        # Check if vectorstore exists
        if does_vectorstore_exist():
            print(f"Appending to existing vectorstore at {PERSIST_DIRECTORY}")
            db = Chroma(persist_directory=PERSIST_DIRECTORY, embedding_function=embeddings)
            # Retrieve existing sources to avoid re-ingesting
            existing_sources = set()
            try:
                collection = db.get(ids=None, where={}, include=['metadatas']) # Fetch all metadatas
                if collection and 'metadatas' in collection:
                    existing_sources = {metadata.get('source') for metadata in collection['metadatas'] if 'source' in metadata}
            except Exception as e:
                print(f"Warning: Could not retrieve existing documents from ChromaDB: {e}. Proceeding as if new DB.")
                # If cannot retrieve existing, treat as new DB or force re-ingestion
                existing_sources = set()

            if new_document_paths:
                # If specific new paths are provided, only process those not already in DB
                files_to_process = [p for p in new_document_paths if p not in existing_sources]
                if not files_to_process:
                    print("All provided documents already in vectorstore. Nothing to ingest.")
                    return {"message": "All provided documents already in vectorstore.", "chunks_ingested": 0}
                texts_to_add = process_documents(files_to_process)
            else:
                # If no specific paths, process all new documents from SOURCE_DIRECTORY
                all_source_files = []
                for ext in LOADER_MAPPING:
                    all_source_files.extend(
                        glob.glob(os.path.join(SOURCE_DIRECTORY, f"**/*{ext}"), recursive=True)
                    )
                files_to_process = [f for f in all_source_files if f not in existing_sources]
                if not files_to_process:
                    print("No new documents found in source directory to ingest.")
                    return {"message": "No new documents to ingest.", "chunks_ingested": 0}
                texts_to_add = process_documents(files_to_process)

            if texts_to_add:
                print(f"Adding {len(texts_to_add)} new chunks to vectorstore...")
                db.add_documents(texts_to_add)
                ingested_count = len(texts_to_add)
        else:
            # Create new vectorstore
            print("Creating new vectorstore...")
            # If new_document_paths are provided, only process those.
            # Otherwise, process all from SOURCE_DIRECTORY.
            texts_to_add = process_documents(new_document_paths)
            if not texts_to_add:
                return {"message": "No documents found to create a new vectorstore.", "chunks_ingested": 0}
            print(f"Adding {len(texts_to_add)} chunks to new vectorstore...")
            db = Chroma.from_documents(texts_to_add, embeddings, persist_directory=PERSIST_DIRECTORY)
            ingested_count = len(texts_to_add)

        if db:
           
            db = None # Clear DB from memory
            print(f"Ingestion complete! {ingested_count} chunks added.")
            return {"message": "Ingestion successful!", "chunks_ingested": ingested_count}
        else:
            return {"message": "No database operation performed.", "chunks_ingested": 0}

    except Exception as e:
        import traceback
        traceback.print_exc() # Print full traceback to console for debugging
        return {"error": f"An error occurred during ingestion: {e}", "chunks_ingested": 0}


# --- Original command-line main function (optional, removed for API) ---
# Removed the `main()` function with `if __name__ == "__main__":` block.
# This file now acts as a module providing `ingest_documents`.

if __name__ == "__main__":
    # This block will only run if ingest.py is executed directly.
    # It provides a simple command-line interface for testing the function.
    print("Running ingest.py in standalone mode.")
    result = ingest_documents()
    if "error" in result:
        print(f"Ingestion failed: {result['error']}")
    else:
        print(f"Ingestion result: {result['message']} ({result['chunks_ingested']} chunks).")
    print("You can now run privateGPT.py to query your documents.")