// 구글 시트 웹앱 URL 설정 (Google Apps Script 배포 URL)
const GOOGLE_SHEETS_WEB_APP_URL = ""; // 구글 앱스 스크립트 배포 시 해당 URL 입력

let side='buy',tradeCount=8,cash=6820000,transactions=[];
let isLoggedIn = false; // 최초 접속 시 미로그인 상태로 시작
let currentUser = null;

// 로컬 저장소 기반 사용자 계정 DB (초기 샘플 계정)
function getStoredUsers() {
  const users = localStorage.getItem('mock_trading_users');
  if (users) return JSON.parse(users);
  const defaultUsers = { 'investor@example.com': { pw: '123456', joinDate: '2026.01.15' } };
  localStorage.setItem('mock_trading_users', JSON.stringify(defaultUsers));
  return defaultUsers;
}

function saveUserToLocal(id, pw) {
  const users = getStoredUsers();
  const joinDate = new Date().toLocaleDateString('ko-KR');
  users[id] = { pw, joinDate };
  localStorage.setItem('mock_trading_users', JSON.stringify(users));
}

// 화면 전환 함수
function navigate(page){
  if (!isLoggedIn && page !== 'auth') {
    switchAuthTab('login');
    page = 'auth';
  }

  document.querySelectorAll('.screen').forEach(s=>s.classList.toggle('active',s.id===page));
  document.querySelectorAll('.navbtn').forEach(b=>b.classList.toggle('active',
    b.dataset.page===page || 
    (page==='trade'&&b.dataset.page==='market') || 
    (page==='history'&&b.dataset.page==='home')
  ));
  
  // 로그인 여부에 따른 하단 네비게이션 및 헤더 프로필 표시
  const nav = document.getElementById('app-bottomnav');
  const profileBtn = document.getElementById('header-profile-btn');
  if (nav) nav.style.display = isLoggedIn ? 'grid' : 'none';
  if (profileBtn) profileBtn.textContent = isLoggedIn ? '나' : '로그인';

  const mainEl = document.querySelector('main');
  if(mainEl) mainEl.scrollTo({top:0,behavior:'smooth'});
}

function switchAuthTab(tab) {
  document.getElementById('tab-login').classList.toggle('on', tab === 'login');
  document.getElementById('tab-signup').classList.toggle('on', tab === 'signup');
  document.getElementById('form-login').hidden = (tab !== 'login');
  document.getElementById('form-signup').hidden = (tab !== 'signup');
  document.getElementById('auth-login-message').hidden = true;
  document.getElementById('auth-signup-message').hidden = true;
}

function message(el,type,title,body){el.className='notice'+(type?' '+type:'');el.innerHTML='<strong>'+title+'</strong>'+body;el.hidden=false;}

// 1. 로그인 처리
function handleLogin(){
  const id = document.getElementById('login-id').value.trim();
  const pw = document.getElementById('login-pw').value.trim();
  const msg = document.getElementById('auth-login-message');

  if(!id || !pw){
    message(msg, 'error', '입력 오류', '아이디와 비밀번호를 모두 입력해 주세요.');
    return;
  }

  const users = getStoredUsers();
  if(!users[id] || users[id].pw !== pw){
    message(msg, 'error', '로그인 실패', '아이디 또는 비밀번호가 일치하지 않습니다.');
    return;
  }

  isLoggedIn = true;
  currentUser = id;
  document.getElementById('current-user-id').textContent = id;
  document.getElementById('user-join-date').textContent = users[id].joinDate || '2026.01.15';
  
  navigate('home');
}

// 2. 회원가입 처리 (구글 시트 및 LocalStorage 동시 저장)
function handleSignup(){
  const id = document.getElementById('signup-id').value.trim();
  const pw = document.getElementById('signup-pw').value.trim();
  const pwConfirm = document.getElementById('signup-pw-confirm').value.trim();
  const msg = document.getElementById('auth-signup-message');

  if(!id || !pw || !pwConfirm){
    message(msg, 'error', '입력 오류', '모든 항목을 입력해 주세요.');
    return;
  }

  if(pw !== pwConfirm){
    message(msg, 'error', '비밀번호 불일치', '입력하신 비밀번호와 비밀번호 재확인이 일치하지 않습니다.');
    return;
  }

  const users = getStoredUsers();
  if(users[id]){
    message(msg, 'error', '회원가입 실패', '이미 존재하거나 등록된 아이디입니다.');
    return;
  }

  message(msg, 'loading', '계정 생성 중', '구글 시트 및 저장소에 회원 정보를 등록하고 있습니다…');

  // 로컬 저장소 저장 (즉시 로그인 가능)
  saveUserToLocal(id, pw);

  // 구글 시트 연동 전송 (Google Apps Script Web App URL이 설정된 경우 전송)
  if(GOOGLE_SHEETS_WEB_APP_URL){
    fetch(GOOGLE_SHEETS_WEB_APP_URL, {
      method: 'POST',
      mode: 'no-cors',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: id, pw: pw, joinDate: new Date().toISOString() })
    }).catch(err => console.log('Google Sheets Sync:', err));
  }

  setTimeout(() => {
    message(msg, '', '회원가입 완료!', '계정이 성공적으로 생성되었습니다. 작성하신 아이디로 로그인해 주세요.');
    document.getElementById('login-id').value = id;
    document.getElementById('login-pw').value = pw;
    setTimeout(() => {
      switchAuthTab('login');
    }, 1200);
  }, 500);
}

function handleLogout(){
  isLoggedIn = false;
  currentUser = null;
  navigate('auth');
}

function setSide(value){side=value;document.getElementById('buy').classList.toggle('on',side==='buy');document.getElementById('sell').classList.toggle('on',side==='sell')}
function won(n){return '₩'+Math.round(n).toLocaleString('ko-KR')}
function updateTotal(){const q=Number(document.getElementById('quantity').value)||0;document.getElementById('order-total').textContent=won(q*78000)}
if(document.getElementById('quantity')) document.getElementById('quantity').addEventListener('input',updateTotal);

function submitTrade(){
 const q=Number(document.getElementById('quantity').value),out=document.getElementById('trade-message'),amount=q*78000;
 if(!Number.isInteger(q)||q<1){message(out,'error','입력 오류','주문 수량은 1 이상의 정수로 입력해 주세요.');return}
 if(side==='buy'&&amount>cash){message(out,'error','가상 잔액 부족','가상 현금 잔액보다 주문 금액이 큽니다.');return}
 message(out,'loading','거래 처리 중','가상 주문을 처리하고 있습니다…');
 setTimeout(()=>{
   if(side==='buy')cash-=amount;else cash+=amount;
   tradeCount++;transactions.unshift({label:'오늘 · 삼성전자 '+(side==='buy'?'매수 ':'매도 ')+q+'주',amount});
   document.getElementById('cash').textContent=won(cash);document.getElementById('trade-cash').textContent=won(cash);
   document.getElementById('trade-count').textContent=tradeCount+'회';
   document.getElementById('history-count').textContent=(4+transactions.length)+'건';
   const row=document.createElement('div');row.className='listitem';row.innerHTML='<span>'+transactions[0].label+'</span><b>'+won(amount)+'</b>';document.getElementById('history-list').prepend(row);
   document.getElementById('history-empty').hidden=true;
   const recent=document.createElement('div');recent.className='listitem';recent.innerHTML='<span>'+transactions[0].label+'</span><b>'+won(amount)+'</b>';document.getElementById('recent-list').prepend(recent);
   message(out,'','거래 완료', (side==='buy'?'매수':'매도')+' '+q+'주가 가상 거래 기록에 반영되었습니다.');
 },450);
}

function filterStocks(){const q=document.getElementById('stock-search').value.trim().toLowerCase();let count=0;document.querySelectorAll('#stocks .stock').forEach(row=>{const show=row.dataset.name.toLowerCase().includes(q);row.style.display=show?'flex':'none';if(show)count++});document.getElementById('stock-empty').hidden=count>0}
function period(p,btn){document.querySelectorAll('#analysis .chip').forEach(x=>x.classList.remove('on'));btn.classList.add('on');const now=new Date('2026-10-31T12:00:00');let start=new Date(now);if(p==='week')start.setDate(start.getDate()-6);if(p==='month')start.setMonth(start.getMonth()-1);if(p==='all')start=new Date('2026-01-01T12:00:00');document.getElementById('from-date').value=start.toISOString().slice(0,10);document.getElementById('to-date').value=now.toISOString().slice(0,10)}
function analyze(){const from=document.getElementById('from-date').value,to=document.getElementById('to-date').value,msg=document.getElementById('analysis-message'),content=document.getElementById('analysis-content');if(!from||!to||from>to){message(msg,'error','기간 입력 오류','시작일과 종료일을 확인해 주세요.');content.innerHTML='';return}message(msg,'loading','분석 처리 중','선택한 기간의 거래 기록을 집계하고 있습니다…');setTimeout(()=>{if(transactions.length===0&&from>'2026-10-31'){message(msg,'','분석 결과 없음','선택한 기간에 확인할 거래 기록이 없습니다.');content.innerHTML='<div class="empty">분석할 데이터가 없습니다.</div>'}else{message(msg,'','분석 완료 · 예시 데이터',from+'부터 '+to+'까지의 통계를 표시합니다.');}},350)}
