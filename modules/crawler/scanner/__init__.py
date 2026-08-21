# -*- coding: utf-8 -*-
"""
==============================================================================
메타데이터 스캐너 모듈 (Metadata Scanner Module)
==============================================================================

목적 (Purpose):
    공공데이터 포털의 메타데이터 JSON API를 스캔하여 데이터셋 존재 여부를 확인하고,
    메타정보를 수집합니다. 대량의 번호 범위를 빠르게 스캔하여 유효한 데이터셋을
    식별합니다.

주요 구성요소 (Main Components):
    1. base_scanner.py - 메타데이터 스캐너 베이스 클래스
       - 공통 스캔 로직 및 대기실 처리
       - 병렬 처리 및 재시도 로직

    2. metadata_openapi.py - OpenAPI 메타데이터 스캐너
       - /catalog/{num}/openapi.json API 스캔

    3. metadata_fileData.py - fileData 메타데이터 스캐너
       - /catalog/{num}/fileData.json API 스캔

    4. metadata_standard.py - standard 메타데이터 스캐너
       - /catalog/{num}/standard.json API 스캔

스캔 프로세스 (Scan Process):
    1. 번호 범위 지정 (예: 15000000 ~ 15001000)
    2. 병렬로 메타데이터 JSON API 요청
    3. 데이터 존재 여부 확인
    4. 대기실 감지 및 복구 대기
    5. 결과 저장 (JSON 파일)

주요 기능 (Main Features):
    - 대량 번호 범위 스캔
    - 병렬 처리 (멀티스레딩)
    - 대기실 자동 감지 및 복구 대기
    - 재시도 로직 (타임아웃 처리)
    - 타입별 통계 및 결과 저장

사용 시나리오 (Use Cases):
    - 전체 데이터셋 목록 수집
    - 유효한 데이터셋 번호 식별
    - 타입별 데이터 분포 분석

의존성 (Dependencies):
    - requests: HTTP 요청
    - concurrent.futures: 병렬 처리
    - tqdm: 진행률 표시

LLM 에이전트 가이드:
    - OpenAPI 스캔: OpenAPIMetadataScanner 사용
    - fileData 스캔: fileDataMetadataScanner 사용
    - standard 스캔: standardMetadataScanner 사용
    - 대기실 처리: BaseMetadataScanner에서 자동 처리
==============================================================================
"""
