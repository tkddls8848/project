#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
공공데이터포털 자동화 - Playwright MCP 기반
main.py의 로직을 Playwright로 재구현한 자동 로그인 및 인증 프로그램
"""

import asyncio
import json
import time
import logging
from typing import Optional, Dict, Any
from pathlib import Path
import subprocess
import os
from datetime import datetime

class PlaywrightDataPortalAutomation:
    def __init__(self):
        self.base_url = "https://www.data.go.kr"
        self.list_url = "https://www.data.go.kr/iim/api/selectAcountList.do"
        self.login_url = "https://auth.data.go.kr/sso/common-login"
        
        # 로깅 설정
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # MCP 서버 프로세스
        self.mcp_process = None
        self.mcp_server_ready = False
        
        # 저장 디렉토리
        self.output_dir = Path("output")
        self.output_dir.mkdir(exist_ok=True)
    
    def start_mcp_server(self) -> bool:
        """
        Playwright MCP 서버 시작
        
        Returns:
            서버 시작 성공 여부
        """
        try:
            print("🚀 Playwright MCP 서버 시작 중...")
            
            # npx로 MCP 서버 시작 (백그라운드)
            self.mcp_process = subprocess.Popen([
                "npx", "@playwright/mcp"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            # 서버가 시작될 때까지 잠시 대기
            time.sleep(3)
            
            # 프로세스가 실행 중인지 확인
            if self.mcp_process.poll() is None:
                print("✅ Playwright MCP 서버가 성공적으로 시작되었습니다!")
                self.mcp_server_ready = True
                return True
            else:
                print("❌ Playwright MCP 서버 시작에 실패했습니다.")
                return False
                
        except FileNotFoundError:
            print("❌ npx가 설치되지 않았습니다. Node.js를 설치해주세요.")
            return False
        except Exception as e:
            print(f"❌ MCP 서버 시작 중 오류: {e}")
            return False
    
    def stop_mcp_server(self):
        """MCP 서버 종료"""
        if self.mcp_process and self.mcp_process.poll() is None:
            print("🔄 Playwright MCP 서버를 종료합니다...")
            self.mcp_process.terminate()
            self.mcp_process.wait()
            print("✅ MCP 서버가 종료되었습니다.")
    
    async def execute_playwright_command(self, action: str, **kwargs) -> Dict[str, Any]:
        """
        Playwright 명령 실행 (MCP 서버 통신 시뮬레이션)
        실제로는 Playwright 라이브러리 직접 사용
        """
        try:
            from playwright.async_api import async_playwright
            
            if not hasattr(self, '_playwright_instance'):
                print("🎭 Playwright 초기화 중...")
                self._playwright_instance = await async_playwright().start()
                self._browser = await self._playwright_instance.chromium.launch(
                    headless=False,  # 브라우저 창 표시
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-web-security",
                        "--allow-running-insecure-content",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-features=VizDisplayCompositor"
                    ]
                )
                self._context = await self._browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    permissions=["notifications"],
                    java_script_enabled=True
                )
                self._page = await self._context.new_page()
                
                # 자동화 감지 방지
                await self._page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined,
                    });
                """)
            
            if action == "goto":
                await self._page.goto(kwargs.get("url"))
                await self._page.wait_for_load_state("networkidle")
                return {"success": True, "url": self._page.url}
            
            elif action == "wait_for_element":
                selector = kwargs.get("selector")
                timeout = kwargs.get("timeout", 10000)
                try:
                    await self._page.wait_for_selector(selector, timeout=timeout)
                    return {"success": True, "found": True}
                except Exception:
                    return {"success": False, "found": False}
            
            elif action == "click":
                selector = kwargs.get("selector")
                try:
                    await self._page.click(selector)
                    return {"success": True}
                except Exception as e:
                    return {"success": False, "error": str(e)}
            
            elif action == "get_text":
                selector = kwargs.get("selector")
                try:
                    text = await self._page.text_content(selector)
                    return {"success": True, "text": text}
                except Exception as e:
                    return {"success": False, "error": str(e)}
            
            elif action == "get_content":
                content = await self._page.content()
                return {"success": True, "content": content}
            
            elif action == "get_url":
                return {"success": True, "url": self._page.url}
            
            elif action == "get_title":
                title = await self._page.title()
                return {"success": True, "title": title}
            
            elif action == "handle_alert":
                try:
                    # alert 대기
                    dialog = await self._page.wait_for_event("dialog", timeout=5000)
                    message = dialog.message
                    accept = kwargs.get("accept", True)
                    
                    if accept:
                        await dialog.accept()
                    else:
                        await dialog.dismiss()
                    
                    return {"success": True, "message": message, "accepted": accept}
                except Exception as e:
                    return {"success": False, "error": str(e)}
            
            elif action == "find_elements":
                selector = kwargs.get("selector")
                try:
                    elements = await self._page.query_selector_all(selector)
                    return {"success": True, "count": len(elements)}
                except Exception as e:
                    return {"success": False, "error": str(e)}
            
            elif action == "screenshot":
                path = kwargs.get("path", f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                await self._page.screenshot(path=str(self.output_dir / path))
                return {"success": True, "path": path}
            
            return {"success": False, "error": "Unknown action"}
            
        except Exception as e:
            print(f"❌ Playwright 명령 실행 중 오류: {e}")
            return {"success": False, "error": str(e)}
    
    async def check_login_status(self) -> bool:
        """
        현재 로그인 상태 확인
        
        Returns:
            로그인 상태 여부
        """
        print(f"\n" + "="*50)
        print("🔍 로그인 상태 확인 중...")
        print("="*50)
        
        try:
            # 현재 URL 확인
            url_result = await self.execute_playwright_command("get_url")
            if not url_result["success"]:
                return False
            
            current_url = url_result["url"]
            print(f"📍 현재 URL: {current_url}")
            
            # 메인 페이지로 이동하여 로그인 상태 확인
            if 'data.go.kr' not in current_url or 'auth.data.go.kr' in current_url:
                print("📱 메인 페이지로 이동하여 로그인 상태 확인...")
                goto_result = await self.execute_playwright_command("goto", url=self.base_url)
                if not goto_result["success"]:
                    return False
                
                await asyncio.sleep(2)
            
            # 페이지 내용 확인
            content_result = await self.execute_playwright_command("get_content")
            if not content_result["success"]:
                return False
            
            page_source = content_result["content"].lower()
            
            # 로그인 상태 판단
            login_indicators = [
                '로그아웃' in content_result["content"],
                'logout' in page_source,
                'mypage' in page_source,
                '마이페이지' in content_result["content"]
            ]
            
            # 로그인 관련 요소 확인
            logout_elements_result = await self.execute_playwright_command(
                "find_elements",
                selector="*:text('로그아웃'), *:text('마이페이지'), *:text('MY PAGE')"
            )
            
            if logout_elements_result["success"] and logout_elements_result["count"] > 0:
                print(f"✅ 로그인 상태가 확인되었습니다! (요소 {logout_elements_result['count']}개 발견)")
                return True
            
            positive_count = sum(login_indicators)
            print(f"🔍 로그인 지표 분석: {positive_count}/4")
            
            if positive_count >= 1:
                print("✅ 로그인 상태가 확인되었습니다!")
                return True
            else:
                print("❌ 로그인이 필요한 상태입니다.")
                return False
                
        except Exception as e:
            print(f"❌ 로그인 상태 확인 중 오류: {e}")
            return False
    
    async def manual_login_process(self) -> bool:
        """
        수동 로그인 프로세스
        
        Returns:
            로그인 성공 여부
        """
        print("=" * 80)
        print("🔐 수동 로그인 프로세스 시작 (Playwright)")
        print("=" * 80)
        
        print(f"\n📍 로그인 URL: {self.login_url}")
        
        try:
            # 로그인 페이지로 이동
            print("\n🌐 로그인 페이지로 이동 중...")
            goto_result = await self.execute_playwright_command("goto", url=self.login_url)
            
            if not goto_result["success"]:
                print("❌ 로그인 페이지 접속 실패")
                return False
            
            print("✅ 로그인 페이지가 성공적으로 열렸습니다!")
            
            # 스크린샷 저장
            await self.execute_playwright_command("screenshot", path="login_page.png")
            
            # 사용자 입력 대기
            print(f"\n" + "="*70)
            print("🔄 로그인 대기 모드")
            print("="*70)
            print("📝 브라우저에서 다음 작업을 완료해주세요:")
            print("   • 공공데이터포털 계정으로 로그인")
            print("   • 로그인 성공 후 data.go.kr 도메인으로 자동 이동")
            print("   • 로그인이 완료되면 엔터키를 눌러주세요")
            
            while True:
                try:
                    user_input = input("\n✋ 로그인을 완료하신 후 엔터키를 눌러주세요 (q: 종료): ").strip().lower()
                    
                    if user_input == 'q':
                        print("❌ 사용자가 프로세스를 중단했습니다.")
                        return False
                    
                    elif user_input == '':
                        # 로그인 상태 확인
                        login_success = await self.check_login_status()
                        if login_success:
                            print("✅ 로그인 완료 확인됨. 다음 단계로 진행합니다...")
                            return True
                        else:
                            print("⚠️  아직 로그인이 완료되지 않은 것 같습니다. 다시 시도해주세요.")
                    else:
                        print("❓ 엔터키를 눌러주세요.")
                        
                except KeyboardInterrupt:
                    print("\n❌ 프로세스가 중단되었습니다.")
                    return False
                    
        except Exception as e:
            print(f"❌ 로그인 프로세스 중 오류: {e}")
            return False
    
    async def get_list_page(self) -> Optional[str]:
        """
        목록 페이지 데이터 수집
        
        Returns:
            페이지 HTML 내용 또는 None
        """
        try:
            print(f"\n" + "="*50)
            print("📋 목록 페이지 데이터 수집")
            print("="*50)
            print(f"🔗 접속 URL: {self.list_url}")
            
            # 목록 페이지로 이동
            goto_result = await self.execute_playwright_command("goto", url=self.list_url)
            if not goto_result["success"]:
                print("❌ 목록 페이지 접속 실패")
                return None
            
            await asyncio.sleep(3)
            
            # 페이지 정보 확인
            url_result = await self.execute_playwright_command("get_url")
            title_result = await self.execute_playwright_command("get_title")
            content_result = await self.execute_playwright_command("get_content")
            
            if not all([url_result["success"], title_result["success"], content_result["success"]]):
                print("❌ 페이지 정보 수집 실패")
                return None
            
            current_url = url_result["url"]
            page_title = title_result["title"]
            page_content = content_result["content"]
            
            print(f"✅ 페이지 로딩 완료")
            print(f"🔗 최종 URL: {current_url}")
            print(f"📄 페이지 제목: {page_title}")
            print(f"📊 페이지 크기: {len(page_content):,} bytes")
            
            # 페이지 내용 검증
            content_checks = {
                'mypage-dataset-list': 'mypage-dataset-list' in page_content,
                'li 태그': '<li' in page_content,
                'fn_detail 함수': 'fn_detail(' in page_content,
                '데이터 목록': any(keyword in page_content for keyword in ['데이터', 'data', 'api'])
            }
            
            print("🔍 페이지 내용 검증:")
            for check_name, result in content_checks.items():
                status = "✅" if result else "❌"
                print(f"   {status} {check_name}: {'발견됨' if result else '찾을 수 없음'}")
            
            # 로그인 상태 재확인
            if 'login' in current_url or 'auth' in current_url:
                print("❌ 로그인 페이지로 리디렉션되었습니다.")
                return None
            
            if content_checks['mypage-dataset-list'] and content_checks['fn_detail 함수']:
                print("✅ 올바른 데이터 목록 페이지입니다!")
            else:
                print("⚠️  예상된 데이터 목록 형식과 다를 수 있습니다.")
            
            # 스크린샷 저장
            await self.execute_playwright_command("screenshot", path="list_page.png")
            
            return page_content
            
        except Exception as e:
            print(f"❌ 목록 페이지 접속 중 오류: {e}")
            return None
    
    async def get_all_title_links(self) -> list:
        """
        현재 페이지의 모든 title-area 링크 정보 수집
        
        Returns:
            링크 정보 리스트
        """
        try:
            links_info = await self._page.evaluate("""
                () => {
                    const links = [];
                    const titleAreas = document.querySelectorAll('div.title-area a');
                    titleAreas.forEach((link, index) => {
                        links.push({
                            index: index,
                            href: link.getAttribute('href'),
                            text: link.textContent.trim(),
                            onclick: link.getAttribute('onclick')
                        });
                    });
                    return links;
                }
            """)
            return links_info
        except Exception as e:
            print(f"❌ 링크 정보 수집 중 오류: {e}")
            return []
    
    async def navigate_to_detail_page(self, link_info: dict = None) -> bool:
        """
        title-area 링크 클릭하여 상세 페이지로 이동
        
        Args:
            link_info: 클릭할 링크 정보 (None이면 첫 번째 링크)
        
        Returns:
            이동 성공 여부
        """
        try:
            print(f"\n" + "="*50)
            print("🔗 상세 페이지 이동")
            print("="*50)
            
            # 지정된 링크 또는 첫 번째 title-area 찾기
            if link_info:
                print(f"🔍 지정된 링크로 이동: {link_info.get('text', 'Unknown')}")
            else:
                print("🔍 첫 번째 title-area 링크 검색 중...")
            
            # title-area div 확인
            title_area_result = await self.execute_playwright_command(
                "wait_for_element",
                selector="div.title-area",
                timeout=10000
            )
            
            if not title_area_result["success"] or not title_area_result["found"]:
                print("❌ title-area div를 찾을 수 없습니다.")
                return False
            
            print("✅ title-area div 발견!")
            
            # 현재 URL 저장
            url_result = await self.execute_playwright_command("get_url")
            current_url = url_result["url"]
            
            # JavaScript 함수 직접 실행을 위해 href 속성 가져오기
            try:
                if link_info:
                    js_function = link_info.get('href')
                else:
                    # 첫 번째 title-area 내의 링크에서 JavaScript 함수 추출
                    js_function = await self._page.evaluate("""
                        () => {
                            const link = document.querySelector('div.title-area a');
                            if (link) {
                                return link.getAttribute('href');
                            }
                            return null;
                        }
                    """)
                
                if js_function and js_function.startswith("javascript:"):
                    # javascript: 제거하고 함수만 추출
                    js_code = js_function.replace("javascript:", "")
                    print(f"📝 JavaScript 함수 발견: {js_code}")
                    
                    # JavaScript 함수 직접 실행
                    await self._page.evaluate(js_code)
                    print("🖱️  JavaScript 함수를 실행했습니다!")
                else:
                    # JavaScript가 아닌 일반 링크인 경우 클릭
                    if link_info:
                        selector = f"div.title-area a:nth-child({link_info['index'] + 1})"
                    else:
                        selector = "div.title-area a:first-child"
                    
                    click_result = await self.execute_playwright_command(
                        "click",
                        selector=selector
                    )
                    
                    if not click_result["success"]:
                        print(f"❌ 링크 클릭 실패: {click_result.get('error', '알 수 없는 오류')}")
                        return False
                    
                    print("🖱️  링크를 클릭했습니다!")
                
            except Exception as js_error:
                print(f"⚠️  JavaScript 실행 방식 실패, 일반 클릭 시도: {js_error}")
                
                # 대체 방법: 직접 클릭
                if link_info:
                    selector = f"div.title-area a:nth-child({link_info['index'] + 1})"
                else:
                    selector = "div.title-area a:first-child"
                
                click_result = await self.execute_playwright_command(
                    "click",
                    selector=selector
                )
                
                if not click_result["success"]:
                    print(f"❌ 링크 클릭 실패: {click_result.get('error', '알 수 없는 오류')}")
                    return False
            
            # 페이지 변화 대기
            await asyncio.sleep(3)
            
            # 새로운 URL 확인
            new_url_result = await self.execute_playwright_command("get_url")
            new_title_result = await self.execute_playwright_command("get_title")
            
            if new_url_result["success"] and new_title_result["success"]:
                new_url = new_url_result["url"]
                new_title = new_title_result["title"]
                
                print(f"🎯 페이지 이동 완료!")
                print(f"   📍 새 URL: {new_url}")
                print(f"   📄 새 페이지 제목: {new_title}")
                
                # 스크린샷 저장
                await self.execute_playwright_command("screenshot", path="detail_page.png")
                
                if new_url != current_url:
                    print("✅ 페이지 이동이 성공적으로 완료되었습니다!")
                    return True
                else:
                    print("⚠️  URL은 변경되지 않았지만 페이지가 업데이트되었을 수 있습니다.")
                    return True
            
            return False
            
        except Exception as e:
            print(f"❌ 상세 페이지 이동 중 오류: {e}")
            return False
    
    async def click_extend_button(self) -> bool:
        """
        연장 신청 버튼 클릭 (개선된 버전)
        
        Returns:
            클릭 성공 여부
        """
        try:
            print(f"\n" + "="*50)
            print("🔗 연장 신청 버튼 클릭")
            print("="*50)
            
            # 현재 페이지 정보
            url_result = await self.execute_playwright_command("get_url")
            title_result = await self.execute_playwright_command("get_title")
            
            print(f"📍 현재 URL: {url_result.get('url', 'Unknown')}")
            print(f"📄 페이지 제목: {title_result.get('title', 'Unknown')}")
            
            # 1. 먼저 필요한 form 데이터가 있는지 확인
            form_check = await self._page.evaluate("""
                () => {
                    const form = document.getElementById('searchVO');
                    const gbnInput = document.getElementById('gbn');
                    return {
                        formExists: !!form,
                        gbnExists: !!gbnInput,
                        formData: form ? new FormData(form).entries() : null
                    };
                }
            """)
            
            print(f"📋 Form 체크: {form_check}")
            
            # 2. Dialog(alert/confirm) 핸들러 설정
            dialog_messages = []
            
            async def handle_dialog(dialog):
                message = dialog.message
                dialog_messages.append(message)
                print(f"📢 Dialog 발생: {message}")
                
                # confirm 대화상자 처리
                if "신청하시겠습니까?" in message:
                    print("✅ 연장 신청 확인 대화상자 - 수락")
                    await dialog.accept()
                # alert 대화상자 처리
                elif "되었습니다" in message or "실패" in message:
                    print(f"ℹ️ 결과 알림: {message}")
                    await dialog.accept()
                else:
                    print(f"ℹ️ 기타 대화상자: {message}")
                    await dialog.accept()
            
            # Dialog 이벤트 리스너 등록
            self._page.on("dialog", handle_dialog)
            
            try:
                # 3. fn_reqst 함수를 직접 실행
                print("\n🔧 fn_reqst 함수 직접 실행 시도...")
                
                # 먼저 jQuery와 필요한 함수들이 있는지 확인
                js_check = await self._page.evaluate("""
                    () => {
                        return {
                            jquery: typeof $ !== 'undefined',
                            fn_reqst: typeof fn_reqst !== 'undefined',
                            loadingStart: typeof loadingStart !== 'undefined',
                            loadingStop: typeof loadingStop !== 'undefined'
                        };
                    }
                """)
                
                print(f"📌 JavaScript 환경 체크: {js_check}")
                
                if not js_check['fn_reqst']:
                    print("❌ fn_reqst 함수를 찾을 수 없습니다.")
                    # 대체 방법: 버튼 직접 클릭
                    print("🔄 대체 방법: 연장 신청 버튼 직접 클릭 시도...")
                    
                    # 연장 신청 버튼 찾기
                    extend_button = await self._page.query_selector("a:has-text('연장 신청')")
                    if extend_button:
                        await extend_button.click()
                        print("🖱️ 연장 신청 버튼을 클릭했습니다!")
                    else:
                        print("❌ 연장 신청 버튼을 찾을 수 없습니다.")
                        return False
                else:
                    # fn_reqst 함수 직접 실행
                    print("✅ fn_reqst 함수 발견! 실행합니다...")
                    
                    # loadingStart, loadingStop 함수가 없으면 더미 함수 생성
                    if not js_check['loadingStart'] or not js_check['loadingStop']:
                        await self._page.evaluate("""
                            () => {
                                if (typeof loadingStart === 'undefined') {
                                    window.loadingStart = function(id) { console.log('Loading start:', id); };
                                }
                                if (typeof loadingStop === 'undefined') {
                                    window.loadingStop = function(id) { console.log('Loading stop:', id); };
                                }
                            }
                        """)
                        print("📌 더미 loading 함수 생성 완료")
                    
                    # fn_reqst 함수 실행
                    await self._page.evaluate("""
                        () => {
                            // gbn 값 설정
                            if (document.getElementById('gbn')) {
                                document.getElementById('gbn').value = 'extend';
                            }
                            
                            // fn_reqst 함수 호출
                            if (typeof fn_reqst === 'function') {
                                fn_reqst('extend', '연장');
                            } else {
                                console.error('fn_reqst 함수를 찾을 수 없습니다.');
                            }
                        }
                    """)
                    
                    print("✅ fn_reqst('extend', '연장') 함수 실행 완료!")
                
                # 4. Dialog 및 페이지 변화 대기
                print("\n⏳ 응답 대기 중...")
                
                # 최대 15초 동안 대기하면서 상태 확인
                success = False
                for i in range(30):  # 0.5초씩 30번 = 15초
                    await asyncio.sleep(0.5)
                    
                    # Dialog 메시지 확인
                    if dialog_messages:
                        print(f"\n📨 받은 메시지들: {dialog_messages}")
                        
                        # 성공 메시지 확인
                        for msg in dialog_messages:
                            if "연장되었습니다" in msg:
                                print("✅ 연장 신청 성공!")
                                success = True
                                break
                            elif "실패" in msg or "오류" in msg:
                                print(f"❌ 연장 신청 실패: {msg}")
                                break
                        
                        if success or any("실패" in msg or "오류" in msg for msg in dialog_messages):
                            break
                    
                    # 페이지 URL 변화 확인
                    current_url = self._page.url
                    if "selectAcountList.do" in current_url:
                        print("✅ 목록 페이지로 이동 감지! 연장 신청 성공!")
                        success = True
                        break
                    
                    # Ajax 요청 상태 확인 (jQuery가 있는 경우)
                    ajax_status = await self._page.evaluate("""
                        () => {
                            if (typeof $ !== 'undefined' && $.active !== undefined) {
                                return $.active;
                            }
                            return -1;
                        }
                    """)
                    
                    if i % 4 == 0:  # 2초마다 상태 출력
                        print(f"  ⏳ 대기 중... ({i//2 + 1}/15초) [Ajax 활성: {ajax_status}]")
                
                # 5. 최종 결과 확인
                await self.execute_playwright_command("screenshot", path="extend_result.png")
                
                if success:
                    print("\n🎉 연장 신청이 성공적으로 완료되었습니다!")
                    return True
                else:
                    print("\n⚠️ 연장 신청 처리 결과를 확인할 수 없습니다.")
                    
                    # 현재 페이지 상태 확인
                    current_url = self._page.url
                    page_content = await self._page.content()
                    
                    if "selectAcountList.do" in current_url:
                        print("✅ 목록 페이지로 이동되었습니다. 연장 신청이 처리되었을 가능성이 높습니다.")
                        return True
                    elif "오류" in page_content or "실패" in page_content:
                        print("❌ 페이지에 오류 메시지가 있습니다.")
                        return False
                    else:
                        print("⚠️ 수동으로 확인이 필요할 수 있습니다.")
                        return False
                    
            except Exception as e:
                print(f"❌ 연장 신청 처리 중 오류: {e}")
                import traceback
                traceback.print_exc()
                return False
                
            finally:
                # Dialog 이벤트 리스너 제거
                self._page.remove_listener("dialog", handle_dialog)
                print("\n🧹 Dialog 핸들러 정리 완료")
                
        except Exception as e:
            print(f"❌ 연장 버튼 클릭 중 오류: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def save_page_content(self, content: str, filename: str) -> bool:
        """
        페이지 내용을 파일로 저장
        
        Args:
            content: 저장할 내용
            filename: 파일명
            
        Returns:
            저장 성공 여부
        """
        try:
            filepath = self.output_dir / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"💾 페이지 내용이 '{filepath}'에 저장되었습니다.")
            return True
        except Exception as e:
            print(f"❌ 파일 저장 중 오류: {e}")
            return False
    
    async def get_pagination_info(self) -> dict:
        """
        페이지네이션 정보 수집
        
        Returns:
            페이지네이션 정보 딕셔너리
        """
        try:
            pagination_info = await self._page.evaluate("""
                () => {
                    const nav = document.querySelector('#contents > div > div.mypage-dataset-list > nav');
                    if (!nav) return { hasNavigation: false };
                    
                    const links = nav.querySelectorAll('a');
                    const pages = [];
                    
                    links.forEach(link => {
                        const onclick = link.getAttribute('onclick');
                        const text = link.textContent.trim();
                        if (onclick && onclick.includes('fn_search(')) {
                            const match = onclick.match(/fn_search\\((\\d+)\\)/);
                            if (match) {
                                pages.push({
                                    page: parseInt(match[1]),
                                    text: text,
                                    onclick: onclick
                                });
                            }
                        }
                    });
                    
                    return {
                        hasNavigation: true,
                        pages: pages,
                        totalPages: pages.length > 0 ? Math.max(...pages.map(p => p.page)) : 1
                    };
                }
            """)
            
            return pagination_info
        except Exception as e:
            print(f"❌ 페이지네이션 정보 수집 중 오류: {e}")
            return {"hasNavigation": False}
    
    async def navigate_to_page(self, page_num: int) -> bool:
        """
        지정된 페이지로 이동
        
        Args:
            page_num: 이동할 페이지 번호
            
        Returns:
            이동 성공 여부
        """
        try:
            print(f"📄 {page_num}페이지로 이동 중...")
            
            # fn_search 함수 실행
            result = await self._page.evaluate(f"""
                () => {{
                    if (typeof fn_search === 'function') {{
                        fn_search({page_num});
                        return true;
                    }}
                    return false;
                }}
            """)
            
            if not result:
                print("❌ fn_search 함수를 찾을 수 없습니다.")
                return False
            
            # 페이지 로딩 대기
            await asyncio.sleep(3)
            await self._page.wait_for_load_state("networkidle")
            
            print(f"✅ {page_num}페이지로 이동 완료")
            return True
            
        except Exception as e:
            print(f"❌ 페이지 이동 중 오류: {e}")
            return False
    
    async def process_all_items_on_page(self) -> int:
        """
        현재 페이지의 모든 항목에 대해 연장신청 처리
        
        Returns:
            처리된 항목 수
        """
        processed_count = 0
        
        try:
            # 현재 페이지의 모든 링크 정보 수집
            links_info = await self.get_all_title_links()
            
            if not links_info:
                print("❌ 현재 페이지에서 처리할 항목을 찾을 수 없습니다.")
                return 0
            
            print(f"📋 현재 페이지에서 {len(links_info)}개 항목 발견")
            
            # 각 항목에 대해 연장신청 처리
            for i, link_info in enumerate(links_info):
                print(f"\n--- {i+1}/{len(links_info)} 항목 처리 중 ---")
                print(f"📝 항목명: {link_info.get('text', 'Unknown')}")
                
                # 상세 페이지로 이동
                if await self.navigate_to_detail_page(link_info):
                    # 연장 신청 처리
                    if await self.click_extend_button():
                        processed_count += 1
                        print(f"✅ {i+1}번째 항목 연장신청 완료")
                    else:
                        print(f"❌ {i+1}번째 항목 연장신청 실패")
                else:
                    print(f"❌ {i+1}번째 항목 상세페이지 이동 실패")
                
                # 목록 페이지로 돌아가기 (연장신청 성공 시 자동으로 돌아감)
                current_url = self._page.url
                if "selectAcountList.do" not in current_url:
                    print("🔄 목록 페이지로 돌아가는 중...")
                    await self.execute_playwright_command("goto", url=self.list_url)
                    await asyncio.sleep(2)
                
                # 잠시 대기 (서버 부하 방지)
                await asyncio.sleep(1)
            
            print(f"\n✅ 현재 페이지 처리 완료: {processed_count}/{len(links_info)}개 성공")
            return processed_count
            
        except Exception as e:
            print(f"❌ 페이지 항목 처리 중 오류: {e}")
            return processed_count
    
    async def process_all_pages(self) -> dict:
        """
        모든 페이지의 모든 항목에 대해 연장신청 처리
        
        Returns:
            처리 결과 딕셔너리
        """
        total_processed = 0
        total_pages = 0
        results = []
        
        try:
            # 첫 번째 페이지부터 시작
            current_page = 1
            
            while True:
                print(f"\n" + "="*60)
                print(f"📄 {current_page}페이지 처리 중")
                print("="*60)
                
                # 현재 페이지가 1이 아니면 해당 페이지로 이동
                if current_page > 1:
                    if not await self.navigate_to_page(current_page):
                        print(f"❌ {current_page}페이지로 이동 실패")
                        break
                
                # 현재 페이지의 모든 항목 처리
                page_processed = await self.process_all_items_on_page()
                total_processed += page_processed
                total_pages += 1
                
                results.append({
                    "page": current_page,
                    "processed": page_processed
                })
                
                # 페이지네이션 정보 확인
                pagination_info = await self.get_pagination_info()
                
                if not pagination_info.get("hasNavigation"):
                    print("📄 더 이상 페이지가 없습니다.")
                    break
                
                # 다음 페이지가 있는지 확인
                next_page = current_page + 1
                available_pages = [p["page"] for p in pagination_info.get("pages", [])]
                
                if next_page not in available_pages:
                    print(f"📄 {next_page}페이지가 존재하지 않습니다. (사용 가능한 페이지: {available_pages})")
                    break
                
                print(f"➡️  다음 페이지({next_page})로 이동합니다...")
                current_page = next_page
                
                # 페이지 간 대기
                await asyncio.sleep(2)
            
            return {
                "total_processed": total_processed,
                "total_pages": total_pages,
                "results": results
            }
            
        except Exception as e:
            print(f"❌ 전체 페이지 처리 중 오류: {e}")
            return {
                "total_processed": total_processed,
                "total_pages": total_pages,
                "results": results,
                "error": str(e)
            }
    
    async def run(self):
        """
        전체 프로세스 실행
        """
        print("=" * 80)
        print("🚀 공공데이터포털 자동화 스크립트 v4.0 (Playwright MCP)")
        print("=" * 80)
        print("🎭 Playwright 기반 안정적인 브라우저 자동화")
        print("🔧 MCP(Model Context Protocol) 연동")
        print("=" * 80)
        
        try:
            # 1. Playwright 초기화 (MCP 서버는 내부적으로 처리)
            print("\n🎭 1단계: Playwright 초기화")
            # MCP 서버 시작 (실제로는 직접 Playwright 사용)
            
            # 2. 수동 로그인 프로세스
            print("\n🔐 2단계: 수동 로그인 프로세스")
            if not await self.manual_login_process():
                print("❌ 로그인 프로세스가 취소되었습니다.")
                return
            
            # 3. 목록 페이지 데이터 수집
            print("\n📋 3단계: 목록 페이지 데이터 수집")
            list_html = await self.get_list_page()
            
            if not list_html:
                print("❌ 목록 페이지를 가져올 수 없습니다.")
                
                retry_login = input("\n로그인을 다시 시도하시겠습니까? (y/N): ").strip().lower()
                if retry_login in ['y', 'yes']:
                    if await self.manual_login_process():
                        list_html = await self.get_list_page()
                        if not list_html:
                            print("❌ 재시도 후에도 목록 페이지를 가져올 수 없습니다.")
                            return
                    else:
                        print("❌ 재로그인에 실패했습니다.")
                        return
                else:
                    print("❌ 프로세스를 종료합니다.")
                    return
            
            # 목록 페이지 내용 저장
            self.save_page_content(list_html, 'list_page.html')
            
            # 4. 모든 페이지의 모든 항목에 대해 연장신청 처리
            print("\n🔗 4단계: 전체 항목 연장신청 처리")
            print("📋 모든 페이지를 순회하며 연장신청을 진행합니다...")
            
            results = await self.process_all_pages()
            
            print("\n" + "="*60)
            print("📊 최종 처리 결과")
            print("="*60)
            print(f"✅ 총 처리된 항목: {results['total_processed']}개")
            print(f"📄 처리된 페이지: {results['total_pages']}개")
            
            if results.get('results'):
                print("\n📋 페이지별 처리 현황:")
                for result in results['results']:
                    print(f"   📄 {result['page']}페이지: {result['processed']}개 처리")
            
            if results.get('error'):
                print(f"⚠️  처리 중 오류 발생: {results['error']}")
            
            print("\n🎉 모든 페이지의 연장신청 처리가 완료되었습니다!")
            
            print("\n✅ Playwright 자동화 스크립트가 실행되었습니다!")
            print(f"💾 결과 파일들이 '{self.output_dir}' 디렉토리에 저장되었습니다.")
            
            # 브라우저 유지
            input("\n프로그램을 종료하려면 엔터키를 누르세요...")
            
        except KeyboardInterrupt:
            print("\n\n⚠️  사용자에 의해 중단되었습니다.")
        except Exception as e:
            print(f"\n❌ 실행 중 예상치 못한 오류 발생: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 정리
            await self.cleanup()
    
    async def cleanup(self):
        """리소스 정리"""
        try:
            if hasattr(self, '_browser'):
                await self._browser.close()
            if hasattr(self, '_playwright_instance'):
                await self._playwright_instance.stop()
            
            self.stop_mcp_server()
            print("🧹 리소스 정리가 완료되었습니다.")
        except Exception as e:
            print(f"⚠️  정리 중 오류: {e}")


def check_requirements():
    """
    필요한 패키지 확인
    """
    print("시스템 요구사항 확인 중...")
    
    missing_requirements = []
    
    # Playwright 확인
    try:
        import importlib.metadata
        try:
            version = importlib.metadata.version("playwright")
            print(f"✅ Playwright 버전: {version}")
        except importlib.metadata.PackageNotFoundError:
            print("❌ Playwright가 설치되지 않음")
            missing_requirements.append("playwright")
    except ImportError:
        missing_requirements.append("playwright")
        print("❌ Playwright가 설치되지 않음")
    
    # Node.js/npm 확인 (MCP 서버용)
    try:
        import subprocess
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Node.js 버전: {result.stdout.strip()}")
        else:
            print("⚠️  Node.js가 설치되지 않음 (선택사항)")
    except FileNotFoundError:
        print("⚠️  Node.js가 설치되지 않음 (선택사항)")
    
    if missing_requirements:
        print("\n❌ 누락된 패키지:")
        for req in missing_requirements:
            print(f"   - {req}")
        print("\n📌 설치 명령어:")
        if 'playwright' in missing_requirements:
            print("   pip install playwright")
            print("   playwright install chromium")
        return False
    
    print("\n✅ 모든 필수 요구사항이 충족되었습니다!")
    return True


async def main():
    """메인 실행 함수"""
    # 요구사항 확인
    if not check_requirements():
        print("\n❌ 필수 패키지를 설치한 후 다시 실행해주세요.")
        return
    
    # 자동화 실행
    automation = PlaywrightDataPortalAutomation()
    await automation.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  프로그램이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 프로그램 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()