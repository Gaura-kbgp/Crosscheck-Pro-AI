import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum, JSON, Integer, Boolean, Float, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base
import enum
from sqlalchemy.types import Uuid

class Role(str, enum.Enum):
    ADMIN = "ADMIN"
    REVIEWER = "REVIEWER"
    VIEWER = "VIEWER"

class ProjectStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PROCESSING = "PROCESSING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    COMPLETED = "COMPLETED"
    FINALIZED = "FINALIZED"
    FAILED = "FAILED"

class DocumentType(str, enum.Enum):
    DESIGN = "DESIGN"
    ORDER = "ORDER"
    ACKNOWLEDGEMENT = "ACKNOWLEDGEMENT"

class ItemCategory(str, enum.Enum):
    CABINET = "CABINET"
    ACCESSORY = "ACCESSORY"
    FILLER = "FILLER"
    PANEL = "PANEL"
    MOLDING = "MOLDING"
    APPLIANCE = "APPLIANCE"
    ARCHITECTURAL_ANNOTATION = "ARCHITECTURAL_ANNOTATION"
    COMMERCIAL_CHARGE = "COMMERCIAL_CHARGE"
    UNKNOWN = "UNKNOWN"

class DocumentStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    settings = Column(JSON, default=dict)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="organization", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="organization", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="organization", cascade="all, delete-orphan")

class User(Base):
    __tablename__ = "users"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    auth_id = Column(String, unique=True, nullable=False, index=True)
    organization_id = Column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    email = Column(String, nullable=False, index=True)
    full_name = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)
    role = Column(SQLEnum(Role), nullable=False, default=Role.VIEWER)
    is_verified = Column(Boolean, nullable=False, default=False)
    verification_token = Column(String, nullable=True, index=True)
    verification_token_expires_at = Column(DateTime(timezone=True), nullable=True)
    reset_token = Column(String, nullable=True, index=True)
    reset_token_expires_at = Column(DateTime(timezone=True), nullable=True)
    google_id = Column(String, nullable=True, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization", back_populates="users")

class Manufacturer(Base):
    """
    Cabinet Code Intelligence: identifies which manufacturer a project's
    Design/Order/Acknowledgement documents belong to, so manufacturer-specific
    SKU dictionaries/aliases can be looked up. Global by default (organization_id
    NULL) since manufacturer identities like "Yorktowne" are shared industry
    knowledge, not tenant-private data; organization_id is set only for a
    tenant's own custom/private manufacturer entry.
    """
    __tablename__ = "manufacturers"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String, nullable=False)
    # Explicit flag (kept consistent with organization_id IS NULL by the
    # service layer, never settable via the tenant-facing API — see
    # ManufacturerService: only pre-seeded/system data is ever global).
    is_global = Column(Boolean, nullable=False, default=False)

    created_by = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization")
    code_dictionary_entries = relationship("ManufacturerCodeDictionary", back_populates="manufacturer", cascade="all, delete-orphan")


class ManufacturerCodeDictionary(Base):
    """
    Cabinet Code Intelligence: a manufacturer's known SKU/code catalog, entered
    (or later imported from a spec book) per manufacturer. A code and its
    documented aliases (e.g. BPFHC12 / BFHC12) share `alias_group`; the
    canonical/primary spelling has `is_primary_alias=True`. `source_document_id`
    points at a `ManufacturerSpecBook.id` when a row was approved from a spec
    book extraction (see below) rather than entered by hand; `source_version`/
    `effective_from`/`effective_to` support historical/versioned catalogs.
    """
    __tablename__ = "manufacturer_code_dictionary"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    manufacturer_id = Column(Uuid(as_uuid=True), ForeignKey("manufacturers.id", ondelete="CASCADE"), nullable=False, index=True)

    code = Column(String, nullable=False)
    normalized_code = Column(String, nullable=False, index=True)
    category = Column(SQLEnum(ItemCategory), nullable=False)
    description = Column(String, nullable=True)

    alias_group = Column(String, nullable=True, index=True)
    is_primary_alias = Column(Boolean, nullable=False, default=True)

    is_current = Column(Boolean, nullable=False, default=True)
    effective_from = Column(DateTime(timezone=True), nullable=True)
    effective_to = Column(DateTime(timezone=True), nullable=True)

    source_document_id = Column(Uuid(as_uuid=True), nullable=True)
    source_version = Column(String, nullable=True)

    created_by = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    manufacturer = relationship("Manufacturer", back_populates="code_dictionary_entries")

    __table_args__ = (
        UniqueConstraint("manufacturer_id", "normalized_code", name="uq_manufacturer_code_normalized"),
    )


class SpecBookStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    EXTRACTING = "EXTRACTING"
    EXTRACTED = "EXTRACTED"
    FAILED = "FAILED"


class SpecBookRowStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ManufacturerSpecBook(Base):
    """
    Settings → Manufacturer → Upload Specification Book PDF → Extract codes →
    Review → Approve → Manufacturer Dictionary.

    An uploaded catalog document. Extraction runs as a background job (mirrors
    the existing Design/Order/Ack processing pipeline in
    app/worker/tasks/processing.py) and writes candidate rows to
    ManufacturerSpecBookRow — never directly into ManufacturerCodeDictionary.
    Only human-approved rows ever become real dictionary entries.
    """
    __tablename__ = "manufacturer_spec_books"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    manufacturer_id = Column(Uuid(as_uuid=True), ForeignKey("manufacturers.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    original_filename = Column(String, nullable=False)
    storage_path = Column(String, nullable=False, unique=True)
    mime_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)

    status = Column(SQLEnum(SpecBookStatus), nullable=False, default=SpecBookStatus.UPLOADED)
    source_version = Column(String, nullable=True)
    error = Column(JSON, nullable=True)

    uploaded_by = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    manufacturer = relationship("Manufacturer")
    rows = relationship("ManufacturerSpecBookRow", back_populates="spec_book", cascade="all, delete-orphan")


class ManufacturerSpecBookRow(Base):
    """
    One AI-extracted candidate code from a spec book, pending human review.
    Raw AI output is preserved as-is (raw_code/description/category/confidence)
    even after a reviewer edits it — the edit updates this row directly (there
    is only one row per candidate; the pre-edit AI guess is not separately
    retained beyond this row's own history), but it is NEVER written into
    ManufacturerCodeDictionary until explicitly approved.
    """
    __tablename__ = "manufacturer_spec_book_rows"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    spec_book_id = Column(Uuid(as_uuid=True), ForeignKey("manufacturer_spec_books.id", ondelete="CASCADE"), nullable=False, index=True)
    manufacturer_id = Column(Uuid(as_uuid=True), ForeignKey("manufacturers.id", ondelete="CASCADE"), nullable=False, index=True)

    raw_code = Column(String, nullable=False)
    normalized_code = Column(String, nullable=False, index=True)
    description = Column(String, nullable=True)
    category = Column(SQLEnum(ItemCategory), nullable=False, default=ItemCategory.UNKNOWN)
    confidence = Column(Float, nullable=True)

    page_number = Column(Integer, nullable=True)
    source_text = Column(String, nullable=True)

    status = Column(SQLEnum(SpecBookRowStatus), nullable=False, default=SpecBookRowStatus.PENDING)
    reviewed_by = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    spec_book = relationship("ManufacturerSpecBook", back_populates="rows")


class NKBAReferenceDocument(Base):
    """
    A stored reference copy of an NKBA (National Kitchen & Bath Association)
    guideline document — generic industry nomenclature knowledge, never a
    manufacturer's own SKU catalog. Storage/reference only: nothing is
    extracted from it and it does not feed Cabinet Code Intelligence's
    classification logic (which stays exactly as implemented in Phase A).
    Global like a manufacturer's global entries: visible to every
    organization, editable/deletable only by the organization that uploaded
    it (organization_id NULL = a system-seeded document, never deletable by
    any tenant).
    """
    __tablename__ = "nkba_reference_documents"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)

    label = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    storage_path = Column(String, nullable=False, unique=True)
    mime_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)

    uploaded_by = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Project(Base):
    __tablename__ = "projects"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    manufacturer_id = Column(Uuid(as_uuid=True), ForeignKey("manufacturers.id", ondelete="SET NULL"), nullable=True, index=True)

    name = Column(String, nullable=False)
    customer_name = Column(String, nullable=True)
    dealer_name = Column(String, nullable=True)
    status = Column(SQLEnum(ProjectStatus), nullable=False, default=ProjectStatus.DRAFT)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization", back_populates="projects")
    manufacturer = relationship("Manufacturer")
    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="project", cascade="all, delete-orphan")

class Document(Base):
    __tablename__ = "documents"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    
    document_type = Column(SQLEnum(DocumentType), nullable=False)
    original_filename = Column(String, nullable=False)
    storage_path = Column(String, nullable=False, unique=True)
    mime_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    status = Column(SQLEnum(DocumentStatus), nullable=False, default=DocumentStatus.UPLOADED)
    # F8.3 Phase 3: SHA-256 of the raw file bytes, computed at upload time — the stable
    # identity used for extraction idempotency (never filename/timestamp/DB id).
    document_hash = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="documents")
    organization = relationship("Organization", back_populates="documents")
    extractions = relationship("Extraction", back_populates="document", cascade="all, delete-orphan")

class ProcessingJobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    VALIDATING = "VALIDATING"
    EXTRACTING = "EXTRACTING"
    NORMALIZING = "NORMALIZING"
    MATCHING = "MATCHING"
    COMPARING = "COMPARING"
    GENERATING_DISCREPANCIES = "GENERATING_DISCREPANCIES"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True) # One active job per project usually, or one job history. Unique constraint can be debated, but typically project -> job is 1:N but we check active ones. Let's not make it unique so we keep history. Wait, user said "Check whether an active job already exists". We can query for it. So no unique=True.
    organization_id = Column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    
    status = Column(SQLEnum(ProcessingJobStatus), nullable=False, default=ProcessingJobStatus.QUEUED)
    error = Column(JSON, nullable=True)
    correlation_id = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    organization = relationship("Organization")

# We remove unique=True from project_id because multiple jobs can be run sequentially.
ProcessingJob.__table__.columns['project_id'].unique = False

class Extraction(Base):
    """
    F8.3 Phase 3: one row per extraction ATTEMPT (no longer 1:1 with Document —
    reprocessing creates a new row rather than deleting the old one, so
    extraction history is never destroyed). `is_latest` marks the row every
    downstream stage should read; `document_hash` + `extraction_version` +
    provider/model/prompt_version together form the identity used to decide
    whether a prior attempt can be safely reused (idempotency).
    """
    __tablename__ = "extractions"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)

    raw_data = Column(JSON, nullable=False)
    provider = Column(String, nullable=False)
    model_name = Column(String, nullable=False)
    prompt_version = Column(String, nullable=False)
    confidence = Column(JSON, nullable=True)
    attempt = Column(Integer, nullable=False, default=1)
    is_latest = Column(Boolean, nullable=False, default=True)
    extraction_version = Column(String, nullable=True)
    document_hash = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    document = relationship("Document", back_populates="extractions")
    organization = relationship("Organization")

class CanonicalLineItem(Base):
    __tablename__ = "canonical_line_items"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    
    source_type = Column(SQLEnum(DocumentType), nullable=False)
    
    raw_sku = Column(String, nullable=True)
    normalized_sku = Column(String, nullable=True, index=True)
    description = Column(String, nullable=True)
    
    item_category = Column(SQLEnum(ItemCategory), nullable=False, default=ItemCategory.CABINET)
    category_confidence = Column(Float, nullable=True, default=1.0)
    category_evidence = Column(JSON, nullable=True)
    # Cabinet Code Intelligence: the full CabinetCodeDecision (manufacturer
    # verification tier, confidence level, reason codes, candidate variants),
    # additive alongside item_category/category_confidence above — those two
    # columns are never changed by this feature (backward compatibility with
    # every existing classification behavior/test when no manufacturer is set).
    cabinet_classification = Column(JSON, nullable=True)

    quantity = Column(Integer, nullable=True)
    
    dimensions = Column(JSON, nullable=True)
    finish = Column(String, nullable=True)
    door_style = Column(String, nullable=True)
    modifications = Column(JSON, nullable=True)
    price = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    source_metadata = Column(JSON, nullable=True)
    
    # Context-specific fields based on source
    acknowledgement_status = Column(String, nullable=True)
    substitution_sku = Column(String, nullable=True)
    rejection_reason = Column(String, nullable=True)
    backorder = Column(String, nullable=True)
    changed_item = Column(String, nullable=True)
    manufacturer_reference = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    organization = relationship("Organization")
    document = relationship("Document")

class MatchGroupStatus(str, enum.Enum):
    MATCHED = "MATCHED"
    MISSING = "MISSING"
    EXTRA = "EXTRA"
    CHANGED = "CHANGED"
    UNCERTAIN = "UNCERTAIN"

class Severity(str, enum.Enum):
    CRITICAL = "Critical"
    WARNING = "Warning"
    INFO = "Info"

class MatchGroup(Base):
    __tablename__ = "match_groups"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    
    design_item_id = Column(Uuid(as_uuid=True), ForeignKey("canonical_line_items.id", ondelete="SET NULL"), nullable=True)
    order_item_id = Column(Uuid(as_uuid=True), ForeignKey("canonical_line_items.id", ondelete="SET NULL"), nullable=True)
    ack_item_id = Column(Uuid(as_uuid=True), ForeignKey("canonical_line_items.id", ondelete="SET NULL"), nullable=True)

    status = Column(SQLEnum(MatchGroupStatus), nullable=False)

    # Final resolved state fields
    final_sku = Column(String, nullable=True)
    final_quantity = Column(Integer, nullable=True)
    final_dimensions = Column(JSON, nullable=True)
    final_finish = Column(String, nullable=True)
    final_door_style = Column(String, nullable=True)
    final_modifications = Column(JSON, nullable=True)
    final_price = Column(String, nullable=True)
    final_status = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    organization = relationship("Organization")
    design_item = relationship("CanonicalLineItem", foreign_keys=[design_item_id])
    order_item = relationship("CanonicalLineItem", foreign_keys=[order_item_id])
    ack_item = relationship("CanonicalLineItem", foreign_keys=[ack_item_id])
    discrepancies = relationship("Discrepancy", back_populates="match_group", cascade="all, delete-orphan")

class Discrepancy(Base):
    __tablename__ = "discrepancies"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    match_group_id = Column(Uuid(as_uuid=True), ForeignKey("match_groups.id", ondelete="CASCADE"), nullable=False)

    field = Column(String, nullable=False)
    source_values = Column(JSON, nullable=False)
    comparison_values = Column(JSON, nullable=False)
    introduced_at = Column(SQLEnum(DocumentType), nullable=True)
    
    status = Column(String, nullable=False, default="OPEN")
    severity = Column(SQLEnum(Severity), nullable=False)
    confidence = Column(String, nullable=True)
    explanation = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    organization = relationship("Organization")
    match_group = relationship("MatchGroup", back_populates="discrepancies")

class ReviewAction(str, enum.Enum):
    ACCEPT_FINDING = "ACCEPT_FINDING"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    OVERRIDE_DATA = "OVERRIDE_DATA"
    ACKNOWLEDGE_MFR_CHANGE = "ACKNOWLEDGE_MFR_CHANGE"
    ESCALATE = "ESCALATE"

class HumanReview(Base):
    __tablename__ = "human_reviews"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    discrepancy_id = Column(Uuid(as_uuid=True), ForeignKey("discrepancies.id", ondelete="CASCADE"), nullable=True)
    match_group_id = Column(Uuid(as_uuid=True), ForeignKey("match_groups.id", ondelete="CASCADE"), nullable=True)
    reviewer_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    action = Column(SQLEnum(ReviewAction), nullable=False)
    reason = Column(String, nullable=True)
    previous_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    organization = relationship("Organization")
    project = relationship("Project")
    reviewer = relationship("User")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    actor_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    action = Column(String, nullable=False)
    resource_type = Column(String, nullable=False)
    resource_id = Column(String, nullable=False)
    
    previous_state = Column(JSON, nullable=True)
    new_state = Column(JSON, nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True) # use metadata_ to avoid conflict with SQLAlchemy metadata
    
    correlation_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    organization = relationship("Organization")
    project = relationship("Project")
    actor = relationship("User")

class ReportFormat(str, enum.Enum):
    PDF = "PDF"
    CSV = "CSV"

class ReportStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Report(Base):
    __tablename__ = "reports"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    
    format = Column(SQLEnum(ReportFormat), nullable=False)
    status = Column(SQLEnum(ReportStatus), nullable=False, default=ReportStatus.QUEUED)
    storage_path = Column(String, nullable=True)
    error = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    project = relationship("Project", back_populates="reports")
    organization = relationship("Organization", back_populates="reports")
