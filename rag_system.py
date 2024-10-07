import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict, Tuple
from logger import main_logger as logger

class RAGSystem:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.documents: Dict[str, Dict] = {}
        self.embeddings: Dict[str, np.ndarray] = {}

    def create_embeddings(self, documents: Dict[str, Dict]):
        for doc_id, doc in documents.items():
            content = doc.get('content', '')
            self.documents[doc_id] = doc
            self.embeddings[doc_id] = self.model.encode(content)

    def similarity_search(self, query: str, top_k: int = 3) -> List[Tuple[str, float]]:
        query_embedding = self.model.encode(query)
        similarities = []
        for doc_id, embedding in self.embeddings.items():
            similarity = cosine_similarity([query_embedding], [embedding])[0][0]
            similarities.append((doc_id, similarity))
        return sorted(similarities, key=lambda x: x[1], reverse=True)[:top_k]

    def retrieve_relevant_chunks(self, query: str, top_k: int = 3) -> List[str]:
        top_docs = self.similarity_search(query, top_k)
        relevant_chunks = []
        for doc_id, similarity in top_docs:
            content = self.documents[doc_id]['content']
            relevancy_percentage = similarity * 100
            logger.info(f"Relevancy percentage: {relevancy_percentage}")
            if relevancy_percentage > 5:
                relevant_chunks.append(content)
            else:
                relevant_chunks.append(f"No relevant information found for this document")
        return relevant_chunks

rag_system = RAGSystem()

def initialize_rag_system(documents: Dict[str, Dict]):
    rag_system.create_embeddings(documents)

def get_relevant_chunks(query: str, top_k: int = 3) -> List[str]:
    return rag_system.retrieve_relevant_chunks(query, top_k)
