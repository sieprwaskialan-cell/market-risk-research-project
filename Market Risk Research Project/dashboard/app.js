/* The source snapshot is embedded in data.js so this dashboard works offline. */
const D = window.RESEARCH_DATA;
const $ = id => document.getElementById(id);
const keys = Object.keys(D.portfolios);
const symbols = Object.keys(D.assets);
const assetColors = {SPY:'#39464c',QQQ:'#157b70',IWM:'#b44e41',TLT:'#827024',GLD:'#705888'};
let activeView = 'portfolios';
let portfolioChart, assetChart;
let currentMetrics = [];
const pct = (v,digits=1) => Number.isFinite(v) ? `${(v*100).toFixed(digits)}%` : 'N/A';
const number = v => Number.isFinite(v) ? v.toFixed(2) : 'N/A';
const money = v => '$'+Math.round(v).toLocaleString('en-US');
const compound = values => values.reduce((a,b)=>a*(1+b),1);

function metrics(values){
  if(values.length<2)return null;
  const n=values.length, mean=values.reduce((a,b)=>a+b,0)/n;
  const sd=Math.sqrt(values.reduce((a,b)=>a+Math.pow(b-mean,2),0)/(n-1));
  let wealth=1,peak=1,dd=0;
  const growth=[1],drawdown=[0];
  for(const r of values){wealth*=1+r;peak=Math.max(peak,wealth);const loss=wealth/peak-1;dd=Math.min(dd,loss);growth.push(wealth);drawdown.push(loss);}
  return {total_return:wealth-1,annualized_return:Math.pow(wealth,252/n)-1,annualized_volatility:sd*Math.sqrt(252),sharpe_ratio:sd>1e-15?mean/sd*Math.sqrt(252):null,max_drawdown:dd,growth,drawdown,observations:n};
}

function selectedRange(){
  const start=$('start').value,end=$('end').value;
  if(!start||!end||start>end)return {error:'Choose a start date on or before the end date.'};
  const indices=D.dates.map((d,i)=>d>=start&&d<=end?i:-1).filter(i=>i>=0);
  if(indices.length<2)return {error:'This range has fewer than two daily returns. Choose a wider date range.'};
  const first=indices[0],last=indices[indices.length-1];
  return {first,last,labels:[D.priceDates[first],...D.dates.slice(first,last+1)]};
}

function chart(canvas,old,datasets,labels,isDrawdown=false){
  const config = {
    type: 'line', data: { labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      onResize: (instance, size) => { instance.options.scales.x.ticks.maxTicksLimit = size.width < 500 ? 4 : 7; },
      interaction: { mode: 'index', intersect: false },
      elements: { point: { radius: 0, hitRadius: 8 }, line: { borderWidth: 1.8, tension: 0 } },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${isDrawdown ? pct(ctx.parsed.y, 2) : money(ctx.parsed.y)}` } }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            maxTicksLimit: window.innerWidth < 600 ? 4 : 7, maxRotation: 0, color: '#677777',
            callback: function(value) {
              const date = this.getLabelForValue(value);
              return window.innerWidth < 600 && labels.length > 500 ? date.slice(0, 4) : date.slice(0, 7);
            }
          }
        },
        y: { grid: { color: '#e8eeeb' }, border: { display: false }, ticks: { color: '#677777', callback: v => isDrawdown ? pct(v, 0) : money(v) } }
      }
    }
  };
  if(old){old.data=config.data;old.options=config.options;old.update();return old;}
  return new Chart(canvas,config);
}

function legend(id,items){$(id).innerHTML=items.map(i=>`<span><b style="background:${i.color}"></b>${i.name}</span>`).join('');}
function weightLabel(spec){return Object.entries(spec.weights).map(([s,w])=>`${s} ${(100*w).toFixed(w===1/3?1:0)}%`).join(' · ');}
function tint(value,scale=.15){const fraction=Math.min(Math.abs(value)/scale,1);return value>=0?`rgba(32,137,106,${.08+fraction*.47})`:`rgba(191,75,57,${.08+fraction*.43})`;}
function corr(a,b){const n=a.length,ma=a.reduce((s,v)=>s+v,0)/n,mb=b.reduce((s,v)=>s+v,0)/n;let cov=0,va=0,vb=0;for(let i=0;i<n;i++){cov+=(a[i]-ma)*(b[i]-mb);va+=Math.pow(a[i]-ma,2);vb+=Math.pow(b[i]-mb,2);}return va&&vb?cov/Math.sqrt(va*vb):null;}

function renderPortfolios(range){
  const scenario=`${$('rebalance').value}_${$('cost').value}`;
  currentMetrics=keys.map(key=>({key,...metrics(D.scenarios[scenario][key].slice(range.first,range.last+1))}));
  const focus=currentMetrics.find(r=>r.key===$('focus').value);
  $('kpi-return').textContent=pct(focus.total_return);$('kpi-annual').textContent=`${pct(focus.annualized_return)} annualized`;
  $('kpi-vol').textContent=pct(focus.annualized_volatility);$('kpi-drawdown').textContent=pct(focus.max_drawdown);$('kpi-sharpe').textContent=number(focus.sharpe_ratio);
  $('period-label').textContent=`${D.dates[range.first]} to ${D.dates[range.last]} · ${range.last-range.first+1} daily returns · USD`;
  $('comparison').querySelector('tbody').innerHTML=currentMetrics.map(m=>`<tr class="${m.key===focus.key?'selected':''}"><td class="name">${D.portfolios[m.key].name}<small>${weightLabel(D.portfolios[m.key])}</small></td><td>${pct(m.total_return)}</td><td>${pct(m.annualized_return)}</td><td>${pct(m.annualized_volatility)}</td><td>${pct(m.max_drawdown)}</td><td>${number(m.sharpe_ratio)}</td></tr>`).join('');
  const mode=document.querySelector('[name="chartMode"]:checked').value;
  const dd=mode==='drawdown';$('chart-title').textContent=dd?'Drawdown from the selected-window peak':'Growth of $10,000';
  const datasets=currentMetrics.map(m=>({label:D.portfolios[m.key].name,data:dd?m.drawdown:m.growth.map(v=>v*10000),borderColor:D.portfolios[m.key].color,borderWidth:m.key===focus.key?2.4:1.5}));
  portfolioChart=chart($('portfolio-chart'),portfolioChart,datasets,range.labels,dd);
  legend('portfolio-legend',Object.values(D.portfolios));
}

function renderAssets(range){
  const chosen=[...document.querySelectorAll('[name="asset"]:checked')].map(e=>e.value);
  const returnMap=Object.fromEntries(chosen.map(s=>[s,D.assets[s].slice(range.first+1,range.last+2).map((v,i)=>v/D.assets[s][range.first+i]-1)]));
  const ms=chosen.map(s=>({symbol:s,...metrics(returnMap[s])}));
  assetChart=chart($('asset-chart'),assetChart,ms.map(m=>({label:m.symbol,data:m.growth.map(v=>v*10000),borderColor:assetColors[m.symbol]})),range.labels);
  legend('asset-legend',chosen.map(s=>({name:s,color:assetColors[s]})));
  $('asset-metrics').querySelector('tbody').innerHTML=ms.map(m=>`<tr><td>${m.symbol}</td><td>${pct(m.annualized_return)}</td><td>${pct(m.annualized_volatility)}</td><td>${pct(m.max_drawdown)}</td></tr>`).join('');
  $('correlation').innerHTML=`<table class="heatmap"><thead><tr><th scope="col">ETF</th>${chosen.map(s=>`<th scope="col">${s}</th>`).join('')}</tr></thead><tbody>${chosen.map(a=>`<tr><th scope="row">${a}</th>${chosen.map(b=>{const v=corr(returnMap[a],returnMap[b]);return `<td style="background:${tint(v,1)}" title="${a} / ${b}: ${number(v)}">${number(v)}</td>`;}).join('')}</tr>`).join('')}</tbody></table>`;
  renderMonthly();
}

function renderMonthly(){
  const year=$('heatmap-year').value,chosen=[...document.querySelectorAll('[name="asset"]:checked')].map(e=>e.value);
  const months=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  $('monthly-heatmap').innerHTML=`<table class="heatmap"><thead><tr><th>${year}</th>${months.map(m=>`<th>${m}</th>`).join('')}</tr></thead><tbody>${chosen.map(s=>`<tr><th scope="row">${s}</th>${months.map((_,i)=>{const month=`${year}-${String(i+1).padStart(2,'0')}`;const row=D.monthly.find(r=>r.symbol===s&&r.month===month);if(!row||row.monthly_return==='')return '<td>—</td>';const star=row.coverage==='Sample boundary month'?'*':'';return `<td style="background:${tint(row.monthly_return)}" title="${s} ${month}: ${pct(row.monthly_return,2)}; ${row.coverage}">${pct(row.monthly_return)}${star}</td>`;}).join('')}</tr>`).join('')}</tbody></table>`;
}

function renderEvidence(){
  $('source-label').textContent=`Requested ${D.metadata.requested_start} to ${D.metadata.requested_end} · Snapshot ${D.metadata.retrieved_at_utc.slice(0,10)}`;
  $('quality').querySelector('tbody').innerHTML=D.quality.map(q=>`<tr><td>${q.symbol}</td><td>${q.raw_rows.toLocaleString()}</td><td>${q.rows_removed}</td><td>${q.missing_observed_sessions}</td><td>${q.large_moves_flagged}</td></tr>`).join('');
  $('flags').querySelector('tbody').innerHTML=D.issues.filter(i=>i.check==='large_move_review_only').map(i=>`<tr><td>${i.symbol}</td><td>${i.trade_date}</td><td>${pct(Number(i.value),2)}</td><td>Retained; not independently verified</td></tr>`).join('')||'<tr><td colspan="4">No moves met the 10% review threshold.</td></tr>';
}

function render(){
  const range=selectedRange();$('error').hidden=!range.error;
  if(range.error){$('error').textContent=range.error;$('export').disabled=true;document.querySelectorAll('.view').forEach(e=>e.hidden=true);return;}
  $('export').disabled=false;
  document.querySelectorAll('.view').forEach(e=>e.hidden=e.id!==activeView);
  document.querySelectorAll('.portfolio-control').forEach(e=>e.hidden=activeView!=='portfolios');
  if(activeView==='portfolios')renderPortfolios(range);
  if(activeView==='assets')renderAssets(range);
  if(activeView==='evidence')renderEvidence();
}

const min=D.dates[0],max=D.dates[D.dates.length-1];
for(const id of ['start','end']){$(id).min=min;$(id).max=max;$(id).value=id==='start'?min:max;$(id).addEventListener('change',()=>{document.querySelectorAll('[name="period"]').forEach(e=>e.checked=false);render();});}
$('snapshot-date').textContent=`Snapshot ${D.metadata.retrieved_at_utc.slice(0,10)}`;
$('asset-toggles').innerHTML=symbols.map(s=>`<label><input type="checkbox" name="asset" value="${s}" checked>${s}</label>`).join('');
document.querySelectorAll('[name="asset"]').forEach(e=>e.addEventListener('change',()=>{if(!document.querySelector('[name="asset"]:checked'))e.checked=true;render();}));
const years=[...new Set(D.monthly.map(r=>r.month.slice(0,4)))];$('heatmap-year').innerHTML=years.map(y=>`<option value="${y}">${y}</option>`).join('');$('heatmap-year').value=years[years.length-1];$('heatmap-year').addEventListener('change',renderMonthly);
document.querySelectorAll('[name="period"]').forEach(e=>e.addEventListener('change',()=>{const p=e.value;$('start').value=p==='all'?min:p==='2023'?'2023-01-01':`${p}-01-01`;$('end').value=['all','2023'].includes(p)?max:`${p}-12-31`;render();}));
document.querySelectorAll('.tab').forEach(e=>e.addEventListener('click',()=>{activeView=e.dataset.view;document.querySelectorAll('.tab').forEach(t=>{t.classList.toggle('active',t===e);if(t===e)t.setAttribute('aria-current','page');else t.removeAttribute('aria-current');});render();}));
for(const id of ['focus','rebalance','cost'])$(id).addEventListener('change',render);
document.querySelectorAll('[name="chartMode"]').forEach(e=>e.addEventListener('change',render));
$('print').addEventListener('click',()=>window.print());
$('export').addEventListener('click',()=>{const range=selectedRange();if(range.error)return;const scenario=`${$('rebalance').value}_${$('cost').value}`;const rows=keys.map(key=>({key,...metrics(D.scenarios[scenario][key].slice(range.first,range.last+1))}));const fields=['total_return','annualized_return','annualized_volatility','max_drawdown','sharpe_ratio'];const lines=['portfolio,start,end,rebalance,cost_bps,observations,'+fields.join(','),...rows.map(r=>[D.portfolios[r.key].name,D.dates[range.first],D.dates[range.last],$('rebalance').value,$('cost').value,r.observations,...fields.map(k=>r[k]??'')].join(','))];const url=URL.createObjectURL(new Blob([lines.join('\n')],{type:'text/csv'}));const a=document.createElement('a');a.href=url;a.download='portfolio-comparison.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
const periodNames=[...new Set(D.periods.map(p=>p.period))];$('periods-table').querySelector('tbody').innerHTML=periodNames.map(period=>`<tr><td>${period}</td>${keys.map(key=>`<td>${pct(D.periods.find(p=>p.period===period&&p.portfolio===key)?.total_return)}</td>`).join('')}</tr>`).join('');
lucide.createIcons();
render();
window.researchMetrics=metrics;
