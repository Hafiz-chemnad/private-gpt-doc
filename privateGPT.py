#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv

# Import constants from our new constants.py
from constants import (
    EMBEDDINGS_MODEL_NAME,
    PERSIST_DIRECTORY,
    MODEL_TYPE,
    OLLAMA_MODEL_NAME,
    MODEL_N_CTX,
    MAX_NEW_TOKENS,
    TEMPERATURE,
    TARGET_SOURCE_CHUNKS,
    HIDE_SOURCE_DOCUMENTS,
    # Assuming CHROMA_SETTINGS is defined there
)

from langchain.chains import RetrievalQA
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain_chroma.vectorstores import Chroma
from langchain_community.llms import Ollama
from langchain_core.prompts import PromptTemplate
from langchain.docstore.document import Document # For type hinting source documents


# Load environment variables (ensure .env is loaded for current execution, though constants.py handles it)
load_dotenv()


# --- Core QA Function for API ---
def get_answer_from_privateGPT(query: str):
    """
    Processes a user query against the loaded documents using a private LLM.
    Returns the answer and source documents.
    """
    # 1. Initialize Embeddings
    try:
        # Force device to 'cpu' as specified in your original code
        embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDINGS_MODEL_NAME,
            model_kwargs={'device': 'cpu'
            }
        )
    except Exception as e:
        print(f"\n--- ERROR: Failed to initialize HuggingFaceEmbeddings: {e}", file=sys.stderr)
        return {"error": f"Failed to initialize embeddings: {e}. Check EMBEDDINGS_MODEL_NAME or internet connection."}

    # 2. Load Chroma DB
    try:
        db = Chroma(
            persist_directory=PERSIST_DIRECTORY,
            embedding_function=embeddings,
            # Use CHROMA_SETTINGS from constants
        )
        retriever = db.as_retriever(search_kwargs={"k": TARGET_SOURCE_CHUNKS})
    except Exception as e:
        print(f"\n--- ERROR: Failed to load Chroma DB or initialize retriever: {e}", file=sys.stderr)
        return {"error": f"Failed to load document database: {e}. Ensure documents are ingested."}


    # 3. Initialize LLM (Ollama)
    llm = None
    if MODEL_TYPE == "Ollama":
        try:
            llm = Ollama(
                model=OLLAMA_MODEL_NAME,
                temperature=TEMPERATURE,
                num_ctx=MODEL_N_CTX,
                num_predict=MAX_NEW_TOKENS
            )
        except Exception as e:
            print(f"\n--- ERROR: Failed to initialize Ollama LLM: {e}", file=sys.stderr)
            return {"error": f"Failed to load Ollama model '{OLLAMA_MODEL_NAME}': {e}. Is Ollama server running and model pulled?"}
    else:
        return {"error": f"Model type '{MODEL_TYPE}' not supported for API integration."}

    if llm is None:
        return {"error": "LLM failed to initialize."}

    # 4. Define Prompt Template
    custom_template = """Use the following pieces of context to answer the user's question.
    If you don't know the answer, just say that you don't know, don't try to make up an answer.

    {context}

    Question: {question}
    Helpful Answer:"""

    custom_prompt = PromptTemplate(
        template=custom_template,
        input_variables=["context", "question"]
    )

    # 5. Create RetrievalQA Chain
    qa = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=not HIDE_SOURCE_DOCUMENTS, # Use HIDE_SOURCE_DOCUMENTS from constants
        chain_type_kwargs={"prompt": custom_prompt}
    )

    # 6. Invoke QA Chain and Process Result
    try:
        res = qa.invoke({"query": query})
        answer = res.get('result', "No answer found.")
        source_documents = res.get('source_documents', [])

        # Format source documents for easier frontend consumption
        formatted_sources = []
        if not HIDE_SOURCE_DOCUMENTS:
            for doc in source_documents:
                # Ensure doc is a Document object and has metadata/page_content
                if isinstance(doc, Document):
                    formatted_sources.append({
                        "page_content": doc.page_content,
                        "metadata": doc.metadata
                    })
                else:
                    # Handle cases where `doc` might not be a Document object (unlikely if LangChain works)
                    print(f"Warning: Unexpected source document type: {type(doc)}", file=sys.stderr)
                    formatted_sources.append({"page_content": str(doc), "metadata": {}})


        return {
            "answer": answer,
            "source_documents": formatted_sources
        }

    except Exception as e:
        # Catch specific Ollama crash error if it occurs frequently
        error_message = str(e)
        if "llama runner process has terminated: exit status 2" in error_message or "context window" in error_message.lower():
            return {"error": f"Ollama model might have crashed or exceeded context window. Try a shorter query or increase MODEL_N_CTX/reduce MAX_NEW_TOKENS in .env. Original error: {error_message}"}
        
        print(f"\n--- ERROR: An unexpected error occurred during query processing: {e}", file=sys.stderr)
        return {"error": f"An unexpected error occurred during query processing: {e}"}


# --- Original command-line main function (optional, removed for API) ---
# Removed the `main()` function with `argparse` and `while True` loop
# This file now acts as a module providing `get_answer_from_privateGPT`

# If you still want a CLI entry point for testing, you can add a simplified one:
if __name__ == "__main__":
    # This block will only run if privateGPT.py is executed directly.
    # It provides a simple command-line interface for testing the function.
    print("Running privateGPT in standalone query mode. Type 'exit' to quit.")
    from argparse import ArgumentParser # Import locally for this block

    parser = ArgumentParser(description='privateGPT: Query documents via command line for testing.')
    parser.add_argument("--hide-source", "-S", action='store_true',
                            help='Use this flag to disable printing of source documents used for answers.')
    args = parser.parse_args()

    # Temporarily override HIDE_SOURCE_DOCUMENTS for CLI testing if flag is used
    if args.hide_source:
        HIDE_SOURCE_DOCUMENTS_CLI = True # Create a local override
    else:
        HIDE_SOURCE_DOCUMENTS_CLI = HIDE_SOURCE_DOCUMENTS # Use global constant

    while True:
        query = input("\nEnter a query (exit to quit): ")
        if query.lower() == "exit":
            print("Exiting privateGPT standalone query mode.")
            break

        print("Processing your query... Please wait.")
        result = get_answer_from_privateGPT(query)

        if "error" in result:
            print(f"\nError: {result['error']}")
        else:
            print("\n\n> Question:")
            print(query)
            print("\n> Answer:")
            print(result['answer'])

            if not HIDE_SOURCE_DOCUMENTS_CLI and result.get('source_documents'):
                print("\n> Sources:")
                for i, doc in enumerate(result['source_documents']):
                    source_path = doc['metadata'].get("source", "Unknown Source")
                    # Clean up path to show just the filename if it's a long path
                    source_filename = os.path.basename(source_path)
                    print(f"\n  Source {i+1} ({source_filename}):")
                    print(doc['page_content'])