// 팝업 UI 관리 스크립트
class PopupManager {
  constructor() {
    this.isRunning = false;
    this.stats = {
      processed: 0,
      success: 0,
      fail: 0,
      currentPage: 0,
      totalItems: 0
    };

    this.initElements();
    this.initEventListeners();
    this.loadStats();
  }

  initElements() {
    this.elements = {
      status: document.getElementById('status'),
      currentPage: document.getElementById('currentPage'),
      processedCount: document.getElementById('processedCount'),
      successCount: document.getElementById('successCount'),
      failCount: document.getElementById('failCount'),
      progressBar: document.getElementById('progressBar'),
      progressText: document.getElementById('progressText'),
      startBtn: document.getElementById('startBtn'),
      stopBtn: document.getElementById('stopBtn'),
      resetBtn: document.getElementById('resetBtn'),
      logContainer: document.getElementById('logContainer'),
      clearLogBtn: document.getElementById('clearLogBtn'),
      autoConfirm: document.getElementById('autoConfirm'),
      delayBetweenItems: document.getElementById('delayBetweenItems'),
      stopOnError: document.getElementById('stopOnError'),
      strategySelect: document.getElementById('strategySelect')
    };
  }

  initEventListeners() {
    this.elements.startBtn.addEventListener('click', () => this.startAutomation());
    this.elements.stopBtn.addEventListener('click', () => this.stopAutomation());
    this.elements.resetBtn.addEventListener('click', () => this.resetStats());
    this.elements.clearLogBtn.addEventListener('click', () => this.clearLog());

    // 설정 변경 감지
    this.elements.autoConfirm.addEventListener('change', (e) => this.saveSetting('autoConfirm', e.target.checked));
    this.elements.delayBetweenItems.addEventListener('change', (e) => this.saveSetting('delayBetweenItems', e.target.checked));
    this.elements.stopOnError.addEventListener('change', (e) => this.saveSetting('stopOnError', e.target.checked));
    this.elements.strategySelect.addEventListener('change', (e) => this.saveSetting('strategy', e.target.value));

    // 백그라운드 스크립트로부터 메시지 수신
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      this.handleMessage(message);
    });
  }

  async startAutomation() {
    // 현재 탭 가져오기
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (!tab.url.includes('data.go.kr')) {
      this.addLog('오류: 공공데이터포털 페이지에서 실행해주세요.', 'error');
      return;
    }

    this.isRunning = true;
    this.updateButtonStates();
    this.updateStatus('실행 중');
    this.addLog('자동 승인 프로세스를 시작합니다...', 'info');

    // 설정 가져오기
    const settings = {
      autoConfirm: this.elements.autoConfirm.checked,
      delayBetweenItems: this.elements.delayBetweenItems.checked,
      stopOnError: this.elements.stopOnError.checked,
      strategy: this.elements.strategySelect.value
    };

    // content script에 메시지 전송
    try {
      await chrome.tabs.sendMessage(tab.id, {
        action: 'startAutomation',
        settings: settings
      });
    } catch (error) {
      this.addLog(`오류: ${error.message}`, 'error');
      this.stopAutomation();
    }
  }

  stopAutomation() {
    this.isRunning = false;
    this.updateButtonStates();
    this.updateStatus('중지됨');
    this.addLog('자동 승인 프로세스가 중지되었습니다.', 'warning');

    // content script에 중지 메시지 전송
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        chrome.tabs.sendMessage(tabs[0].id, { action: 'stopAutomation' });
      }
    });
  }

  resetStats() {
    this.stats = {
      processed: 0,
      success: 0,
      fail: 0,
      currentPage: 0,
      totalItems: 0
    };
    this.updateStats();
    this.saveStats();
    this.updateProgress(0);
    this.updateStatus('대기 중');
    this.addLog('통계가 초기화되었습니다.', 'info');
  }

  handleMessage(message) {
    switch (message.type) {
      case 'status':
        this.updateStatus(message.status);
        break;
      case 'log':
        this.addLog(message.message, message.level || 'info');
        break;
      case 'stats':
        this.updateStatsFromMessage(message.stats);
        break;
      case 'progress':
        this.updateProgress(message.progress);
        break;
      case 'complete':
        this.onComplete(message);
        break;
      case 'error':
        this.onError(message);
        break;
    }
  }

  updateStatsFromMessage(stats) {
    if (stats.processed !== undefined) this.stats.processed = stats.processed;
    if (stats.success !== undefined) this.stats.success = stats.success;
    if (stats.fail !== undefined) this.stats.fail = stats.fail;
    if (stats.currentPage !== undefined) this.stats.currentPage = stats.currentPage;
    if (stats.totalItems !== undefined) this.stats.totalItems = stats.totalItems;

    this.updateStats();
    this.saveStats();
  }

  updateStats() {
    this.elements.processedCount.textContent = this.stats.processed;
    this.elements.successCount.textContent = this.stats.success;
    this.elements.failCount.textContent = this.stats.fail;
    this.elements.currentPage.textContent = this.stats.currentPage || '-';
  }

  updateProgress(percent) {
    this.elements.progressBar.style.width = `${percent}%`;
    this.elements.progressText.textContent = `${Math.round(percent)}%`;
  }

  updateStatus(status) {
    this.elements.status.textContent = status;
    this.elements.status.className = `value status-${status.toLowerCase().replace(' ', '-')}`;
  }

  updateButtonStates() {
    this.elements.startBtn.disabled = this.isRunning;
    this.elements.stopBtn.disabled = !this.isRunning;
  }

  addLog(message, level = 'info') {
    const logEntry = document.createElement('div');
    logEntry.className = `log-entry log-${level}`;

    const timestamp = new Date().toLocaleTimeString('ko-KR');
    logEntry.innerHTML = `
      <span class="log-time">[${timestamp}]</span>
      <span class="log-message">${this.escapeHtml(message)}</span>
    `;

    this.elements.logContainer.appendChild(logEntry);
    this.elements.logContainer.scrollTop = this.elements.logContainer.scrollHeight;

    // 로그 저장 (최근 100개만)
    this.saveLog(message, level, timestamp);
  }

  clearLog() {
    this.elements.logContainer.innerHTML = '';
    chrome.storage.local.remove('logs');
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  onComplete(message) {
    this.isRunning = false;
    this.updateButtonStates();
    this.updateStatus('완료');
    this.addLog(`모든 작업이 완료되었습니다! (성공: ${this.stats.success}, 실패: ${this.stats.fail})`, 'success');
    this.updateProgress(100);
  }

  onError(message) {
    this.addLog(`오류: ${message.error}`, 'error');
    if (this.elements.stopOnError.checked) {
      this.stopAutomation();
    }
  }

  // 저장소 관리
  async saveStats() {
    await chrome.storage.local.set({ stats: this.stats });
  }

  async loadStats() {
    const result = await chrome.storage.local.get('stats');
    if (result.stats) {
      this.stats = result.stats;
      this.updateStats();
    }

    // 로그 로드
    const logResult = await chrome.storage.local.get('logs');
    if (logResult.logs) {
      logResult.logs.forEach(log => {
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry log-${log.level}`;
        logEntry.innerHTML = `
          <span class="log-time">[${log.timestamp}]</span>
          <span class="log-message">${this.escapeHtml(log.message)}</span>
        `;
        this.elements.logContainer.appendChild(logEntry);
      });
    }

    // 설정 로드
    const settings = await chrome.storage.local.get(['autoConfirm', 'delayBetweenItems', 'stopOnError', 'strategy']);
    if (settings.autoConfirm !== undefined) this.elements.autoConfirm.checked = settings.autoConfirm;
    if (settings.delayBetweenItems !== undefined) this.elements.delayBetweenItems.checked = settings.delayBetweenItems;
    if (settings.stopOnError !== undefined) this.elements.stopOnError.checked = settings.stopOnError;
    if (settings.strategy !== undefined) this.elements.strategySelect.value = settings.strategy;
  }

  async saveLog(message, level, timestamp) {
    const result = await chrome.storage.local.get('logs');
    const logs = result.logs || [];
    logs.push({ message, level, timestamp });

    // 최근 100개만 유지
    if (logs.length > 100) {
      logs.shift();
    }

    await chrome.storage.local.set({ logs });
  }

  async saveSetting(key, value) {
    await chrome.storage.local.set({ [key]: value });
  }
}

// 팝업 로드 시 초기화
document.addEventListener('DOMContentLoaded', () => {
  new PopupManager();
});
