#!/usr/bin/env python3
import tiktoken
import gradio as gr # Not used in this script, can remove if not planning to use
from dotenv import load_dotenv
from langchain import PromptTemplate # Not used in this script, can remove if not planning to use
from langchain.chains.summarize import load_summarize_chain
from langchain_community.document_loaders import PyPDFLoader # Changed to langchain_community

from langchain_huggingface.embeddings import HuggingFaceEmbeddings # Changed to langchain_huggingface
#from langchain.embeddings.openai import OpenAIEmbeddings # Not used, commented out

from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain_chroma.vectorstores import Chroma # Using langchain_chroma now
from langchain_community.vectorstores import FAISS # Changed to langchain_community
from langchain_community.llms import GPT4All, LlamaCpp # Changed to langchain_community
from langchain_community.llms import Ollama # <-- ADDED OLLAMA IMPORT
import os
import argparse


def num_tokens_from_string(string: str, encoding_name: str) -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    print(encoding.encode(string))
    num_tokens = len(encoding.encode(string))
    return num_tokens

def summarize_pdf(pdf_file_path, llm_instance, mute_stream=False): # Pass llm and mute_stream
    loader = PyPDFLoader(pdf_file_path)
    docs = loader.load_and_split()
    
    # Define callbacks locally for the chain
    callbacks = [] if mute_stream else [StreamingStdOutCallbackHandler()]
    
    chain = load_summarize_chain(llm=llm_instance, chain_type="map_reduce", verbose=True, callbacks=callbacks) # Pass llm_instance and callbacks
    summary = chain.run(docs)
    return summary


def main():
    load_dotenv() # Load environment variables here, once per run

    embeddings_model_name = os.environ.get("EMBEDDINGS_MODEL_NAME")
    # persist_directory = os.environ.get('PERSIST_DIRECTORY') # Not used for summarization, can remove

    model_type = os.environ.get('MODEL_TYPE')
    model_path = os.environ.get('MODEL_PATH') # Only relevant for LlamaCpp/GPT4All
    model_n_ctx = int(os.environ.get('MODEL_N_CTX', 2048)) # Default to 2048 if not set

    # target_source_chunks = int(os.environ.get('TARGET_SOURCE_CHUNKS',4)) # Not used for summarization, can remove

    args = parse_arguments() # Parse arguments here

    llm = None # Initialize llm to None

    # Prepare the LLM based on MODEL_TYPE
    match model_type:
        case "LlamaCpp":
            llm = LlamaCpp(model_path=model_path, n_ctx=model_n_ctx, callbacks=[StreamingStdOutCallbackHandler()], verbose=False) # Callbacks defined here
        case "GPT4All":
            llm = GPT4All(model=model_path, n_ctx=model_n_ctx, backend='gptj', callbacks=[StreamingStdOutCallbackHandler()], verbose=False) # Callbacks defined here
        case "Ollama": # <-- ADDED OLLAMA CASE
            llm = Ollama(
                model="llama3",
                callbacks=[StreamingStdOutCallbackHandler()], # Callbacks defined here
                verbose=False,
                temperature=0.7,
                num_ctx=4096, # Ollama uses 'num_ctx'
            )
        case _default:
            print(f"Model {model_type} not supported!")
            exit() # Corrected: Use exit() as a function call

    if llm is None:
        print("Failed to initialize LLM. Exiting.")
        exit()

    # --- Summarization Part ---
    # This assumes '2023_GPT4All_Technical_Report.pdf' is in 'source_documents/'
    pdf_to_summarize_path = 'source_documents/2023_GPT4All_Technical_Report.pdf'
    
    print(f"\n--- Summarizing: {pdf_to_summarize_path} ---")
    # Pass the llm instance and mute_stream arg to the summarize_pdf function
    summary = summarize_pdf(pdf_to_summarize_path, llm, args.mute_stream) 
    print("\n--- Summary ---")
    print(summary)
    print("\n--- End of Summary ---")

    # --- FAISS Part (if you still want to run it, 'pages' needs to be defined) ---
    # To run this, you'd need to load the PDF documents into 'pages' first
    # For example:
    # loader = PyPDFLoader(pdf_to_summarize_path)
    # pages = loader.load_and_split()
    # faiss_index = FAISS.from_documents(pages, HuggingFaceEmbeddings(model_name=embeddings_model_name))
    # print("\n--- FAISS Similarity Search ---")
    # docs = faiss_index.similarity_search("What makes a useful API?", k=2)
    # for doc in docs:
    #     print(str(doc.metadata["page"]) + ":", doc.page_content[:1000])
    # print("\n--- End of FAISS Similarity Search ---")


def parse_arguments():
    parser = argparse.ArgumentParser(description='summarize.py: Summarize PDF documents using LLMs.')
    parser.add_argument("--mute-stream", "-M",
                        action='store_true',
                        help='Use this flag to disable the streaming StdOut callback for LLMs.')
    return parser.parse_args()


if __name__ == "__main__":
    main()