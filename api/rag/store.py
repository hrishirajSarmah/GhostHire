import chromadb

CHROMA_DB_PATH = "./chroma_db"

def get_chroma_client():
    return chromadb.PersistentClient(path=CHROMA_DB_PATH)