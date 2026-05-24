// Background Service Worker
// 익스텐션 설치 및 업데이트 이벤트 처리

chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    console.log('공공데이터포털 자동 승인 익스텐션이 설치되었습니다.');

    // 초기 설정
    chrome.storage.local.set({
      autoConfirm: true,
      delayBetweenItems: true,
      stopOnError: false,
      stats: {
        processed: 0,
        success: 0,
        fail: 0,
        currentPage: 0,
        totalItems: 0
      }
    });
  } else if (details.reason === 'update') {
    console.log('공공데이터포털 자동 승인 익스텐션이 업데이트되었습니다.');
  }
});

// 메시지 수신 처리
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // CSP 우회를 위한 메인 월드 스크립트 실행
  if (message.action === 'executeInMainWorld') {
    chrome.scripting.executeScript({
      target: { tabId: sender.tab.id },
      world: 'MAIN',
      func: (code) => {
        // 페이지 컨텍스트에서 직접 실행
        eval(code);
      },
      args: [message.code]
    })
    .then(() => {
      sendResponse({ success: true });
    })
    .catch((error) => {
      console.error('Script execution error:', error);
      sendResponse({ success: false, error: error.message });
    });
    return true; // 비동기 응답을 위해 true 반환
  }

  // Content script로부터 메시지를 받아 popup으로 전달
  // chrome.runtime.sendMessage는 팝업과 백그라운드 모두 수신하므로
  // 여기서 다시 보내면 팝업에서 중복 수신됨. 따라서 로깅만 하거나 비워둠.

  sendResponse({ success: true });
  return true;
});

// 탭 업데이트 감지
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  // 페이지 로딩 완료 시
  if (changeInfo.status === 'complete' && tab.url && tab.url.includes('data.go.kr')) {
    console.log('공공데이터포털 페이지 로드 완료:', tab.url);
  }
});

// 컨텍스트 메뉴 추가
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'startAutomation',
    title: '자동 승인 시작',
    contexts: ['page'],
    documentUrlPatterns: ['https://www.data.go.kr/*']
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === 'startAutomation') {
    // Content script에 메시지 전송
    chrome.tabs.sendMessage(tab.id, {
      action: 'startAutomation',
      settings: {
        autoConfirm: true,
        delayBetweenItems: true,
        stopOnError: false
      }
    });
  }
});

console.log('공공데이터포털 자동 승인 Background Service Worker 실행 중...');