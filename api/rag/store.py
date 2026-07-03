import chromadb
from settings import settings

def get_chroma_client():
    return chromadb.PersistentClient(path=settings.chroma_db_path)