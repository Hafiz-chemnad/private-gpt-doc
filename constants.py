import os
from dotenv import load_dotenv

load_dotenv()

# --- Directories ---
# Define the folder for storing processed documents (vector database)
PERSIST_DIRECTORY = os.environ.get('PERSIST_DIRECTORY', 'db') # Default to 'db' if not set

# Define the folder for storing source documents (uploaded files)
SOURCE_DIRECTORY = os.environ.get('SOURCE_DIRECTORY', 'source_documents') # Default to 'source_documents'

# --- Embedding Model ---
# Name of the embeddings model to use (e.g., 'all-MiniLM-L6-v2')
EMBEDDINGS_MODEL_NAME = os.environ.get('EMBEDDINGS_MODEL_NAME', 'intfloat/multilingual-e5-large')

# --- LLM Settings (for Ollama) ---
# Type of LLM (currently supports "Ollama")
MODEL_TYPE = os.environ.get('MODEL_TYPE', 'Ollama')

# Name of the Ollama model to use (e.g., 'phi3', 'llama3')
# This should match the model you have pulled with `ollama pull <model_name>`
OLLAMA_MODEL_NAME = os.environ.get('OLLAMA_MODEL_NAME', 'phi3:mini') # Default to 'phi3'

# Context window size for the LLM
# This affects how much text the LLM can "see" at once. Higher values require more RAM.
# Adjust based on your available RAM and the model's capabilities.
# Ollama's `num_ctx` corresponds to this.
MODEL_N_CTX = int(os.environ.get('MODEL_N_CTX', 4096)) # Default to 4096 (common for smaller models)

# Number of tokens to predict in the response.
# Higher values mean longer answers, but consume more VRAM/RAM during generation.
MAX_NEW_TOKENS = int(os.environ.get('MAX_NEW_TOKENS', 512)) # Default to 512

# Temperature for LLM generation (controls randomness).
# Lower values (e.g., 0.0-0.3) make output more deterministic/factual.
# Higher values (e.g., 0.7-1.0) make output more creative/diverse.
TEMPERATURE = float(os.environ.get('TEMPERATURE', 0.2)) # Default to 0.2

# --- Document Processing Settings ---
# Chunk size for text splitting (how many characters in each text chunk)
CHUNK_SIZE = int(os.environ.get('CHUNK_SIZE', 500))

# Chunk overlap for text splitting (how many characters overlap between chunks)
CHUNK_OVERLAP = int(os.environ.get('CHUNK_OVERLAP', 50))

# Number of relevant chunks to retrieve from the vector store
TARGET_SOURCE_CHUNKS = int(os.environ.get('TARGET_SOURCE_CHUNKS', 4))

# --- ChromaDB Settings (if using a client) ---
# For a persistent, embedded ChromaDB (default), these usually aren't strictly necessary,
# but can be helpful for explicit configuration if you scale up.
# If you run into issues, you might need to adjust or remove this if not strictly needed
# by your ChromaDB version and usage.

# --- Flag to hide source documents in the final answer ---
# Set to True to hide the source documents that contributed to the answer.
HIDE_SOURCE_DOCUMENTS = os.environ.get('HIDE_SOURCE_DOCUMENTS', 'False').lower() == 'true'