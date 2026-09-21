from abc import ABC, abstractmethod
from typing import Dict, Any, Type
from pydantic import BaseModel

class AIProvider(ABC):
    @abstractmethod
    def extract_structured_data(
        self, 
        file_bytes: bytes, 
        mime_type: str, 
        prompt: str, 
        schema: Type[BaseModel]
    ) -> Dict[str, Any]:
        """
        Extract structured data from a document using the provided prompt and schema.
        Returns the raw parsed dictionary and handles provider-specific timeout/retries.
        """
        pass
