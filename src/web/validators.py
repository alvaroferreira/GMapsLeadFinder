"""
Pydantic validators for input validation and sanitization.

Implements OWASP recommendations for:
- Input validation (A03:2021 - Injection)
- Data integrity checks
- Type safety
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class SearchRequest(BaseModel):
    """Validated search request model."""

    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    location: Optional[str] = Field(None, max_length=100, description="Location as lat,lng")
    radius: int = Field(5000, ge=100, le=50000, description="Search radius in meters")
    place_type: Optional[str] = Field(None, max_length=50, description="Place type filter")
    max_reviews: Optional[int] = Field(None, ge=0, le=10000, description="Maximum review count filter")
    has_website: Optional[str] = Field(None, pattern="^(yes|no)?$", description="Website filter")
    max_results: int = Field(60, ge=1, le=100, description="Maximum results")
    date_from: Optional[str] = Field(None, description="Filter date from (YYYY-MM-DD)")
    date_to: Optional[str] = Field(None, description="Filter date to (YYYY-MM-DD)")
    only_new: Optional[str] = Field(None, pattern="^(yes)?$", description="Show only new businesses")

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        """Sanitize search query to prevent injection attacks."""
        if not v:
            raise ValueError("Query cannot be empty")
        # Remove potentially dangerous characters
        dangerous_chars = ["<", ">", ";", "--", "/*", "*/"]
        for char in dangerous_chars:
            if char in v:
                raise ValueError(f"Query contains invalid character: {char}")
        return v.strip()

    @field_validator("location")
    @classmethod
    def validate_location(cls, v: Optional[str]) -> Optional[str]:
        """Validate location format (lat,lng)."""
        if v:
            parts = v.split(",")
            if len(parts) != 2:
                raise ValueError("Location must be in format: lat,lng")
            try:
                lat, lng = float(parts[0].strip()), float(parts[1].strip())
                if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                    raise ValueError("Invalid latitude or longitude values")
            except ValueError:
                raise ValueError("Location must contain valid numeric coordinates")
        return v

    @field_validator("date_from", "date_to")
    @classmethod
    def validate_date(cls, v: Optional[str]) -> Optional[str]:
        """Validate date format."""
        if v:
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError("Date must be in YYYY-MM-DD format")
        return v


class LeadUpdateRequest(BaseModel):
    """Validated lead update request."""

    status: Optional[str] = Field(None, max_length=20, description="Lead status")
    notes: Optional[str] = Field(None, max_length=5000, description="Lead notes")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        """Validate status is one of allowed values."""
        if v:
            allowed_statuses = ["new", "contacted", "qualified", "converted", "rejected"]
            if v not in allowed_statuses:
                raise ValueError(f"Status must be one of: {', '.join(allowed_statuses)}")
        return v

    @field_validator("notes")
    @classmethod
    def sanitize_notes(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize notes to prevent XSS."""
        if v:
            # Remove script tags and other dangerous HTML
            dangerous_patterns = ["<script", "javascript:", "onerror=", "onload="]
            v_lower = v.lower()
            for pattern in dangerous_patterns:
                if pattern in v_lower:
                    raise ValueError("Notes contain invalid content")
        return v


class ExportRequest(BaseModel):
    """Validated export request."""

    format: str = Field(..., pattern="^(csv|xlsx|json)$", description="Export format")
    status: Optional[str] = Field(None, max_length=20, description="Filter by status")
    min_score: Optional[int] = Field(None, ge=0, le=100, description="Minimum lead score")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        """Validate status is allowed."""
        if v:
            allowed_statuses = ["new", "contacted", "qualified", "converted", "rejected"]
            if v not in allowed_statuses:
                raise ValueError(f"Status must be one of: {', '.join(allowed_statuses)}")
        return v


class APIKeyUpdate(BaseModel):
    """Validated API key update request."""

    api_key: str = Field(..., min_length=10, max_length=500, description="API key")

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate API key format and detect masked keys."""
        if not v:
            raise ValueError("API key cannot be empty")

        # Reject masked keys
        if "•" in v or "*" in v or "..." in v:
            raise ValueError("Cannot save masked API key")

        # Basic format validation - most API keys are alphanumeric with some special chars
        if not all(c.isalnum() or c in "_-." for c in v):
            raise ValueError("API key contains invalid characters")

        return v


class NotionConnectionRequest(BaseModel):
    """Validated Notion connection request."""

    api_key: str = Field(..., min_length=10, max_length=500, description="Notion API key")
    database_id: str = Field(..., min_length=10, max_length=100, description="Notion database ID")

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate Notion API key format."""
        if not v.startswith("secret_") and not v.startswith("ntn_"):
            raise ValueError("Invalid Notion API key format")
        return v

    @field_validator("database_id")
    @classmethod
    def validate_database_id(cls, v: str) -> str:
        """Validate Notion database ID format."""
        # Remove hyphens for validation
        clean_id = v.replace("-", "")
        if not clean_id.isalnum():
            raise ValueError("Invalid Notion database ID format")
        return v


class AutomationRequest(BaseModel):
    """Validated automation search request."""

    name: str = Field(..., min_length=1, max_length=100, description="Search name")
    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    location: Optional[str] = Field(None, max_length=100, description="Location")
    radius: int = Field(5000, ge=100, le=50000, description="Search radius")
    place_type: Optional[str] = Field(None, max_length=50, description="Place type")
    interval_hours: int = Field(24, ge=1, le=168, description="Interval in hours (max 1 week)")
    notify_on_new: bool = Field(True, description="Send notifications for new leads")
    notify_threshold_score: int = Field(50, ge=0, le=100, description="Minimum score for notifications")

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        """Sanitize automation name."""
        dangerous_chars = ["<", ">", ";", "--"]
        for char in dangerous_chars:
            if char in v:
                raise ValueError(f"Name contains invalid character: {char}")
        return v.strip()

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        """Sanitize search query."""
        dangerous_chars = ["<", ">", ";", "--", "/*", "*/"]
        for char in dangerous_chars:
            if char in v:
                raise ValueError(f"Query contains invalid character: {char}")
        return v.strip()


class PaginationParams(BaseModel):
    """Validated pagination parameters."""

    page: int = Field(1, ge=1, le=10000, description="Page number")
    limit: int = Field(20, ge=1, le=1000, description="Items per page")
    offset: int = Field(0, ge=0, description="Offset for querying")

    @model_validator(mode="after")
    def calculate_offset(self):
        """Calculate offset from page and limit."""
        self.offset = (self.page - 1) * self.limit
        return self
