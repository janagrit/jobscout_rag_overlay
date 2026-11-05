from hashlib import sha256
import chromadb
from app.config import CHROMA_PATH
from app.chunking import chunk_text


class EmptyProfileError(ValueError):
    """The profile has no indexable text (maps to HTTP 400)."""


class ProfileStore:
    def __init__(self, client=None):
        self.client = client or chromadb.PersistentClient(path=CHROMA_PATH)

    @staticmethod
    def _collection_name(tenant_id: str, profile_id: str) -> str:
        # Do not expose account identifiers in collection names.
        digest = sha256(f"{tenant_id}:{profile_id}".encode()).hexdigest()[:32]
        return f"profile_{digest}"

    def index_profile(self, tenant_id: str, profile_id: str, text: str, embed):
        chunks = chunk_text(text)
        if not chunks:
            raise EmptyProfileError("Profile contains no indexable text")
        name = self._collection_name(tenant_id, profile_id)
        try:
            self.client.delete_collection(name)
        except Exception:
            pass
        collection = self.client.create_collection(name=name, metadata={"hnsw:space": "cosine"})
        vectors = embed(chunks)
        ids = [f"chunk-{i}" for i in range(len(chunks))]
        collection.add(
            ids=ids,
            documents=chunks,
            embeddings=vectors,
            metadatas=[{"source_id": f"CV-{i+1}", "tenant_id": tenant_id} for i in range(len(chunks))],
        )
        return len(chunks)

    def retrieve(self, tenant_id: str, profile_id: str, query: str, embed, top_k: int):
        name = self._collection_name(tenant_id, profile_id)
        try:
            collection = self.client.get_collection(name)
        except Exception:
            return []
        if collection.count() == 0:
            return []
        vector = embed([query])[0]
        result = collection.query(
            query_embeddings=[vector],
            n_results=min(top_k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        return [
            {"source_id": meta["source_id"], "excerpt": doc,
             "relevance_distance": distances[i] if i < len(distances) else None}
            for i, (doc, meta) in enumerate(zip(docs, metas))
            if meta.get("tenant_id") == tenant_id
        ]
