"""
Purpose: Base class for scanning metadata JSON APIs in bulk.
Guide: Use subclasses like OpenAPIMetadataScanner. Automatically handles waiting rooms and retries.

스키마 주의 (2026-08 data.go.kr 리뉴얼):
    /catalog/{num}/{type}.json 은 여전히 200을 주지만 본문이 schema.org Dataset
    스키마로 바뀌었다. title/organization/apiType/updateDate 키가 사라지고
    name/creator.name/dateModified 등으로 대체됐다. 응답 Content-Type은
    text/html 이지만 본문은 JSON 이다(requests의 .json()은 정상 동작).
    옛 스키마 키는 폴백으로 남겨 리뉴얼 전 저장분도 계속 파싱된다.
"""

import requests
import json
import concurrent.futures
from datetime import datetime
from tqdm import tqdm
import time
import threading

# 데이터셋이 없을 때 포털이 돌려주는 고정 문구 (리뉴얼 전후 동일)
NOT_FOUND_DESCRIPTION = '해당 데이터는 존재하지 않습니다.'


def pick_text(source, *keys):
    """주어진 키를 순서대로 훑어 처음 만나는 비어있지 않은 문자열 값을 돌려준다."""
    if not isinstance(source, dict):
        return ''

    for key in keys:
        value = source.get(key)
        if value is None:
            continue
        if not isinstance(value, str):
            value = str(value)
        value = value.strip()
        if value:
            return value

    return ''


def extract_organization(data):
    """제공기관명 추출 - 신규 creator/publisher 객체 우선, 옛 organization 폴백"""
    for key in ('creator', 'publisher'):
        node = data.get(key)
        if isinstance(node, dict):
            name = pick_text(node, 'name')
            if name:
                return name
        elif isinstance(node, str) and node.strip():
            return node.strip()

    return pick_text(data, 'organization')


def extract_contact(data):
    """담당 부서/전화번호 추출 - creator.contactPoint (리뉴얼 스키마)"""
    creator = data.get('creator')
    contact = creator.get('contactPoint') if isinstance(creator, dict) else None
    if not isinstance(contact, dict):
        contact = {}

    return {
        'department': pick_text(contact, 'contactType') or pick_text(data, 'department'),
        'tel_no': pick_text(contact, 'telephone') or pick_text(data, 'telNo', 'telephone'),
    }


def extract_common_info(data):
    """타입 공통 메타데이터 추출 (신규 schema.org 키 우선, 옛 키 폴백)"""
    common = {
        'title': pick_text(data, 'name', 'title'),
        'organization': extract_organization(data),
        'description': pick_text(data, 'description'),
        'url': pick_text(data, 'url'),
        'update_date': pick_text(data, 'dateModified', 'datePublished', 'updateDate', 'modified'),
        'create_date': pick_text(data, 'dateCreated', 'datePublished', 'createDate'),
        'license': pick_text(data, 'license'),
        'classification': pick_text(data, 'additionalType', 'classification'),
        'data_format': pick_text(data, 'encodingFormat', 'format'),
        'keywords': pick_text(data, 'keywords'),
    }
    common.update(extract_contact(data))
    return common


def is_metadata_document(data):
    """메타데이터 문서로 볼 수 있는 JSON인지 판정 (대기실/에러 페이지 구분용)

    리뉴얼 후에는 title/organization 키가 없으므로 schema.org 표식(@type/@context)과
    name 을 근거로 삼고, 리뉴얼 전 저장분을 위해 옛 키도 함께 인정한다.
    """
    if not isinstance(data, dict):
        return False

    if pick_text(data, '@type') == 'Dataset':
        return True
    if 'schema.org' in pick_text(data, '@context'):
        return True
    if pick_text(data, 'name', 'title', 'organization'):
        return True

    return False

class BaseMetadataScanner:
    """공공데이터포털 메타데이터 스캐너 베이스 클래스"""
    
    def __init__(self, scan_type, start_num, end_num, max_workers=50, 
                 max_retries=3, retry_delay=1, timeout=5):
        self.start_num = start_num
        self.end_num = end_num
        self.max_workers = max_workers
        self.scan_type = scan_type
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.base_url = f"https://www.data.go.kr/catalog/{{}}/{self.scan_type}.json"
        self.results = {
            'total': 0,
            'with_data': 0,
            'without_data': 0,
            'failed': 0,
            'retried': 0,
            'retry_success': 0,
            'waiting_room_detected': 0,
            'data_numbers': [],
            'data_types': {},
            'details': {}
        }
        
        # 대기실 제어용 변수
        self.waiting_room_active = False
        self.waiting_room_lock = threading.Lock()
        self.paused_futures = []
    
    def is_waiting_room_response(self, response):
        """대기실 응답인지 확인"""
        try:
            # 1. URL 리다이렉션 확인
            if 'waitingroom' in response.url.lower():
                print(f"🚨 대기실 감지 (URL): {response.url}")
                return True
            
            # 2. JSON 파싱 시도
            #    Content-Type이 text/html이어도 본문은 JSON이므로 파싱이 먼저다.
            #    (대기실은 JSON을 돌려주지 않는다 - 파싱에 성공하면 정상 응답으로 본다)
            try:
                data = response.json()
                if isinstance(data, dict):
                    if data.get('description') == NOT_FOUND_DESCRIPTION:
                        return False
                    if is_metadata_document(data):
                        return False
                    if len(data) == 0:
                        return False
                elif isinstance(data, list):
                    return False

                return False

            except (json.JSONDecodeError, ValueError):
                pass
            
            # 3. Content-Type이 HTML이고 응답 내용에서 대기실 키워드 확인
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' in content_type:
                try:
                    response_text = response.text.lower()
                    waiting_room_patterns = [
                        ('waitingroom', 'main.html'),
                        ('대기실', '접속'),
                        ('대기실', '트래픽'),
                        ('접속 대기', ''),
                        ('잠시 대기', ''),
                        ('트래픽 과부하', ''),
                        ('서비스 대기', ''),
                        ('please wait', 'traffic'),
                        ('waiting room', ''),
                        ('대기 중', '과부하'),
                        ('서비스 점검', '대기')
                    ]
                    
                    for primary, secondary in waiting_room_patterns:
                        if primary in response_text:
                            if not secondary or secondary in response_text:
                                print(f"🚨 대기실 감지 (패턴 '{primary}'+'{secondary}'): {response.url}")
                                return True
                except:
                    pass
                
                print(f"⚠️  메타데이터 JSON이 아닌 HTML 사이트 수신 - URL: {response.url}")
                return False
            
            return False
                
        except Exception:
            return False
        
        return False
    
    def wait_for_site_recovery(self, test_num):
        """사이트 복구를 기다림"""
        print(f"\n🚨 대기실 감지! 사이트 복구 대기 중...")
        print(f"   📍 테스트 번호: {test_num}")
        
        recovery_check_interval = 30
        max_wait_time = 1800
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            try:
                test_url = self.base_url.format(test_num)
                response = requests.get(test_url, timeout=self.timeout)
                
                if response.status_code == 200 and not self.is_waiting_room_response(response):
                    try:
                        response.json()
                        print(f"✅ 사이트 복구 완료! ({elapsed_time}초 경과)")
                        return True
                    except (json.JSONDecodeError, ValueError):
                        pass
                
                print(f"⏳ 대기 중... ({elapsed_time}초 경과)")
                time.sleep(recovery_check_interval)
                elapsed_time += recovery_check_interval
                
            except Exception as e:
                print(f"⚠️ 복구 확인 중 오류: {str(e)}")
                time.sleep(recovery_check_interval)
                elapsed_time += recovery_check_interval
        
        print(f"❌ 최대 대기 시간 초과 ({max_wait_time}초)")
        return False
    
    def extract_data_info(self, data, num, has_data, retry_count):
        """데이터 정보 추출 - 하위 클래스에서 구현"""
        raise NotImplementedError("하위 클래스에서 구현해야 합니다")
    
    def check_metadata(self, num, retry_count=0):
        """단일 메타데이터 조회"""
        url = self.base_url.format(num)
        
        try:
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                # 대기실 응답인지 확인
                if self.is_waiting_room_response(response):
                    with self.waiting_room_lock:
                        if not self.waiting_room_active:
                            self.waiting_room_active = True
                            self.results['waiting_room_detected'] += 1
                            
                            # 사이트 복구 대기
                            if self.wait_for_site_recovery(self.end_num):
                                self.waiting_room_active = False
                                # 복구 후 재시도
                                return self.check_metadata(num, retry_count)
                            else:
                                return {
                                    'number': num,
                                    'has_data': False,
                                    'status': 'waiting_room_timeout',
                                    'error': '대기실 복구 대기 시간 초과',
                                    'retry_count': retry_count
                                }
                        else:
                            # 다른 스레드가 이미 대기실 처리 중
                            time.sleep(30)
                            return self.check_metadata(num, retry_count)
                
                data = response.json()
                
                # 데이터셋 존재 여부 확인
                if (
                    isinstance(data, dict) and
                    data.get('description') == NOT_FOUND_DESCRIPTION
                ):
                    return {
                        'number': num,
                        'has_data': False,
                        'status': 'not_found',
                        'error': f'{self.scan_type} 메타데이터 없음',
                        'retry_count': retry_count
                    }
                
                # 데이터 존재 여부 확인
                has_data = bool(data)
                
                # 데이터 정보 추출 (하위 클래스에서 구현)
                data_info = self.extract_data_info(data, num, has_data, retry_count)
                
                # 데이터 타입 통계 업데이트
                data_type_key = f"{self.scan_type}_type"
                if data_info.get(data_type_key):
                    data_type = data_info[data_type_key].upper()
                    self.results['data_types'][data_type] = self.results['data_types'].get(data_type, 0) + 1
                
                if has_data and (data_info.get('url') or data_info.get('title')):
                    self.results['data_numbers'].append(num)
                    
                return data_info
                
            elif response.status_code == 404:
                return {
                    'number': num,
                    'has_data': False,
                    'status': 'not_found',
                    'error': f'{self.scan_type} 메타데이터 없음',
                    'retry_count': retry_count
                }
            else:
                return {
                    'number': num,
                    'has_data': False,
                    'status': 'error',
                    'error': f'HTTP {response.status_code}',
                    'retry_count': retry_count
                }
                
        except requests.exceptions.Timeout:
            if retry_count < self.max_retries:
                time.sleep(self.retry_delay)
                return self.check_metadata(num, retry_count + 1)
            else:
                return {
                    'number': num,
                    'has_data': False,
                    'status': 'timeout',
                    'error': f'요청 시간 초과 (재시도 {retry_count}회 후 실패)',
                    'retry_count': retry_count
                }
        # requests의 JSONDecodeError는 RequestException도 상속하므로 반드시 먼저 잡는다
        except json.JSONDecodeError:
            print(f"⚠️  JSON 파싱 실패 - 번호: {num}")
            print(f"📄 응답 내용 (처음 500자):")
            print(response.text[:500])
            print("=" * 50)

            return {
                'number': num,
                'has_data': False,
                'status': 'error',
                'error': '잘못된 JSON 형식',
                'response_content': response.text[:500],
                'retry_count': retry_count
            }
        except requests.exceptions.RequestException as e:
            return {
                'number': num,
                'has_data': False,
                'status': 'error',
                'error': str(e),
                'retry_count': retry_count
            }
        except Exception as e:
            return {
                'number': num,
                'has_data': False,
                'status': 'error',
                'error': str(e),
                'retry_count': retry_count
            }
    
    def scan_range(self):
        """지정된 범위의 메타데이터 스캔"""
        total_numbers = self.end_num - self.start_num + 1
        self.results['total'] = total_numbers
        
        print(f"\n🔍 {self.scan_type} 메타데이터 스캔 시작")
        print(f"   📋 범위: {self.start_num} ~ {self.end_num}")
        print(f"   📊 총 {total_numbers:,}개 번호")
        print(f"   👥 동시 작업자: {self.max_workers}개")
        print(f"   🌐 Base URL: {self.base_url}")
        
        # 시작 시간 기록
        start_time = datetime.now()
        
        # 병렬 처리로 메타데이터 조회
        numbers = list(range(self.start_num, self.end_num + 1))
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_num = {
                executor.submit(self.check_metadata, num): num 
                for num in numbers
            }
            
            with tqdm(total=total_numbers, desc="스캔 진행") as pbar:
                for future in concurrent.futures.as_completed(future_to_num):
                    num = future_to_num[future]
                    
                    try:
                        result = future.result()
                        
                        # 결과 저장
                        self.results['details'][num] = result
                        
                        # 통계 업데이트
                        if result['status'] == 'success':
                            if result['has_data']:
                                self.results['with_data'] += 1
                            else:
                                self.results['without_data'] += 1
                            
                            if result.get('retry_count', 0) > 0:
                                self.results['retry_success'] += 1
                        else:
                            self.results['failed'] += 1
                        
                        if result.get('retry_count', 0) > 0:
                            self.results['retried'] += 1
                        
                    except Exception as e:
                        self.results['failed'] += 1
                        self.results['details'][num] = {
                            'number': num,
                            'has_data': False,
                            'status': 'exception',
                            'error': str(e)
                        }
                    
                    pbar.update(1)
                    
                    if pbar.n % 100 == 0:
                        success_rate = (self.results['with_data'] / pbar.n * 100) if pbar.n > 0 else 0
                        pbar.set_postfix({
                            '데이터있음': self.results['with_data'],
                            '데이터없음': self.results['without_data'],
                            '실패': self.results['failed'],
                            '성공률': f"{success_rate:.1f}%"
                        })
        
        # 종료 시간 및 소요 시간 계산
        end_time = datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()
        
        # 최종 결과 저장
        self.results['scan_time'] = {
            'start': start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'end': end_time.strftime('%Y-%m-%d %H:%M:%S'),
            'elapsed_seconds': elapsed_time,
            'elapsed_formatted': self._format_elapsed_time(elapsed_time)
        }
        
        # 데이터 번호 정렬
        self.results['data_numbers'].sort()
        
        return self.results
    
    def _format_elapsed_time(self, seconds):
        """초를 시:분:초 형식으로 변환"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}시간 {minutes}분 {secs}초"
        elif minutes > 0:
            return f"{minutes}분 {secs}초"
        else:
            return f"{secs}초"
    
    def save_results(self, output_dir="/data/metadata_results"):
        """스캔 결과 저장"""
        from scanner.reporting import save_results

        return save_results(
            self.results,
            self.scan_type,
            self.start_num,
            self.end_num,
            output_dir=output_dir,
        )
    
    def print_summary(self):
        """스캔 결과 요약 출력"""
        from scanner.reporting import print_summary

        print_summary(self.results, self.scan_type, self.start_num, self.end_num)
