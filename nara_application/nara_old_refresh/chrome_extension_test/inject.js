// 페이지 컨텍스트(MAIN World)에서 실행되는 스크립트
// content.js로부터 명령을 받아 페이지 내 함수(fn_search 등)를 실행

console.log("[Nara Refresh] Page Script Loaded");

// 1. Alert/Confirm 오버라이드 설정
function setupOverrides() {
    window.confirm = function(msg) {
        console.log('[Page] Auto-confirming:', msg);
        return true; 
    };
    window.alert = function(msg) {
        console.log('[Page] Auto-alert acknowledged:', msg);
        return true;
    };
    console.log("[Page] Alert/Confirm overridden.");
}

// 2. Mock 함수 설정 (안전장치)
function setupMocks() {
    if (typeof window.loadingStart === 'undefined') {
        window.loadingStart = function() { console.log('[Page] Mock loadingStart called'); };
    }
    if (typeof window.loadingStop === 'undefined') {
        window.loadingStop = function() { console.log('[Page] Mock loadingStop called'); };
    }
}

// 초기화 완료 신호 전송
window.dispatchEvent(new CustomEvent('NARA_INJECT_READY'));
console.log("[Page] inject.js ready and listening.");

// 3. 이벤트 리스너: content.js로부터 명령 수신
window.addEventListener('NARA_EXTENSION_CMD', function(e) {
    const data = e.detail;
    console.log("[Page] Command received:", data);

    // 로그 전송 헬퍼
    function sendLogToExtension(msg) {
        window.dispatchEvent(new CustomEvent('NARA_PAGE_LOG', { detail: msg }));
    }

    if (data.action === 'EXECUTE_FN_SEARCH') {
        const pageNum = data.pageNum;
        if (typeof window.fn_search === 'function') {
            try {
                window.fn_search(pageNum);
                sendLogToExtension(`[Page] fn_search(${pageNum}) executed.`);
            } catch (err) {
                console.error(err);
                sendLogToExtension(`[Page] fn_search execution error: ${err.message}`);
            }
        } else {
            console.error("[Page] fn_search not found!");
            sendLogToExtension("[Page] Error: fn_search function not found in window scope.");
        }
    } else if (data.action === 'EXECUTE_FN_REQST') {
        // 1. Alert/Confirm 오버라이드 (실행 직전 재설정)
        setupOverrides();
        setupMocks();

        // 2. jQuery 확인
        if (typeof window.$ === 'undefined') {
            console.error("[Page] jQuery not loaded yet.");
            sendLogToExtension("[Page] Error: jQuery not found. Cannot execute fn_reqst.");
            return;
        }

        // 3. gbn 값 설정
        const gbnInput = document.getElementById('gbn');
        if (gbnInput) {
            gbnInput.value = 'extend';
            sendLogToExtension("[Page] #gbn value set to 'extend'");
        }

        // 4. fn_reqst 실행
        if (typeof window.fn_reqst === 'function') {
            try {
                sendLogToExtension("[Page] Invoking fn_reqst('extend', '연장')...");
                window.fn_reqst('extend', '연장');
                sendLogToExtension("[Page] fn_reqst executed. Waiting for ajax...");
            } catch (err) {
                console.error(err);
                sendLogToExtension(`[Page] fn_reqst error: ${err.message}`);
            }
        } else {
            console.error("[Page] fn_reqst not found!");
            sendLogToExtension("[Page] Error: fn_reqst function not found.");
        }
    } else if (data.action === 'EXECUTE_SCRIPT_STRING') {
        try {
            const code = data.code.replace(/^\s*javascript:/i, '');
            sendLogToExtension(`[Page] Executing script: ${code}`);
            
            // new Function으로 실행
            new Function(code)(); 
            sendLogToExtension("[Page] Script execution successful (no return value check).");
        } catch (err) {
            console.error("[Page] Script execution failed:", err);
            sendLogToExtension(`[Page] Script execution failed: ${err.message}`);
        }
    } else if (data.action === 'EXECUTE_CLICK_BY_INDEX') {
        const index = data.index;
        const links = document.querySelectorAll('div.title-area a');
        if (links && links[index]) {
            const link = links[index];
            sendLogToExtension(`[Page] Clicking link at index ${index} (Text: ${link.textContent.trim()})`);
            
            // target="_blank" 제거 (여기서도 수행)
            if (link.getAttribute('target') === '_blank') {
                link.removeAttribute('target');
            }

            // Native Click Trigger
            link.click(); 
        } else {
            sendLogToExtension(`[Page] Error: Link at index ${index} not found.`);
        }
    }
});
