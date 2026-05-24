// 고속 연장기 Background Service Worker

// 설치 시 초기화
chrome.runtime.onInstalled.addListener(() => {
    chrome.storage.local.set({
      isRunning: false,
      logs: []
    });
});
  
// 메시지 핸들러
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'LOG') {
        saveLog(request.message);
    }
});
  
function saveLog(message) {
    chrome.storage.local.get(['logs'], (data) => {
        const logs = data.logs || [];
        const time = new Date().toLocaleTimeString();
        logs.push(`[${time}] ${message}`);
        if (logs.length > 100) logs.shift(); // 로그 100개 유지
        chrome.storage.local.set({ logs: logs });
    });
}