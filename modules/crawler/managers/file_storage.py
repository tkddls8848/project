import os
import json
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple, Any

from crawl_types import storage_subdirectory

class DataExporter:
    """Handles saving crawling results to the file system."""

    @staticmethod
    def save_crawling_result(data: Dict[str, Any], output_dir: str, api_id: str, formats: List[str] = None) -> Tuple[List[str], List[str]]:
        """
        Saves the crawled data in specified formats.

        Args:
            data: The dictionary containing crawled data.
            output_dir: The root directory for output.
            api_id: The unique identifier for the API.
            formats: List of formats ('json'). Defaults to ['json'].

        Returns:
            Tuple containing list of saved file paths and list of error messages.
        """
        if formats is None:
            formats = ['json']
            
        saved_files = []
        errors = []

        # Determine subdirectory based on API type
        api_type = data.get('api_type', 'unknown')
        data_dir = output_dir if output_dir else './data'

        # For openapi types, save in api_type subdirectory.
        # openapi_old is the historical bucket for non-LINK documents without a
        # parseable inline swaggerJson. Their API rules are rendered as HTML.
        result_subdirectory = storage_subdirectory(api_type)
        if result_subdirectory:
            base_dir = os.path.join(data_dir, result_subdirectory)
        else:
            # Save directly under data type folder for other types
            base_dir = data_dir

        doc_num = api_id if api_id and api_id != 'unknown' else 'unknown_doc'
        # 재크롤링 시 같은 파일을 덮어쓴다 — 전 타입 공통, 최신 1파일만 유지
        file_prefix = doc_num
        
        try:
            os.makedirs(base_dir, exist_ok=True)
        except OSError as e:
            errors.append(f"Failed to create directory {base_dir}: {e}")
            return saved_files, errors

        for format_type in formats:
            try:
                if format_type == 'json':
                    file_path = os.path.join(base_dir, f"{file_prefix}.json")
                    success, error = DataExporter._save_as_json(data, file_path)
                    if success:
                        saved_files.append(file_path)
                    else:
                        errors.append(error)
            except Exception as e:
                errors.append(f"Unexpected error saving {format_type.upper()}: {str(e)}")

        return saved_files, errors

    @staticmethod
    def _save_as_json(data: Dict, file_path: str) -> Tuple[bool, str]:
        target = Path(file_path)
        temporary: Path | None = None
        try:
            fd, temporary_name = tempfile.mkstemp(
                prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
            )
            os.close(fd)
            temporary = Path(temporary_name)
            with temporary.open('w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, target)
            return True, ""
        except Exception as e:
            return False, f"JSON Save Error: {str(e)}"
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
