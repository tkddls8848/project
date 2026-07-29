const records = [
  { id: '2024-12-31-01', date: '2024-12-31', agency: '행정안전부', category: '고시', title: '2025년 지방자치단체 예산편성 운영기준 개정 알림', body: ['행정안전부고시 제2024-00호', '지방재정법 및 관계 법령에 따라 2025년도 지방자치단체 예산편성 운영기준을 다음과 같이 개정하여 알립니다.', '## 주요 내용', '이번 개정은 지방재정 운용의 투명성과 주민 접근성을 높이기 위한 기준을 담고 있습니다. 세부 기준은 첨부된 원문 공고에서 확인할 수 있습니다.'] },
  { id: '2024-12-30-02', date: '2024-12-30', agency: '국토교통부', category: '공고', title: '공공주택 건설사업계획 승인에 관한 공고', body: ['국토교통부공고 제2024-000호', '공공주택 특별법에 따라 공공주택 건설사업계획을 승인하였기에 그 내용을 공고합니다.', '## 사업 개요', '사업 위치, 규모 및 사업시행자에 관한 사항은 원문 파일의 사업계획을 따릅니다.'] },
  { id: '2024-12-27-03', date: '2024-12-27', agency: '환경부', category: '고시', title: '생태·자연도 정기고시', body: ['환경부고시 제2024-000호', '자연환경보전법에 따른 생태·자연도를 정기 고시합니다.', '## 고시의 효력', '고시된 도면 및 관련 자료는 관할 기관에서 열람할 수 있습니다.'] },
  { id: '2024-12-23-04', date: '2024-12-23', agency: '교육부', category: '훈령', title: '대학설립·운영 규정 일부개정령안 입법예고', body: ['교육부공고 제2024-000호', '대학설립·운영 규정 일부개정령안을 마련하여 국민에게 미리 알리고 의견을 듣고자 합니다.', '## 의견 제출', '개정안에 의견이 있는 기관·단체 또는 개인은 정해진 기한 내 의견서를 제출할 수 있습니다.'] },
  { id: '2024-12-18-05', date: '2024-12-18', agency: '보건복지부', category: '고시', title: '건강보험 요양급여의 기준에 관한 규칙 일부개정', body: ['보건복지부고시 제2024-000호', '국민건강보험법 관계 규정에 따라 요양급여 기준의 일부를 개정합니다.', '## 시행일', '이 고시는 공포한 날부터 시행합니다.'] },
  { id: '2024-11-29-06', date: '2024-11-29', agency: '산업통상자원부', category: '공고', title: '산업기술혁신사업 통합 시행계획 공고', body: ['산업통상자원부공고 제2024-000호', '산업기술혁신을 위한 사업의 지원 내용과 절차를 다음과 같이 안내합니다.', '## 지원 분야', '세부 사업별 지원 규모와 신청 자격은 공고문을 참고하여 주시기 바랍니다.'] },
  { id: '2024-10-17-07', date: '2024-10-17', agency: '행정안전부', category: '공고', title: '국민참여예산사업 제안 접수 안내', body: ['행정안전부공고 제2024-000호', '국민의 목소리를 예산에 반영하기 위한 제안 접수 절차를 안내합니다.', '## 참여 방법', '온라인 시스템을 통해 누구나 제안할 수 있으며, 심사를 거쳐 다음 연도 사업에 반영됩니다.'] },
  { id: '2024-08-05-08', date: '2024-08-05', agency: '국토교통부', category: '고시', title: '도로구역 결정 및 지형도면 고시', body: ['국토교통부고시 제2024-000호', '도로법에 따라 도로구역을 결정하고 지형도면을 고시합니다.', '## 열람', '관계 도서는 관계 행정기관에서 일반인이 열람할 수 있습니다.'] },
  { id: '2024-06-12-09', date: '2024-06-12', agency: '법무부', category: '령', title: '출입국관리법 시행규칙 일부개정령', body: ['법무부령 제000호', '출입국관리법 시행규칙 일부를 다음과 같이 개정합니다.', '## 부칙', '이 규칙은 공포한 날부터 시행합니다.'] },
  { id: '2024-03-04-10', date: '2024-03-04', agency: '환경부', category: '공고', title: '국가 기후위기 적응대책 세부시행계획', body: ['환경부공고 제2024-000호', '국가 기후위기 적응대책의 세부시행계획을 수립하여 알립니다.', '## 추진 방향', '기후위기 영향을 줄이고 적응 역량을 높이기 위한 분야별 과제를 담고 있습니다.'] }
];
const monthly = [{label:'1월',n:14},{label:'2월',n:23},{label:'3월',n:18},{label:'4월',n:31},{label:'5월',n:27},{label:'6월',n:20},{label:'7월',n:36},{label:'8월',n:17},{label:'9월',n:29},{label:'10월',n:25},{label:'11월',n:42},{label:'12월',n:48}];
const $ = (s) => document.querySelector(s);
let activeAgency = '', activeDate = '', order = 'new', currentId = null;
const agencies = [...new Set(records.map(r => r.agency))].sort((a,b) => a.localeCompare(b,'ko'));
let savedIds = new Set(JSON.parse(localStorage.getItem('nara-saved-records') || '[]'));

function initialize() {
  $('#heroStats').innerHTML = `<div><strong>${records.length}</strong><span>예시 기록</span></div><div><strong>${agencies.length}</strong><span>발행 기관</span></div><div><strong>2024</strong><span>수록 연도</span></div>`;
  $('#agencyTotal').textContent = agencies.length;
  $('#dateFilter').innerHTML += '<option value="2024-12">2024년 12월</option><option value="2024-11">2024년 11월</option><option value="2024-10">2024년 10월</option><option value="2024-08">2024년 8월</option><option value="2024-06">2024년 6월</option><option value="2024-03">2024년 3월</option>';
  $('#agencyFilter').innerHTML += agencies.map(a => `<option>${a}</option>`).join('');
  $('#agencyList').innerHTML = `<button class="agency-button selected" data-agency="">전체 기관 <span>${records.length}</span></button>` + agencies.map(a => `<button class="agency-button" data-agency="${a}">${a}<span>${records.filter(r => r.agency === a).length}</span></button>`).join('');
  const max = Math.max(...monthly.map(m => m.n));
  $('#monthChart').innerHTML = monthly.map((m,i) => `<button class="month-bar" style="height:${Math.round(m.n/max*100)}%" data-month="2024-${String(i+1).padStart(2,'0')}"><span>${m.label} · ${m.n}건</span></button>`).join('');
  render();
}
function filteredRecords() {
  const term = $('#searchInput').value.trim().toLowerCase();
  return records.filter(r => (!activeAgency || r.agency === activeAgency) && (!activeDate || r.date.startsWith(activeDate)) && (!term || `${r.title} ${r.agency} ${r.category} ${r.body.join(' ')}`.toLowerCase().includes(term))).sort((a,b) => order === 'new' ? b.date.localeCompare(a.date) : a.date.localeCompare(b.date));
}
function render() {
  const result = filteredRecords();
  $('#recordCount').textContent = `${records.length} records in demo archive`;
  $('#resultSummary').textContent = `${result.length}개의 기록`;
  $('#recordList').innerHTML = result.length ? result.map(r => `<article class="record-item" data-id="${r.id}" role="button" tabindex="0"><time class="record-date">${r.date.replaceAll('-','. ')}</time><span><span class="record-agency">${r.agency} · ${r.category}</span><span class="record-title">${highlight(r.title)}</span></span><button class="record-save ${savedIds.has(r.id) ? 'saved' : ''}" data-save="${r.id}" aria-label="${savedIds.has(r.id) ? '저장 취소' : '기록 저장'}">${savedIds.has(r.id) ? '★' : '☆'}</button></article>`).join('') : '<div class="empty">조건에 맞는 기록이 없습니다.<br />다른 검색어로 다시 찾아보세요.</div>';
  const leadingAgency = result.length ? result.reduce((counts, r) => ({ ...counts, [r.agency]: (counts[r.agency] || 0) + 1 }), {}) : {};
  const leading = Object.entries(leadingAgency).sort((a,b) => b[1] - a[1])[0];
  $('#exploreInsight').innerHTML = result.length ? `<strong>탐색 메모</strong><span>현재 결과는 ${leading?.[0]}의 기록이 ${leading?.[1]}건으로 가장 많습니다. 원문을 열어 발행일·기관·근거를 함께 확인하세요.</span>` : `<strong>탐색 메모</strong><span>검색 조건을 바꿔 다른 정책 기록을 찾아보세요.</span>`;
  updateSavedUI();
  document.querySelectorAll('.agency-button').forEach(b => b.classList.toggle('selected', b.dataset.agency === activeAgency));
}
function highlight(text) { const term = $('#searchInput').value.trim(); return term ? text.replace(new RegExp(`(${term.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')})`,'ig'), '<mark>$1</mark>') : text; }
function openReader(id) { const r = records.find(x => x.id === id); if (!r) return; currentId = id; $('#documentMeta').textContent = `${r.agency}  /  ${r.category}  /  ${r.date.replaceAll('-','. ')}`; $('#documentTitle').textContent = r.title; $('#documentBody').innerHTML = r.body.map(line => line.startsWith('## ') ? `<h2>${line.slice(3)}</h2>` : `<p>${line}</p>`).join(''); $('#sourceLink').href = `https://www.gwanbo.go.kr/`; $('#readerDialog').showModal(); history.replaceState(null,'',`#record-${id}`); }
function changeReader(delta) { const list = filteredRecords(); let i = list.findIndex(r => r.id === currentId); i = (i + delta + list.length) % list.length; openReader(list[i].id); }
function updateSavedUI() { $('#savedCount').textContent = savedIds.size; }
function toggleSaved(id) { savedIds.has(id) ? savedIds.delete(id) : savedIds.add(id); localStorage.setItem('nara-saved-records', JSON.stringify([...savedIds])); render(); renderSavedList(); }
function renderSavedList() { const saved = records.filter(r => savedIds.has(r.id)); $('#savedList').innerHTML = saved.length ? saved.map(r => `<div class="saved-item"><time class="saved-date">${r.date.replaceAll('-','. ')}</time><button data-open-saved="${r.id}"><span class="record-agency">${r.agency}</span><span class="saved-title">${r.title}</span></button><button class="saved-remove" data-remove-saved="${r.id}">제거</button></div>`).join('') : '<div class="saved-empty">아직 저장한 기록이 없습니다.<br />목록의 ☆ 버튼으로 관심 기록을 모아 보세요.</div>'; }

$('#searchInput').addEventListener('input', render);
$('#dateFilter').addEventListener('change', e => { activeDate = e.target.value; render(); });
$('#agencyFilter').addEventListener('change', e => { activeAgency = e.target.value; render(); });
$('#agencyList').addEventListener('click', e => { const b = e.target.closest('[data-agency]'); if (!b) return; activeAgency = b.dataset.agency; $('#agencyFilter').value = activeAgency; render(); });
$('#monthChart').addEventListener('click', e => { const b = e.target.closest('[data-month]'); if (!b) return; activeDate = b.dataset.month; $('#dateFilter').value = activeDate; document.querySelectorAll('.month-bar').forEach(x => x.classList.toggle('active',x === b)); document.querySelector('#explore').scrollIntoView({behavior:'smooth'}); render(); });
$('#recordList').addEventListener('click', e => { const save = e.target.closest('[data-save]'); if (save) { e.preventDefault(); e.stopPropagation(); toggleSaved(save.dataset.save); return; } const b = e.target.closest('[data-id]'); if (b) openReader(b.dataset.id); });
$('#recordList').addEventListener('keydown', e => { const item = e.target.closest('.record-item'); if (item && ['Enter', ' '].includes(e.key)) { e.preventDefault(); openReader(item.dataset.id); } });
$('#sortButton').addEventListener('click', e => { order = order === 'new' ? 'old' : 'new'; e.currentTarget.textContent = order === 'new' ? '최신순 ↓' : '오래된순 ↑'; render(); });
$('#resetButton').addEventListener('click', () => { activeAgency = activeDate = ''; $('#searchInput').value = ''; $('#dateFilter').value = ''; $('#agencyFilter').value = ''; render(); });
$('#closeReader').addEventListener('click', () => { $('#readerDialog').close(); history.replaceState(null,'','#explore'); });
$('#previousDoc').addEventListener('click', () => changeReader(-1)); $('#nextDoc').addEventListener('click', () => changeReader(1));
$('#copyLink').addEventListener('click', async () => { await navigator.clipboard?.writeText(location.href); $('#copyLink').textContent = '복사됨'; setTimeout(() => $('#copyLink').textContent = '링크 복사', 1200); });
$('#themeButton').addEventListener('click', () => { document.body.classList.toggle('dark'); localStorage.setItem('nara-theme', document.body.classList.contains('dark') ? 'dark':'light'); });
$('#helpButton').addEventListener('click', () => $('#helpDialog').showModal()); $('[data-close-help]').addEventListener('click', () => $('#helpDialog').close());
$('#savedButton').addEventListener('click', () => { renderSavedList(); $('#savedDialog').showModal(); });
$('[data-close-saved]').addEventListener('click', () => $('#savedDialog').close());
$('#savedList').addEventListener('click', e => { const remove = e.target.closest('[data-remove-saved]'); if (remove) { toggleSaved(remove.dataset.removeSaved); return; } const open = e.target.closest('[data-open-saved]'); if (open) { $('#savedDialog').close(); openReader(open.dataset.openSaved); } });
document.querySelectorAll('[data-journey]').forEach(button => button.addEventListener('click', () => { const journey = button.dataset.journey; if (journey === 'saved') { renderSavedList(); $('#savedDialog').showModal(); return; } activeAgency = journey === 'environment' ? '환경부' : ''; activeDate = ''; $('#agencyFilter').value = activeAgency; $('#dateFilter').value = ''; $('#searchInput').value = journey === 'environment' ? '기후' : ''; render(); $('#explore').scrollIntoView({behavior:'smooth'}); }));
document.addEventListener('keydown', e => { const typing = ['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName); if (e.key === '?' && !typing) $('#helpDialog').showModal(); if (e.key === '/' && !typing) { e.preventDefault(); $('#searchInput').focus(); } if (e.key === 'Escape' && !$('#readerDialog').open && !$('#helpDialog').open && $('#searchInput').value) { $('#searchInput').value = ''; render(); } if ($('#readerDialog').open && !typing && ['j','ArrowDown'].includes(e.key)) changeReader(1); if ($('#readerDialog').open && !typing && ['k','ArrowUp'].includes(e.key)) changeReader(-1); });
if (localStorage.getItem('nara-theme') === 'dark') document.body.classList.add('dark');
initialize();
const hashId = location.hash.replace('#record-',''); if (hashId && records.some(r => r.id === hashId)) openReader(hashId);
