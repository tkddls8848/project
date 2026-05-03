"""
Redis 캐싱 서비스

성능 최적화를 위한 Redis 기반 캐싱 레이어
"""

import json
import hashlib
from typing import Any, Optional, Callable
from functools import wraps
import redis
import logging

logger = logging.getLogger(__name__)


class CacheService:
    """Redis 기반 캐싱 서비스"""

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0, ttl: int = 3600):
        """
        Args:
            host: Redis 호스트
            port: Redis 포트
            db: Redis 데이터베이스 번호
            ttl: 기본 TTL (초)
        """
        try:
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # 연결 테스트
            self.redis_client.ping()
            self.enabled = True
            logger.info(f"✅ Redis 연결 성공: {host}:{port}")
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.warning(f"⚠️ Redis 연결 실패 (캐싱 비활성화): {e}")
            self.redis_client = None
            self.enabled = False

        self.default_ttl = ttl

    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """
        캐시 키 생성

        Args:
            prefix: 키 접두사 (예: "neo4j:explore")
            *args: 위치 인자
            **kwargs: 키워드 인자

        Returns:
            Redis 키 문자열
        """
        # 인자들을 JSON으로 직렬화하여 해시 생성
        key_data = {
            "args": args,
            "kwargs": kwargs
        }
        key_json = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.md5(key_json.encode()).hexdigest()[:12]

        return f"{prefix}:{key_hash}"

    def get(self, key: str) -> Optional[Any]:
        """
        캐시에서 값 조회

        Args:
            key: 캐시 키

        Returns:
            캐시된 값 (없으면 None)
        """
        if not self.enabled:
            return None

        try:
            cached = self.redis_client.get(key)
            if cached:
                logger.debug(f"🎯 캐시 HIT: {key}")
                return json.loads(cached)
            logger.debug(f"❌ 캐시 MISS: {key}")
            return None
        except Exception as e:
            logger.error(f"Redis GET 오류: {e}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        캐시에 값 저장

        Args:
            key: 캐시 키
            value: 저장할 값
            ttl: TTL (초, None이면 기본값)

        Returns:
            성공 여부
        """
        if not self.enabled:
            return False

        try:
            ttl = ttl if ttl is not None else self.default_ttl
            value_json = json.dumps(value, ensure_ascii=False)
            self.redis_client.setex(key, ttl, value_json)
            logger.debug(f"💾 캐시 저장: {key} (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Redis SET 오류: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        캐시 삭제

        Args:
            key: 캐시 키

        Returns:
            성공 여부
        """
        if not self.enabled:
            return False

        try:
            self.redis_client.delete(key)
            logger.debug(f"🗑️ 캐시 삭제: {key}")
            return True
        except Exception as e:
            logger.error(f"Redis DELETE 오류: {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """
        패턴에 맞는 모든 캐시 삭제

        Args:
            pattern: 키 패턴 (예: "neo4j:*")

        Returns:
            삭제된 키 개수
        """
        if not self.enabled:
            return 0

        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info(f"🗑️ 캐시 일괄 삭제: {pattern} ({deleted}개)")
                return deleted
            return 0
        except Exception as e:
            logger.error(f"Redis DELETE PATTERN 오류: {e}")
            return 0

    def clear_all(self) -> bool:
        """
        모든 캐시 삭제

        Returns:
            성공 여부
        """
        if not self.enabled:
            return False

        try:
            self.redis_client.flushdb()
            logger.warning("🗑️ 모든 캐시 삭제")
            return True
        except Exception as e:
            logger.error(f"Redis FLUSHDB 오류: {e}")
            return False

    def cached(
        self,
        prefix: str,
        ttl: Optional[int] = None,
        key_func: Optional[Callable] = None
    ):
        """
        함수 결과 캐싱 데코레이터

        Args:
            prefix: 캐시 키 접두사
            ttl: TTL (초)
            key_func: 커스텀 키 생성 함수 (args, kwargs를 받아 키 반환)

        Example:
            @cache.cached("explore", ttl=600)
            def explore_graph(doc_id: str, depth: int):
                ...
        """
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 캐시 비활성화 시 원본 함수 실행
                if not self.enabled:
                    return func(*args, **kwargs)

                # 캐시 키 생성
                if key_func:
                    cache_key = f"{prefix}:{key_func(*args, **kwargs)}"
                else:
                    cache_key = self._make_key(prefix, *args, **kwargs)

                # 캐시 조회
                cached_value = self.get(cache_key)
                if cached_value is not None:
                    return cached_value

                # 원본 함수 실행
                result = func(*args, **kwargs)

                # 결과 캐싱
                self.set(cache_key, result, ttl)

                return result

            return wrapper
        return decorator


# 전역 캐시 인스턴스
_cache_instance: Optional[CacheService] = None


def get_cache_service(
    host: str = "localhost",
    port: int = 6379,
    db: int = 0,
    ttl: int = 3600
) -> CacheService:
    """
    CacheService 싱글톤 인스턴스 반환

    Args:
        host: Redis 호스트
        port: Redis 포트
        db: Redis 데이터베이스 번호
        ttl: 기본 TTL (초)

    Returns:
        CacheService 인스턴스
    """
    global _cache_instance

    if _cache_instance is None:
        _cache_instance = CacheService(host=host, port=port, db=db, ttl=ttl)

    return _cache_instance
