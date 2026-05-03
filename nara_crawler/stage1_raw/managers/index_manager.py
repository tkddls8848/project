import os
import json
from typing import List, Dict, Any, Optional

class IndexManager:
    """
    Manages the index.json file which aggregates metadata for all crawled datasets.
    Stores data hierarchically: { api_type: { doc_key: { ...metadata... } } }
    """

    # Mapping from Korean Keys (in raw CSV info) to English Keys (in index.json)
    FIELD_MAPPING = {
        '목록키': 'doc_key',
        'api_type': 'type',
        '목록명': 'title',
        '제공기관': 'org',
        '제공기관코드': 'org_code',
        '키워드': 'keyword',
        '설명': 'description',
        '목록 URL': 'URL',
        '국가중점여부': 'national_primary',
        '수정일': 'update_time'
    }

    @classmethod
    def save(cls, results: List[Any], output_path: str = './data/index.json') -> Dict[str, Any]:
        """
        Extracts key metadata from crawl results and updates index.json.
        """
        # Load existing
        existing_data = {}
        if os.path.exists(output_path):
            try:
                with open(output_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    if not isinstance(existing_data, dict): existing_data = {}
            except Exception as e:
                print(f"Warning: Failed to read existing index.json: {e}")
                existing_data = {}

        new_count = 0
        updated_count = 0

        for result in results:
            # Handle both Pydantic models (CrawlResult) and legacy Dicts
            if hasattr(result, 'success'):
                success = result.success
                data = result.data.model_dump() if result.data else None
            else:
                success = result.get('success')
                data = result.get('data')

            if success and data:
                info = data.get('info', {})
                api_type = data.get('api_type', 'unknown')

                extracted_info = {}
                for korean_key, english_key in cls.FIELD_MAPPING.items():
                    extracted_info[english_key] = info.get(korean_key, '-')

                api_id = extracted_info.get('doc_key', 'unknown')
                
                # doc_key is used as key, so remove from value
                value_data = {k: v for k, v in extracted_info.items() if k != 'doc_key'}

                if api_type not in existing_data:
                    existing_data[api_type] = {}

                if api_id in existing_data[api_type]:
                    existing_data[api_type][api_id] = value_data
                    updated_count += 1
                else:
                    existing_data[api_type][api_id] = value_data
                    new_count += 1

        # Save
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
            
            total_items = sum(len(v) for v in existing_data.values() if isinstance(v, dict))
            return {
                'total': total_items,
                'new': new_count,
                'updated': updated_count,
                'success': True
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def load(cls, input_path: str = './data/index.json') -> Dict:
        if not os.path.exists(input_path): return {}
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {}
