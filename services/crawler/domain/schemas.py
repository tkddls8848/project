from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field

class CrawlerConfig(BaseModel):
    """Configuration for the crawler service."""
    start_num: int
    end_num: int
    output_dir: str
    formats: List[str] = Field(default_factory=lambda: ['json'])
    max_workers: int = 30
    full_scan: bool = False
    csv_path: Optional[str] = None
    csv_dir: str = './crawler/scanner/database'
    target_api_type: Optional[str] = None
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

class CrawlData(BaseModel):
    """Standardized data structure for crawled content."""
    api_id: str
    api_type: str = "unknown"
    crawled_url: str
    crawled_time: str = Field(default_factory=lambda: datetime.now().isoformat())
    info: Dict[str, Any] = Field(default_factory=dict) # Metadata from table
    operation_ids: Optional[List[str]] = None # UDDI operation IDs
    download_urls: Optional[Dict[str, str]] = None # File download URLs (for fileData)

    # Specific fields (optional as they depend on type)
    endpoints: Optional[List[Dict[str, Any]]] = None # For Swagger
    swagger_json: Optional[Dict[str, Any]] = None    # For Swagger
    standard_grid_table: Optional[List[Dict[str, Any]]] = None # For Standard Data

class CrawlResult(BaseModel):
    """Result of a single crawling operation."""
    url: str
    success: bool
    data: Optional[CrawlData] = None
    errors: List[str] = Field(default_factory=list)
    crawled_at: str = Field(default_factory=lambda: datetime.now().isoformat())
