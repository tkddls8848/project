from typing import List, Dict, Any
from datetime import datetime

class SummaryService:
    """Service for generating crawl summary reports."""
    
    @staticmethod
    def generate_crawling_summary(results: List[Any], stats: Dict, saved_info: Dict, extra_stats: Dict = None, start_doc: int = None, end_doc: int = None) -> Dict[str, Any]:
        """Generates a summary dictionary from crawl results."""
        # Handle both Pydantic models and legacy dicts
        total_urls = len(results)
        total_success = 0
        total_failed = 0
        success_urls = []
        failed_urls = []
        error_details = {}

        for r in results:
            # Check if it's a Pydantic model
            if hasattr(r, 'success'):
                is_success = r.success
                url = r.url
                errors = r.errors
            else:
                is_success = r.get('success')
                url = r.get('url')
                errors = r.get('errors', [])

            if is_success:
                total_success += 1
                success_urls.append(url)
            else:
                total_failed += 1
                failed_urls.append(url)
                if errors:
                    error_details[url] = errors

        summary = {
            'crawling_summary': {
                'start_document': start_doc,
                'end_document': end_doc,
                'total_urls': total_urls,
                'total_success': total_success,
                'total_failed': total_failed,
                'overall_success_rate': f"{(total_success / total_urls * 100):.1f}%" if total_urls else '0%',
                'total_time_seconds': round(stats.get('total_time', 0), 2),
                'avg_time_per_url': round(stats.get('total_time', 0) / total_urls, 2) if total_urls else 0
            },
            'save_summary': saved_info,
            'timestamp': datetime.now().isoformat(),
            'success_urls': success_urls,
            'failed_urls': failed_urls,
            'error_details': error_details
        }

        if extra_stats:
            summary.update(extra_stats)

        return summary
