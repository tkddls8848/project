from typing import Dict, List, Any, Optional

class NaraParser:
    """Parser for OpenAPI/Swagger JSON specifications."""

    def __init__(self, driver=None):
        self.driver = driver

    def extract_base_url(self, swagger_json: Dict[str, Any]) -> str:
        """Extracts the base URL from the Swagger definition."""
        if not swagger_json:
            return ""

        schemes = swagger_json.get('schemes', ['https'])
        host = swagger_json.get('host', '')
        base_path = swagger_json.get('basePath', '')

        if host:
            scheme = schemes[0] if schemes else 'https'
            return f"{scheme}://{host}{base_path}"
        return ""

    def extract_endpoints(self, swagger_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extracts endpoint details from the Swagger definition."""
        endpoints = []
        if not swagger_json:
            return endpoints

        paths = swagger_json.get('paths', {})
        for path, methods in paths.items():
            for method, data in methods.items():
                if method.lower() in ['get', 'post', 'put', 'delete', 'patch']:
                    endpoint = {
                        'method': method.upper(),
                        'path': path,
                        'description': data.get('summary', '') or data.get('description', ''),
                        'parameters': self._extract_swagger_parameters(data.get('parameters', [])),
                        'responses': self._extract_swagger_responses(data.get('responses', {})),
                        'tags': data.get('tags', []),
                        'section': data.get('tags', ['Default'])[0] if data.get('tags') else 'Default'
                    }
                    endpoints.append(endpoint)

        return endpoints

    def _extract_swagger_parameters(self, params_list: List[Dict]) -> List[Dict[str, Any]]:
        """Extracts parameter details."""
        return [{
            'name': param.get('name', ''),
            'description': param.get('description', ''),
            'required': param.get('required', False),
            'type': param.get('type', '') or (param.get('schema', {}).get('type', '') if 'schema' in param else '')
        } for param in params_list]

    def _extract_swagger_responses(self, responses_dict: Dict) -> List[Dict[str, Any]]:
        """Extracts response details."""
        return [{
            'status_code': status_code,
            'description': data.get('description', '')
        } for status_code, data in responses_dict.items()]
