document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const statusText = document.getElementById('statusText');
    const logArea = document.getElementById('logArea');

    // 상태 업데이트
    function updateUI(isRunning) {
        if (isRunning) {
            startBtn.disabled = true;
            stopBtn.disabled = false;
            statusText.textContent = "실행 중 (고속 처리)";
            statusText.style.color = "green";
        } else {
            startBtn.disabled = false;
            stopBtn.disabled = true;
            statusText.textContent = "대기 중";
            statusText.style.color = "#555";
        }
    }

    // 초기 상태 로드
    chrome.storage.local.get(['isRunning', 'logs'], (data) => {
        updateUI(data.isRunning);
        if (data.logs) {
            renderLogs(data.logs);
        }
    });

    // 로그 렌더링
    function renderLogs(logs) {
        logArea.innerHTML = logs.map(log => `<div class="log-item">${log}</div>`).reverse().join('');
    }

    // 변경 감지 (로그/상태)
    chrome.storage.onChanged.addListener((changes, area) => {
        if (area === 'local') {
            if (changes.isRunning) {
                updateUI(changes.isRunning.newValue);
            }
            if (changes.logs) {
                renderLogs(changes.logs.newValue);
            }
        }
    });

    // 버튼 이벤트
    startBtn.addEventListener('click', () => {
        // 활성 탭으로 메시지 전송
        chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
            if (tabs[0]) {
                chrome.tabs.sendMessage(tabs[0].id, { action: 'START' }, (response) => {
                    if (chrome.runtime.lastError) {
                        alert("페이지를 새로고침하거나 데이터 목록 페이지로 이동해주세요.");
                    }
                });
            }
        });
    });

    stopBtn.addEventListener('click', () => {
        chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
            if (tabs[0]) {
                chrome.tabs.sendMessage(tabs[0].id, { action: 'STOP' });
            }
        });
    });
});