// 공공데이터포털 자동 승인 Content Script (Multi-Strategy)
class DataPortalAutomation {
  constructor() {
    this.listUrl = 'https://www.data.go.kr/iim/api/selectAcountList.do';
    this.initMessageListener();
    this.checkAutoRun();
  }

  initMessageListener() {
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      if (message.action === 'startAutomation') {
        this.startAutomation(message.settings);
        sendResponse({ success: true });
      } else if (message.action === 'stopAutomation') {
        this.stopAutomation();
        sendResponse({ success: true });
      }
      return true;
    });
  }

  async checkAutoRun() {
    const state = await this.loadState('automationState');
    if (state === 'RUNNING') {
      console.log('Automation is RUNNING. Resuming...');
      this.runLoop();
    }
  }

  async startAutomation(settings) {
    await this.saveState('automationState', 'RUNNING');
    await this.saveState('settings', settings);
    
    // 초기 통계
    await this.saveState('stats', {
          processed: 0,
          success: 0,
          fail: 0,
          currentPage: 0,
          totalItems: 0
    });

    if (settings.strategy === 'sequential') {
        await this.saveState('pageIndex', 1);
        await this.saveState('itemIndex', 0);
    }
    
    let strategyName = '끝번부터 갱신';
    if (settings.strategy === 'sequential') strategyName = '순차 갱신';

    this.sendLog(`자동 승인을 시작합니다. 전략: ${strategyName}`, 'info');
    this.runLoop();
  }

  async stopAutomation() {
    await this.saveState('automationState', 'STOPPED');
    this.sendStatus('중지됨');
    this.sendLog('자동 승인이 중지되었습니다.', 'warning');
  }

  async runLoop() {
    this.sendStatus('실행 중');
    const settings = await this.loadState('settings') || {};

    if (window.location.href.includes('selectAcountList.do')) {
      if (settings.strategy === 'sequential') {
        await this.runStrategySequential();
      } else {
        await this.runStrategyLastItem();
      }
    } else {
      await this.handleDetailPage();
    }
  }

  // --- Strategy: Sequential ---
  async runStrategySequential() {
    await this.waitForPageLoad();
    
    // 목록 아이템이 로드될 때까지 대기 (최대 10초)
    await this.waitForListItems();

    if (await this.checkLoginStatus() === false) {
        this.sendLog('로그인이 필요합니다.', 'error');
        this.stopAutomation();
        return;
    }

    // 통계 및 위치 정보 로드
    let stats = await this.loadState('stats') || { processed: 0, success: 0, fail: 0, currentPage: 0, totalItems: 0 };
    let totalItems = await this.loadState('totalItems');
    if (!totalItems) {
        totalItems = this.parseTotalItems();
        if (totalItems > 0) await this.saveState('totalItems', totalItems);
    }

    let targetPage = await this.loadState('pageIndex') || 1;
    let targetItemIndex = await this.loadState('itemIndex') || 0;
    const currentPage = this.parseCurrentPage();

    if (totalItems > 0 && stats.processed >= totalItems) {
        this.sendLog('모든 문서의 갱신이 완료되었습니다.', 'success');
        this.sendMessage({ type: 'complete' });
        this.stopAutomation();
        return;
    }

    // 페이지 이동 필요 확인
    if (currentPage !== targetPage) {
        this.sendLog(`${targetPage}페이지로 이동합니다... (현재: ${currentPage})`, 'info');
        await this.navigateToPage(targetPage);
        return;
    }

    // 아이템 찾기
    const titleLinks = document.querySelectorAll('div.title-area a');
    if (titleLinks.length === 0) {
        this.sendLog('항목을 찾을 수 없습니다.', 'warning');
        this.stopAutomation();
        return;
    }

    // 페이지 넘김 체크 (아이템 인덱스가 현재 페이지 개수를 초과하면 다음 페이지로)
    if (targetItemIndex >= titleLinks.length) {
        const nextPage = targetPage + 1;
        // 마지막 페이지 체크 로직이 필요하지만, totalItems 기반으로 종료조건이 있으므로 계속 진행
        this.sendLog(`현재 페이지(${targetPage}) 완료. 다음 페이지(${nextPage})로 이동합니다.`, 'info');
        
        await this.saveState('pageIndex', nextPage);
        await this.saveState('itemIndex', 0);
        await this.navigateToPage(nextPage);
        return;
    }

    // 항목 처리
    const link = titleLinks[targetItemIndex];
    this.sendLog(`[${stats.processed + 1}/${totalItems || '?'}] ${targetPage}페이지 ${targetItemIndex + 1}번째 항목 처리 중...`, 'info');
    
    this.clickLink(link);
  }

  // --- Strategy: Last Item ---
  async runStrategyLastItem() {
    await this.waitForPageLoad();
    await this.delay(1000);

    if (await this.checkLoginStatus() === false) {
        this.sendLog('로그인이 필요합니다.', 'error');
        this.stopAutomation();
        return;
    }

    let totalItems = await this.loadState('totalItems');
    if (!totalItems) {
        totalItems = this.parseTotalItems();
        if (totalItems > 0) await this.saveState('totalItems', totalItems);
    }

    const lastPage = Math.ceil(totalItems / 10);
    const currentPage = this.parseCurrentPage();
    await this.saveState('lastPage', lastPage);
    
    const stats = await this.loadState('stats');
    if (totalItems > 0 && stats.processed >= totalItems) {
        this.sendLog('모든 문서의 갱신이 완료되었습니다.', 'success');
        this.sendMessage({ type: 'complete' });
        this.stopAutomation();
        return;
    }

    if (currentPage !== lastPage) {
        this.sendLog(`마지막 페이지(${lastPage})로 이동합니다...`, 'info');
        await this.navigateToPage(lastPage);
        return;
    }

    const titleLinks = document.querySelectorAll('div.title-area a');
    if (titleLinks.length === 0) {
        this.stopAutomation();
        return;
    }

    const lastItemIndex = titleLinks.length - 1;
    const link = titleLinks[lastItemIndex];
    this.sendLog(`[${stats.processed + 1}/${totalItems || '?'}] 마지막 항목 처리 중...`, 'info');

    this.clickLink(link);
  }

  // --- Detail Page Logic ---
  async handleDetailPage() {
    this.sendLog('상세 페이지 진입.', 'info');

    const settings = await this.loadState('settings') || {};
    this.settings = settings;

    // 페이지 로드 완료 대기
    await this.waitForPageLoad();

    // 동적 컨텐츠 로드를 위한 추가 대기
    await this.delay(1000);

    this.sendLog('문서 갱신 시작...', 'info');

    // 복귀할 페이지 (패치 적용 시 pageIndex 자동 처리되므로 참조용)
    let returnPage = 1;
    if (settings.strategy === 'sequential') {
        returnPage = await this.loadState('pageIndex') || 1;
    } else {
        returnPage = await this.loadState('lastPage') || 1;
    }

    // 작업 수행
    const success = await this.clickExtendButton(returnPage);
    
    const stats = await this.loadState('stats');
    stats.processed++;
    if (success) {
        stats.success++;
        this.sendLog('갱신 성공', 'success');
        
        // 순차 전략일 경우 다음 아이템 인덱스 증가
        if (settings.strategy === 'sequential') {
            const currentItemIndex = await this.loadState('itemIndex') || 0;
            await this.saveState('itemIndex', currentItemIndex + 1);
        }
    } else {
        stats.fail++;
        this.sendLog('갱신 실패', 'error');
        // 실패 시에도 일단 다음으로 넘어가야 무한루프 방지 (옵션에 따라 다름)
        if (!settings.stopOnError && settings.strategy === 'sequential') {
             const currentItemIndex = await this.loadState('itemIndex') || 0;
             await this.saveState('itemIndex', currentItemIndex + 1);
        }
    }
    await this.saveState('stats', stats);
    this.sendStats(stats);

    if (!success && settings.stopOnError) {
        this.stopAutomation();
        return;
    }

    if (!window.location.href.includes('selectAcountList.do')) {
        this.sendLog('목록으로 돌아갑니다...', 'info');
        window.location.href = this.listUrl;
    }
  }

  // --- Actions ---

  async clickExtendButton(targetPageIndex) {
    try {
      if (this.settings && this.settings.autoConfirm) {
        const overrideScript = `
          window.originalConfirm = window.confirm;
          window.originalAlert = window.alert;
          window.confirm = function(msg) {
            if (msg.includes('신청') || msg.includes('재신청')) return true;
            return window.originalConfirm(msg);
          };
          window.alert = function(msg) { console.log('Alert blocked:', msg); };
        `;
        await this.executeInMainWorld(overrideScript);
      }

      // -----------------------------------------------------------------------
      // [FIX] Apply function overrides to fix page redirect (Using Form Submit)
      // -----------------------------------------------------------------------
      const patchScript = `
        // 공통 성공 콜백 로직: location.replace 대신 폼 서밋 사용
        function handleSuccessFix(msg) {
            alert(msg);
            // $("#searchVO").attr("action", "/iim/api/selectAcountList.do").submit(); 
            // 위 코드가 fn_list()와 유사한 동작을 함. pageIndex 등 기존 검색조건 유지.
            var form = $("#searchVO");
            if(form.length > 0) {
                form.attr("action", "/iim/api/selectAcountList.do");
                form.submit();
            } else {
                // 폼이 없으면 (예외상황) fallback
                location.replace("/iim/api/selectAcountList.do");
            }
        }

        // fn_reqst 오버라이드
        window.fn_reqst = function(gbn, txt){ 
            $("#gbn").val(gbn);
            if(gbn=="runAcnt" || gbn=="change"){ 
                var url = ( gbn=="runAcnt" ? "/iim/api/selectRunAcountRequestForm.do" :
                ( ("STCD01"=="STCD01") ? "/iim/api/selectDevAcountRequestForm.do" :  "/iim/api/selectRunAcountRequestForm.do" ) );
                if ((gbn == "runAcnt" || gbn == "change") && false) {
                    let projectId = 'BUSINESS__';
                    $("#projectIds").val(projectId);
                    $("#businessApply").val("true");
                }
                $("#searchVO").attr("onSubmit","");
                $("#searchVO").attr("action", url).submit();
            }else if(gbn === "cancle"){
                if(confirm("활용신청을 취소하시겠습니까?")){
                    $("#loader").show();
                    $.ajax({
                        type:"POST",
                        url: '/iim/api/updateRunAcountRequest.json',
                        data : $("#searchVO").serialize(),
                        dataType : "json",
                        success: function(resultMap){
                            $("#loader").hide();
                            if(resultMap.result==true){
                                handleSuccessFix("취소되었습니다."); // 메시지 임의 설정
                            }else{
                                alert("신청취소에 실패하였습니다. 잠시후 시도해 주세요.");
                            }
                        },
                        error: function(xhr, status, error) {
                            $("#loader").hide();
                            alert("신청취소에 실패하였습니다. 잠시후 시도해 주세요.");
                        }
                    });
                }
            }else{
                if(txt == '인증키 재발급') {
                    alert("인증키 재발급 받을 시에 기존에 활용신청한 API에 대한 인증키도 모두 변경 됩니다.")
                }
                if (gbn != "runAcnt" && gbn != "change" && gbn != "cancle" && false) {
                    let projectId = 'BUSINESS__';
                    $("#projectIds").val(projectId);
                    $("#businessApply").val("true");
                }
                if(confirm(txt + "신청하시겠습니까?")){ 
                    $("#loader").show();
                    $.ajax({
                        type:"POST",
                        url: '/iim/api/updateReqState.do',
                        data : $("#searchVO").serialize(),
                        dataType : "json",
                        success: function(json){
                            $("#loader").hide();
                            if(json.result==true){
                                handleSuccessFix(txt+"되었습니다.");
                            }else{
                                alert(txt+"처리시 문제가 발생했습니다.");
                            }
                        },
                        error: function(xhr, status, error) {
                            $("#loader").hide();
                            alert("저장이 실패하였습니다.");
                        }
                    });
                }
            }
        };

        // fn_reCreateToken 오버라이드
        window.fn_reCreateToken = function() {
            if(confirm('재신청을 하시겠습니까?')) {
                $("#loader").show();
                $.ajax({
                    type:"POST",
                    url: '/iim/api/reCreateToken.do',
                    data : $("#searchVO").serialize(),
                    dataType : "json",
                    success: function(json){
                        $("#loader").hide();
                        if(json.result) {
                            handleSuccessFix("재신청되었습니다."); // 메시지 임의 설정 (원래는 alert 안떴을수도 있음)
                        } else {
                            alert('재신청에 실패했습니다.');
                        }
                    },
                    error: function(xhr, status, error) {
                        $("#loader").hide();
                        alert("저장이 실패하였습니다.");
                    }
                });
            }
        };
      `;
      await this.executeInMainWorld(patchScript);

      // Inject Page Index (Still useful to ensure the form has the value before submit)
      if (targetPageIndex) {
          const injectPageScript = `
            const pageInput = document.querySelector('input[name="pageIndex"]');
            if (pageInput) {
                pageInput.value = '${targetPageIndex}';
            } else {
                const form = document.querySelector('#searchVO');
                if (form) {
                    const input = document.createElement('input');
                    input.type = 'hidden';
                    input.name = 'pageIndex';
                    input.value = '${targetPageIndex}';
                    form.appendChild(input);
                }
            }
          `;
          await this.executeInMainWorld(injectPageScript);
      }
      
      const gbnInput = document.getElementById('gbn');
      if (gbnInput) gbnInput.value = 'extend';


      let reCreateBtn = null;
      let extendBtn = null;
      const startTime = Date.now();
      
      while (Date.now() - startTime < 5000) {
        reCreateBtn = document.querySelector('a[href*="fn_reCreateToken"]') || 
                      findElementByText('a', '재신청');
        
        extendBtn = document.querySelector('a[href*="fn_reqst"]') ||
                    findElementByText('a', '연장') ||
                    findElementByText('button', '연장');

        if (reCreateBtn || extendBtn) break;
        await this.delay(500);
      }

      let actionSuccess = false;

      if (reCreateBtn) {
        this.sendLog('재신청 진행...', 'info');
        await this.executeInMainWorld(`
           if(typeof fn_reCreateToken === 'function') fn_reCreateToken(); 
           else {
               const btn = document.querySelector('a[href*="fn_reCreateToken"]'); 
               if(btn) btn.click();
           }
        `);
        await this.delay(2000); 
        actionSuccess = true; 
        
      } else if (extendBtn) {
        this.sendLog('연장 진행...', 'info');
        await this.executeInMainWorld(`
           if(typeof fn_reqst === 'function') fn_reqst('extend', '연장'); 
           else {
               const btn = document.querySelector('a[href*="fn_reqst"]');
               if(btn) btn.click();
           }
        `);
        await this.delay(2000);
        actionSuccess = true;

      } else {
        const content = document.body.textContent;
        if (content.includes('연장되었습니다') || content.includes('신청되었습니다')) {
            return true;
        }
        return false;
      }

      if (this.settings && this.settings.autoConfirm) {
        await this.executeInMainWorld(`
          if (window.originalConfirm) window.confirm = window.originalConfirm;
          if (window.originalAlert) window.alert = window.originalAlert;
        `);
      }

      return actionSuccess;

    } catch (error) {
      this.sendLog(`오류: ${error.message}`, 'error');
      return false;
    }
  }

  // --- Helpers ---
  
  parseTotalItems() {
      const totalText = document.body.innerText.match(/총\s*(\d+)건/);
      if (totalText) return parseInt(totalText[1]);
      
      const infoData = document.querySelector('.info-data');
      if (infoData) {
          const match = infoData.textContent.match(/(\d+)/);
          if (match) return parseInt(match[1]);
      }
      return 44; 
  }

  parseCurrentPage() {
      const activePage = document.querySelector('.pagination .active') || document.querySelector('nav strong');
      if (activePage) return parseInt(activePage.textContent.trim());
      
      const pageInput = document.querySelector('input[name="pageIndex"]');
      if (pageInput) return parseInt(pageInput.value);
      
      return 1;
  }

  async checkLoginStatus() {
    const indicators = ['로그아웃', '마이페이지'];
    const text = document.body.innerText;
    return indicators.some(i => text.includes(i));
  }

  async navigateToPage(pageNum) {
    await this.executeInMainWorld(`if (typeof fn_search === 'function') fn_search(${pageNum});`);
    await this.delay(2000);
  }
  
  async clickLink(link) {
    const href = link.getAttribute('href');
    const onclick = link.getAttribute('onclick');

    try {
        if (href && href.startsWith('javascript:')) {
             const js = href.replace('javascript:', '');
             await this.executeInMainWorld(js);
        } else if (onclick) {
             await this.executeInMainWorld(onclick);
        } else {
             link.click();
        }
    } catch (e) {
        this.sendLog(`이동 실패: ${e.message}`, 'error');
    }
  }

  async executeInMainWorld(code) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ action: 'executeInMainWorld', code }, () => resolve());
    });
  }

  async saveState(key, value) { await chrome.storage.local.set({ [key]: value }); }
  async loadState(key) { const res = await chrome.storage.local.get(key); return res[key]; }

  sendMessage(msg) { chrome.runtime.sendMessage(msg); }
  sendLog(msg, level='info') { this.sendMessage({ type: 'log', message: msg, level }); }
  sendStatus(status) { this.sendMessage({ type: 'status', status }); }
  sendStats(stats) { this.sendMessage({ type: 'stats', stats }); }
  
  async delay(ms) { return new Promise(r => setTimeout(r, ms)); }
  async waitForListItems() {
    const startTime = Date.now();
    while (Date.now() - startTime < 10000) {
       const items = document.querySelectorAll('div.title-area a');
       if (items.length > 0) return true;
       await this.delay(200);
    }
    return false;
  }

  async waitForPageLoad() {
    if (document.readyState === 'complete') return;
    return new Promise(r => window.addEventListener('load', r, { once: true }));
  }
}

function findElementByText(tag, text) {
  const elements = document.getElementsByTagName(tag);
  for (let el of elements) {
    if (el.textContent.includes(text)) return el;
  }
  return null;
}

new DataPortalAutomation();
