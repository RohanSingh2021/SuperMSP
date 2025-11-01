
import os
import shutil
from pathlib import Path
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_chroma import Chroma
from langchain_core.prompts import PromptTemplate
from langchain.chat_models import init_chat_model
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.schema import Document
from dotenv import load_dotenv

load_dotenv()


DATA_PATH = Path(__file__).parent.parent / "data" / "generic_queries"
CHROMA_PATH = Path(__file__).parent.parent / "data" / "chroma"

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")



def generate_data_store():
    """Load documents, split them, and save to Chroma vector store."""
    documents = load_documents()
    chunks = split_text(documents)
    save_to_chroma(chunks)

def load_documents() -> list[Document]:
    """Load all .txt files from DATA_PATH."""
    docs = []
    for filename in os.listdir(DATA_PATH):
        path = os.path.join(DATA_PATH, filename)
        if filename.endswith(".txt"):
            loader = TextLoader(path, encoding='utf-8')
            docs.extend(loader.load())
    return docs

def split_text(documents: list[Document]) -> list[Document]:
    """Split documents into smaller chunks for vector store."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=50,
        length_function=len,
        add_start_index=True
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Split {len(documents)} documents into {len(chunks)} chunks")
    return chunks

def save_to_chroma(chunks: list[Document]):
    """Save chunks to Chroma vector store."""
    if os.path.exists(CHROMA_PATH):
        shutil.rmtree(CHROMA_PATH)

    db = Chroma.from_documents(chunks, embeddings, persist_directory=CHROMA_PATH)
    print(f"Saved {len(chunks)} chunks to {CHROMA_PATH}.")


def get_rag_answer(ticket_text: str, k: int = 5) -> dict:
    """
    Retrieve an answer for the ticket using RAG.
    Returns a structured dict:
      - status: "found" or "not_found"
      - answer: string or None
      - sources: list of document sources
    """
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)

    docs_with_scores = db.similarity_search_with_score(ticket_text, k=k)

    if not docs_with_scores:
        return {"status": "not_found", "answer": None, "sources": []}

    context = "\n\n".join([doc.page_content for doc, score in docs_with_scores])

    llm = init_chat_model("gemini-2.5-flash", model_provider="google_genai")

    template = """You are a helpful and knowledgeable assistant. Use ONLY the context below to answer the question. If you can't find the answer in the context, say "I don't know". 
Context: {context}

Question: {question}

Answer:"""
    prompt = PromptTemplate.from_template(template)

    qa_chain = prompt | llm

    answer = qa_chain.invoke({"context": context, "question": ticket_text})

    sources = [doc.metadata.get("source") if hasattr(doc, "metadata") else None for doc, _ in docs_with_scores]

    return {"status": "found", "answer": answer.content, "sources": sources}


def initialize_rag():
    """Call this once to create Chroma DB from documents."""
    if not os.path.exists(CHROMA_PATH):
        print("Chroma DB not found, generating data store...")
        generate_data_store()
    else:
        print("Chroma DB already exists, skipping generation.")
