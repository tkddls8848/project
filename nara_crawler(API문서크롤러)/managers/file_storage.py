import os
import json
import re
from typing import Dict, List, Tuple, Any

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

        table_info = data.get('info', {})
        org_name = table_info.get('제공기관', 'unknown_org')
        modified_date = table_info.get('수정일', 'unknown_date')
        
        # Determine subdirectory based on API type
        api_type = data.get('api_type', 'unknown')
        api_category = table_info.get('API 유형', '')
        is_openapi_link_type = 'LINK' in api_category.upper() if api_category else False

        # Sanitize organization name
        org_name = re.sub(r'[^\w\s-]', '', org_name)
        org_name = re.sub(r'[\s]+', '_', org_name).strip()

        data_dir = output_dir if output_dir else './data'

        # For openapi types, save in api_type subdirectory
        if api_type in ['openapi_link', 'openapi_new']:
            base_dir = os.path.join(data_dir, api_type)
        else:
            # Save directly under data type folder for other types
            base_dir = data_dir

        doc_num = api_id if api_id and api_id != 'unknown' else 'unknown_doc'
        file_prefix = f"{doc_num}_{modified_date}"
        
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
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True, ""
        except Exception as e:
            return False, f"JSON Save Error: {str(e)}"
