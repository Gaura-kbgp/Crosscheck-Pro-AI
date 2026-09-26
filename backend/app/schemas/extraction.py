from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
from app.models.core import DocumentType, ItemCategory

class ExtractionResponse(BaseModel):
    id: UUID
    document_id: UUID
    organization_id: UUID
    raw_data: Dict[str, Any]
    provider: str
    model_name: str
    prompt_version: str
    confidence: Optional[Dict[str, Any]] = None
    attempt: int = 1
    is_latest: bool = True
    extraction_version: Optional[str] = None
    document_hash: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CanonicalLineItemResponse(BaseModel):
    id: UUID
    project_id: UUID
    document_id: UUID
    source_type: DocumentType
    raw_sku: Optional[str] = None
    normalized_sku: Optional[str] = None
    description: Optional[str] = None
    item_category: Optional[ItemCategory] = None
    category_confidence: Optional[float] = None
    category_evidence: Optional[Any] = None
    cabinet_classification: Optional[Any] = None
    quantity: Optional[int] = None
    dimensions: Optional[Any] = None
    finish: Optional[str] = None
    door_style: Optional[str] = None
    modifications: Optional[Any] = None
    price: Optional[str] = None
    notes: Optional[str] = None
    source_metadata: Optional[Any] = None

    acknowledgement_status: Optional[str] = None
    substitution_sku: Optional[str] = None
    rejection_reason: Optional[str] = None
    backorder: Optional[str] = None
    changed_item: Optional[str] = None
    manufacturer_reference: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# AI Validation Schemas
class DesignExtractionItem(BaseModel):
    sku: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[int] = None
    dimensions: Optional[Dict[str, Any]] = None
    finish: Optional[str] = None
    door_style: Optional[str] = None
    color: Optional[str] = None
    modifications: Optional[List[str]] = None
    accessories: Optional[List[str]] = None
    panels: Optional[List[str]] = None
    fillers: Optional[List[str]] = None
    moldings: Optional[List[str]] = None
    position: Optional[str] = None
    drawing_reference: Optional[str] = None
    notes: Optional[str] = None
    confidence: Optional[float] = None
    page_number: Optional[int] = None
    source_text: Optional[str] = None

class DesignExtraction(BaseModel):
    items: List[DesignExtractionItem]

class OrderExtractionItem(BaseModel):
    sku: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[int] = None
    dimensions: Optional[Dict[str, Any]] = None
    finish: Optional[str] = None
    door_style: Optional[str] = None
    modifications: Optional[List[str]] = None
    accessories: Optional[List[str]] = None
    notes: Optional[str] = None
    line_number: Optional[str] = None
    source_reference: Optional[str] = None
    price: Optional[str] = None
    confidence: Optional[float] = None
    page_number: Optional[int] = None
    source_text: Optional[str] = None

class OrderExtraction(BaseModel):
    items: List[OrderExtractionItem]

class AcknowledgementExtractionItem(BaseModel):
    sku: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[int] = None
    dimensions: Optional[Dict[str, Any]] = None
    price: Optional[str] = None
    ack_status: Optional[str] = None
    substitution_sku: Optional[str] = None
    rejection_reason: Optional[str] = None
    backorder: Optional[str] = None
    changed_item: Optional[str] = None
    manufacturer_reference: Optional[str] = None
    notes: Optional[str] = None
    line_number: Optional[str] = None
    source_reference: Optional[str] = None
    confidence: Optional[float] = None
    page_number: Optional[int] = None
    source_text: Optional[str] = None

class AcknowledgementExtraction(BaseModel):
    items: List[AcknowledgementExtractionItem]

class SpecBookCodeExtractionItem(BaseModel):
    code: str
    description: Optional[str] = None
    category: Optional[str] = None
    confidence: Optional[float] = None
    page_number: Optional[int] = None
    source_text: Optional[str] = None

class SpecBookCodeExtraction(BaseModel):
    items: List[SpecBookCodeExtractionItem]
