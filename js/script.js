let side='buy',tradeCount=8,cash=6820000,transactions=[];
const pages=['home','market','trade','history','analysis','feedback','project'];
function navigate(page){
  document.querySelectorAll('.screen').forEach(s=>s.classList.toggle('active',s.id===page));
  document.querySelectorAll('.navbtn').forEach(b=>b.classList.toggle('active',b.dataset.page===page || (page==='trade'&&b.dataset.page==='market') || (page==='project'&&b.dataset.page==='feedback') || (page==='history'&&b.dataset.page==='home')));
  window.scrollTo({top:0,behavior:'smooth'});
}
function setSide(value){side=value;document.getElementById('buy').classList.toggle('on',side==='buy');document.getElementById('sell').classList.toggle('on',side==='sell')}
function won(n){return '₩'+Math.round(n).toLocaleString('ko-KR')}
function updateTotal(){const q=Number(document.getElementById('quantity').value)||0;document.getElementById('order-total').textContent=won(q*78000)}
document.getElementById('quantity').addEventListener('input',updateTotal);
function message(el,type,title,body){el.className='notice'+(type?' '+type:'');el.innerHTML='<strong>'+title+'</strong>'+body}
function submitTrade(){
 const q=Number(document.getElementById('quantity').value),out=document.getElementById('trade-message'),amount=q*78000;
 if(!Number.isInteger(q)||q<1){message(out,'error','입력 오류','주문 수량은 1 이상의 정수로 입력해 주세요. 수량을 수정한 뒤 다시 실행할 수 있습니다.');return}
 if(side==='buy'&&amount>cash){message(out,'error','가상 잔액 부족','가상 현금 잔액보다 주문 금액이 큽니다. 수량을 줄인 뒤 다시 시도해 주세요.');return}
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
function analyze(){const from=document.getElementById('from-date').value,to=document.getElementById('to-date').value,msg=document.getElementById('analysis-message'),content=document.getElementById('analysis-content');if(!from||!to||from>to){message(msg,'error','기간 입력 오류','시작일과 종료일을 확인해 주세요. 시작일은 종료일보다 늦을 수 없습니다.');content.innerHTML='';return}message(msg,'loading','분석 처리 중','선택한 기간의 거래 기록을 집계하고 있습니다…');setTimeout(()=>{if(transactions.length===0&&from>'2026-10-31'){message(msg,'','분석 결과 없음','선택한 기간에 확인할 거래 기록이 없습니다. 기간을 변경해 다시 확인해 주세요.');content.innerHTML='<div class="empty">분석할 데이터가 없습니다.</div>'}else{message(msg,'','분석 완료 · 예시 데이터',from+'부터 '+to+'까지의 예시 통계를 표시합니다. 실제 데이터 연동 전의 고정 예시 결과입니다.');}},350)}
function previewEnd(){document.getElementById('project-status').textContent='종료';message(document.getElementById('project-message'),'error','프로젝트 종료 · 예시 상태','첫 주 평균 거래 횟수가 0건인 경우 체결량 미달로 종료됩니다. BC-01 평가와 첫 주 기록 재평가는 진행하지 않습니다.')}