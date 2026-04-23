import logging
from typing import List, Union
import numpy as np
from sentence_transformers import SentenceTransformer
from src.config import settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    Service for generating vector embeddings for legal text.
    Uses SentenceTransformer with the configured model.
    """
    _instance = None

    def __init__(self, model_name: str = settings.EMBEDDING_MODEL):
        logger.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.dimension = settings.EMBEDDING_DIM
        logger.info(f"Model loaded. Dimension: {self.dimension}")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def encode(self, text: Union[str, List[str]], convert_to_list: bool = True) -> Union[List[float], List[List[float]], np.ndarray]:
        """Encode text into embeddings."""
        embeddings = self.model.encode(
            text, 
            normalize_embeddings=True, 
            show_progress_bar=False
        )
        if convert_to_list:
            if isinstance(text, str):
                return embeddings.tolist()
            return embeddings.tolist()
        return embeddings

    def encode_query(self, query: str) -> List[float]:
        """Encode a single search query."""
        return self.encode(query, convert_to_list=True)
