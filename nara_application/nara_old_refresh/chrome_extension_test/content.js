// 고속 연장기 (API Mode) - content.js

// 유틸리티: 로그 전송
function log(msg) {
    console.log(`[FastExt] ${msg}`);
    chrome.runtime.sendMessage({ action: 'LOG', message: msg });
}

// 상태 변수
let isRunning = false;
let processedCount = 0;
let failCount = 0;

// inject.js 주입 (페이지 함수 실행용 - 페이지네이션 등)
function injectPageScript() {
    const script = document.createElement('script');
    script.src = chrome.runtime.getURL('inject.js');
    script.onload = function() { this.remove(); };
    (document.head || document.documentElement).appendChild(script);
}

// inject.js로 명령 전송
function sendPageCommand(action, data = {}) {
    window.dispatchEvent(new CustomEvent('NARA_EXTENSION_CMD', { detail: { action, ...data } }));
}

// 초기화
injectPageScript();

// 메시지 리스너 (Popup/Background 통신)
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'START') {
        if (!isRunning) {
            isRunning = true;
            processedCount = 0;
            failCount = 0;
            log("고속 연장 작업 시작...");
            processListPage();
        }
        sendResponse({ success: true });
    } else if (request.action === 'STOP') {
        isRunning = false;
        log("작업 중지 요청됨.");
        sendResponse({ success: true });
    }
});

// 자동 시작 체크 (페이지 이동 후 계속 실행)
chrome.storage.local.get(['isRunning'], (data) => {
    if (data.isRunning) {
        isRunning = true;
        log("페이지 로드 감지. 작업 재개...");
        setTimeout(processListPage, 1000); // DOM 안정화 대기
    }
});

// --- 핵심 로직: 목록 처리 및 API 호출 ---

async function processListPage() {
    if (!isRunning) return;

    // 1. 목록 링크 찾기
    // div.title-area 하위의 a 태그들
    const links = Array.from(document.querySelectorAll('div.title-area a'));
    const totalItems = links.length;

    log(`현재 페이지에서 ${totalItems}개 항목 발견.`);

    if (totalItems === 0) {
        log("항목이 없습니다. 다음 페이지 확인...");
        goToNextPage();
        return;
    }

    // 2. 순차/병렬 처리
    // 너무 빠르면 차단되므로 1건씩 순차 처리하되 딜레이 최소화 (0.5초)
    for (let i = 0; i < totalItems; i++) {
        if (!isRunning) break;

        const link = links[i];
        const title = link.textContent.trim();
        log(`[${i + 1}/${totalItems}] 처리 중: ${title}`);

        try {
            // 상세 페이지 URL 추출
            const detailUrl = extractDetailUrl(link);
            if (!detailUrl) {
                log(`  -> URL 추출 실패. 스킵.`);
                failCount++;
                continue;
            }

            // 상세 페이지 내용 Fetch (화면 이동 X)
            const htmlText = await fetchDetailPage(detailUrl);
            if (!htmlText) {
                log(`  -> 상세 페이지 로드 실패. 스킵.`);
                failCount++;
                continue;
            }

            // 폼 데이터 파싱
            const formData = parseFormData(htmlText);
            if (!formData) {
                log(`  -> 폼 데이터 파싱 실패 (연장 대상 아닐 수 있음). 스킵.`);
                failCount++; // 연장 버튼이 없는 경우 등
                continue;
            }

            // 연장 API 호출
            const result = await callExtendApi(formData);
            if (result) {
                log(`  -> 연장 신청 성공!`);
                processedCount++;
            } else {
                log(`  -> 연장 신청 실패.`);
                failCount++;
            }

        } catch (e) {
            log(`  -> 에러 발생: ${e.message}`);
            failCount++;
        }

        // 밴 방지 딜레이 (0.5초 ~ 1초 랜덤)
        const delay = 500 + Math.random() * 500;
        await new Promise(r => setTimeout(r, delay));
    }

    if (isRunning) {
        log(`현재 페이지 완료. (성공: ${processedCount}, 실패: ${failCount})`);
        goToNextPage();
    }
}

// 링크 요소에서 상세 URL 추출
function extractDetailUrl(linkElement) {
    const href = linkElement.getAttribute('href');
    const onclick = linkElement.getAttribute('onclick');

    // Case 1: href가 URL인 경우
    if (href && !href.startsWith('javascript:') && href.length > 1) {
        return href;
    }

    // Case 2: onclick="fn_detail('ID')" 등에서 ID 추출
    // 정확한 패턴을 모르므로, issue.md의 리스트 패턴을 추정
    // 보통 javascript:fn_movePage(this, 'ID', '/path/to.do') 형태라면
    // 3번째 인자가 URL임.
    if (onclick && onclick.includes('fn_movePage')) {
        const parts = onclick.split("'");
        // parts[1]: this (or ID), parts[3]: ID, parts[5]: URL
        // 인자 순서가 fn_movePage(obj, menuId, menuUrl) 이라면 
        // 정규식으로 안전하게 추출
        const match = onclick.match(/fn_movePage\s*\([^,]+,\s*'[^']+',\s*'([^']+)'/);
        if (match && match[1]) {
            return match[1];
        }
    }
    
    // Case 3: fn_detail 등 다른 함수일 경우
    // 현재 URL이 목록 페이지라면, 상세 페이지는 보통 같은 경로 + View.do 등
    // 하지만 정확한 URL을 모르면 Fetch 불가.
    // 만약 href가 javascript:fn_detail() 이라면, 이는 form submit일 가능성 높음.
    // 이 경우엔 fetch로 처리하기 까다로움. (form data를 리스트에서 긁어야 함)
    
    // Fallback: href가 javascript:가 아니면 리턴
    return null;
}

// 상세 페이지 HTML Fetch
async function fetchDetailPage(url) {
    try {
        const res = await fetch(url);
        return await res.text();
    } catch (e) {
        console.error(e);
        return null;
    }
}

// HTML 텍스트에서 #searchVO 폼 데이터 추출
function parseFormData(htmlText) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(htmlText, 'text/html');

    // 연장 버튼 확인 (없으면 이미 연장되었거나 대상 아님)
    // issue.md: <a href="javascript:fn_reqst('extend', '?怨')" ...>
    // 텍스트에 "연장"이 포함된 링크가 있는지 확인
    const hasExtendBtn = Array.from(doc.querySelectorAll('a')).some(a => a.textContent.includes('연장'));
    
    if (!hasExtendBtn) {
        // 버튼이 없다면 연장 대상이 아님
        return null;
    }

    // 폼 추출
    const form = doc.getElementById('searchVO');
    if (!form) return null;

    const inputs = form.querySelectorAll('input');
    const formData = new URLSearchParams();

    inputs.forEach(input => {
        if (input.name && input.value) {
            formData.append(input.name, input.value);
        }
    });

    // 연장 신청을 위한 필수 값 강제 설정 (fn_reqst('extend', '연장') 로직)
    formData.set('gbn', 'extend'); 
    
    // issue.md의 fn_reqst 로직 참조:
    // projectId, businessApply 등은 특정 조건(runAcnt 등)에서만 쓰이므로 무시 가능하거나 기본값 유지.
    
    return formData;
}

// API 호출 (연장 신청)
async function callExtendApi(formData) {
    try {
        // issue.md 참조: url: '/iim/api/updateReqState.do'
        const res = await fetch('/iim/api/updateReqState.do', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                // X-Requested-With 헤더가 필요할 수 있음 (Ajax 식별)
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: formData.toString()
        });

        const json = await res.json();
        // 성공 조건: json.result == true
        return json && json.result === true;

    } catch (e) {
        console.error(e);
        return false;
    }
}

// 페이지네이션 처리
function goToNextPage() {
    log("다음 페이지 이동 준비...");
    
    // 현재 페이지 번호 파악 (어려우면 단순히 '다음' 버튼 찾기)
    // inject.js를 통해 fn_search(nextPage) 실행이 가장 확실함.
    
    // 1. 현재 활성화된 페이지 번호 찾기
    const activePage = document.querySelector('.pagination .active') || document.querySelector('.pagination strong');
    let nextPageNum = 2;
    if (activePage) {
        nextPageNum = parseInt(activePage.textContent.trim()) + 1;
    } else {
        // 활성 페이지 못 찾으면 state나 url 파라미터 확인 (복잡하므로 1->2 가정 위험)
        // 화면의 "다음" 화살표 버튼 찾기
        const nextBtn = document.querySelector('.btn-next') || document.querySelector('a[onclick*="fn_search"]:last-child'); // 대략적
    }

    // 안전하게: onclick에 fn_search(N) 있는 것 중 현재+1 인 것 찾기
    // 혹은 inject.js에게 "현재 페이지 + 1로 이동해줘" 라고 위임할 순 없나? (현재 페이지 번호를 안다면)
    
    // 여기서는 간단히: fn_search(N) 링크들을 긁어서, 현재 페이지보다 큰 가장 작은 N을 찾음.
    const pageLinks = Array.from(document.querySelectorAll('a[onclick*="fn_search"]'));
    let targetPage = -1;
    
    // 현재 페이지 번호가 명확하지 않으므로, URL 쿼리스트링 pageIndex 확인
    const urlParams = new URLSearchParams(window.location.search);
    const currentPage = parseInt(urlParams.get('pageIndex')) || 1;
    const nextPage = currentPage + 1;
    
    // 다음 페이지 번호가 nextPage인 링크가 있는지 확인
    const hasNext = pageLinks.some(link => {
        const match = link.getAttribute('onclick').match(/fn_search\((\d+)\)/);
        return match && parseInt(match[1]) === nextPage;
    });

    if (hasNext) {
        log(`${nextPage} 페이지로 이동합니다.`);
        
        // inject.js에 페이지 이동 위임
        sendPageCommand('EXECUTE_FN_SEARCH', { pageNum: nextPage });
    } else {
        log("다음 페이지를 찾을 수 없습니다. 작업 종료.");
        isRunning = false;
        chrome.storage.local.set({ isRunning: false });
        alert(`작업 완료!\n성공: ${processedCount}건\n실패: ${failCount}건`);
    }
}
