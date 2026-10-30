'use strict';
const $=(s,e=document)=>e.querySelector(s),$$=(s,e=document)=>[...e.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const app=$('#app'),dlg=$('#dlg'),S={me:null,likes:new Set(),names:{},unread:0};
const RUB=n=>new Intl.NumberFormat('ru-RU').format(n)+' ₽';
const dur=m=>m<60?m+' мин':Math.floor(m/60)+' ч'+(m%60?' '+m%60+' мин':'');
const D=(s,o)=>new Date(s).toLocaleString('ru-RU',o);
const DAYS=['Понедельник','Вторник','Среда','Четверг','Пятница','Суббота','Воскресенье'];
const badge=()=>S.unread>0?`<span class="badge" aria-label="Непрочитанных: ${S.unread}">${S.unread>99?'99+':S.unread}</span>`:'';
const ST={pending:'Ожидает',confirmed:'Подтверждена',cancelled:'Отменена',completed:'Завершена'};
const HEART='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-7-4.6-9.3-9.1C1.1 8.6 2.9 5 6.4 5c2 0 3.4 1.1 4.1 2.3h3C14.2 6.100 15.600 5 17.600 5c3.500 0 5.300 3.600 3.700 6.900C19 16.400 12 21 12 21z"/></svg>';
const E=(h,p='')=>`<div class="empty"><h2>${h}</h2><p>${p}</p></div>`;
const stars=n=>`<span class="stars" style="--p:${Math.max(0,Math.min(5,n))/5*100}%" role="img" aria-label="Оценка ${String(n).replace('.',',')} из 5">★★★★★</span>`;
const plural=(n,a,b,c)=>{const m=n%100,k=n%10;return n+' '+(m>10&&m<20?c:k===1?a:k>1&&k<5?b:c)};
function toast(m,err){const t=document.createElement('div');t.className='toast'+(err?' err':'');t.textContent=m;$('#toasts').append(t);setTimeout(()=>t.remove(),4500)}

const B='/BookLet';
async function api(path,{method='GET',body,q}={}){
  const qs=q?Object.entries(q).filter(([,v])=>v!==''&&v!=null):[];
  let r;
  try{r=await fetch(B+path+(qs.length?'?'+new URLSearchParams(qs):''),{method,credentials:'same-origin',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined})}
  catch{throw new Error('Нет связи с сервером. Проверьте интернет и попробуйте ещё раз.')}
  let d=null;try{d=await r.json()}catch{}
  if(!r.ok){
    const x=d&&d.detail;
    const e=new Error(Array.isArray(x)?x.map(i=>String(i.msg).replace('Value error, ','')).join('. '):x||'Ошибка '+r.status);
    e.status=r.status;throw e;
  }
  return d;
}
async function refreshUnread(){
  if(!S.me)return setUnread(0);
  try{setUnread((await api('/me/my_notifications/unread_count')).unread)}catch{}
}
function setUnread(n){
  S.unread=n;nav();
  const a=$('.side a[href="/me/notifications"]');if(a)a.innerHTML='Уведомления'+badge();
}
setInterval(()=>{if(S.me&&!document.hidden)refreshUnread()},60000);
async function loadMe(){
  try{S.me=await api('/account/me')}catch{S.me=null;S.likes=new Set();S.unread=0;return}
  try{S.unread=(await api('/me/my_notifications/unread_count')).unread}catch{}
  try{S.likes=new Set((await api('/me/my_favourites',{q:{limit:150}})).announcements.map(a=>a.id))}catch{}
}
async function names(ids){
  await Promise.all([...new Set(ids)].filter(i=>!S.names[i]).map(async i=>{
    try{S.names[i]=(await api(`/user/${i}/profile`)).user.username}catch{S.names[i]='Мастер'}}));
}

/* ---------- router ---------- */
const R=[[/^\/$/,catalog],[/^\/user\/(\d+)$/,profile],[/^\/login$/,login],[/^\/register$/,register],[/^\/forgot$/,forgot],[/^\/reset_password$/,reset],[/^\/me(?:\/(\w+))?$/,account]];
function go(p,replace){history[replace?'replaceState':'pushState'](null,'',p);return render()}
async function render(){
  const p=location.pathname.replace(/(.)\/$/,'$1'),r=R.find(([re])=>re.test(p));
  app.innerHTML='<div class="load">Загрузка…</div>';
  try{await(r?r[1](...p.match(r[0]).slice(1)):app.replaceChildren(Object.assign(document.createElement('div'),{innerHTML:E('Страница не найдена','<a data-l href="/">Вернуться в каталог</a>')})))}
  catch(e){app.innerHTML=E('Не удалось загрузить',esc(e.message))}
  nav();scrollTo(0,0);
}
function nav(){
  const L=(h,t,c='')=>`<a data-l ${c?`class="${c}"`:''} href="${h}"${location.pathname===h?' aria-current="page"':''}>${t}</a>`;
  $('#nav').innerHTML=L('/','Каталог')+(S.me?L('/me/bookings','Мои записи')+L('/me/notifications','Уведомления'+badge())+L('/me/announcements',esc(S.me.user.username),'btn sm'):L('/login','Войти')+L('/register','Регистрация','btn sm'));
}
addEventListener('popstate',render);
document.addEventListener('click',e=>{
  const l=e.target.closest('a[data-l]');
  if(l&&!e.metaKey&&!e.ctrlKey&&!e.shiftKey){e.preventDefault();if(dlg.open)dlg.close();return go(l.getAttribute('href'))}
  if(e.target.closest('[data-close]')||e.target===dlg)return dlg.close();
  const lk=e.target.closest('[data-like]');if(lk)return like(lk);
  const ar=e.target.closest('[data-arch]');if(ar)return archive(ar.dataset.arch);
  const cn=e.target.closest('[data-cancel]');if(cn)return cancelBooking(cn);
  const rv=e.target.closest('[data-review]');if(rv)return reviewForm({anc:+rv.dataset.anc,name:rv.dataset.name,booking:rv.dataset.review?+rv.dataset.review:null,after:rv.dataset.after});
  const c=e.target.closest('[data-open]');if(c)open(c.dataset.open);
});
document.addEventListener('keydown',e=>{if(e.key==='Enter'&&e.target.matches('[data-open]'))open(e.target.dataset.open)});

/* ---------- forms ---------- */
const F=(id,fields,btn,extra='')=>`<form id="${id}" class="form">${fields.map(([n,l,t='text',a=''])=>`<label>${l}<input name="${n}" type="${t}" ${a} required></label>`).join('')}<p class="err" role="alert"></p><button class="btn">${btn}</button>${extra}</form>`;
function submit(id,fn){
  const f=$('#'+id);
  f.onsubmit=async e=>{e.preventDefault();const b=$('button:not([type=button])',f),er=$('.err',f);er.textContent='';b.disabled=true;
    try{await fn(Object.fromEntries(new FormData(f)),f)}catch(x){er.textContent=x.message}b.disabled=false};
}
const shell=(t,body)=>`<div class="narrow panel"><h1>${t}</h1>${body}</div>`;
const finish=async()=>{await loadMe();go('/')};

async function login(){
  app.innerHTML=shell('Вход',F('lf',[['username','Логин','text','autocomplete="username"'],['password','Пароль','password','autocomplete="current-password"']],'Войти','<p class="links"><a data-l href="/forgot">Забыли пароль?</a><a data-l href="/register">Создать аккаунт</a></p>'));
  submit('lf',async d=>{const r=await api('/login',{method:'POST',body:d});if(!/успешно/.test(r.msg))return twofa(r.msg);toast('С возвращением!');await finish()});
}
function twofa(msg){
  app.innerHTML=shell('Код из письма',`<p class="hint" style="margin-bottom:14px">${esc(msg)}. Код действует 5 минут.</p>`+F('tf',[['usercode','Код подтверждения','text','inputmode="numeric" maxlength="6" autocomplete="one-time-code"']],'Подтвердить','<button type="button" class="btn ghost" id="rs">Отправить код ещё раз</button>'));
  $('#rs').onclick=()=>api('/login/2fa/resend',{method:'POST'}).then(r=>toast(r.msg),e=>toast(e.message,1));
  submit('tf',async d=>{await api('/login/2fa',{method:'POST',body:d});toast('С возвращением!');await finish()});
}
async function register(){
  app.innerHTML=shell('Регистрация',F('rf',[['username','Логин','text','minlength="3" maxlength="50" autocomplete="username"'],['email','Почта','email','autocomplete="email"'],['password','Пароль','password','minlength="6" maxlength="20" autocomplete="new-password"']],'Продолжить','<p class="hint">Пароль: 6–20 символов, минимум одна буква и один спецсимвол (например, !@#).</p><p class="links"><span>Уже есть аккаунт?</span><a data-l href="/login">Войти</a></p>'));
  submit('rf',async d=>{const r=await api('/registration',{method:'POST',body:d});verify(d.email,r.msg)});
}
function verify(email,msg){
  app.innerHTML=shell('Подтвердите почту',`<p class="hint" style="margin-bottom:14px">${esc(msg)}. Письмо отправлено на ${esc(email)}.</p>`+F('vf',[['usercode','Код из письма','text','inputmode="numeric" maxlength="6" autocomplete="one-time-code"']],'Создать аккаунт','<button type="button" class="btn ghost" id="rs">Отправить код ещё раз</button>'));
  $('#rs').onclick=()=>api('/registration/verify_email/resend_code',{method:'POST'}).then(r=>toast(r.msg),e=>toast(e.message,1));
  submit('vf',async d=>{await api('/registration/verify_email',{method:'POST',body:d});toast('Аккаунт создан. Теперь войдите.');go('/login')});
}
async function forgot(){
  app.innerHTML=shell('Восстановление пароля',F('ff',[['username','Логин'],['email','Почта','email']],'Отправить ссылку','<p class="links"><a data-l href="/login">Вернуться ко входу</a></p>'));
  submit('ff',async d=>{const r=await api('/forgot_password',{method:'POST',body:d});$('#ff').innerHTML=`<p>${esc(r.msg)}</p><p class="hint">Ссылка действует 5 минут.</p>`});
}
async function reset(){
  const token=new URLSearchParams(location.search).get('reset_token');
  if(!token){app.innerHTML=shell('Ссылка недействительна','<p>Запросите восстановление пароля заново.</p><a data-l class="btn" href="/forgot">Запросить ссылку</a>');return}
  app.innerHTML=shell('Новый пароль',F('pf',[['new_password','Новый пароль','password','minlength="6" maxlength="20" autocomplete="new-password"']],'Сохранить пароль','<p class="hint">6–20 символов, минимум одна буква и один спецсимвол.</p>'));
  submit('pf',async d=>{await api('/reset_password',{method:'POST',body:{token,new_password:d.new_password}});toast('Пароль изменён. Войдите с новым паролем.');go('/login',1)});
}

/* ---------- catalog ---------- */
const card=(a,o={})=>`<article class="card" tabindex="0" data-open="${a.id}">
<div class="top2"><span class="chip">${esc(a.type)}</span>${o.like===false?'':`<button class="like${S.likes.has(a.id)?' on':''}" data-like="${a.id}" aria-label="В избранное">${HEART}</button>`}</div>
<h3>${esc(a.name)}</h3>${o.by===false?'':`<p class="by">Мастер: <a data-l href="/user/${a.user_id}">${esc(S.names[a.user_id])}</a></p>`}
<div class="bar"><i style="width:${Math.max(18,Math.min(100,a.duration_minutes/2.4))}%"></i><span>${dur(a.duration_minutes)}</span></div>
<div class="foot"><b>${RUB(a.price)}</b>${o.extra?o.extra(a):''}</div></article>`;
async function grid(el,more,get,o={}){
  const L=12;let off=0;
  const run=async()=>{
    const items=await get(off,L);items.forEach(a=>{if(a.provider_username)S.names[a.user_id]=a.provider_username});await names(items.map(a=>a.user_id));
    el.insertAdjacentHTML('beforeend',items.map(a=>card(a,o)).join('')+'');
    off+=items.length;more.hidden=items.length<L;
    if(!off)el.innerHTML=E(o.empty||'Ничего не нашлось',o.hint||'Попробуйте другой запрос или уберите фильтры.');
  };
  el.innerHTML='';more.onclick=()=>run().catch(e=>toast(e.message,1));
  try{await run()}catch(e){el.innerHTML=E('Не удалось загрузить',esc(e.message))}
}
async function catalog(){
  app.innerHTML=`<section class="hero"><h1>Запишитесь к мастеру на удобное время</h1><p>Выберите услугу, посмотрите свободные окна и забронируйте за минуту.</p>
<form id="sf" class="search" role="search"><input name="name" placeholder="Что ищете? Например, стрижка" aria-label="Название"><input name="type" placeholder="Тип услуги" aria-label="Тип услуги"><input name="min_price" type="number" min="0" placeholder="Цена от" aria-label="Цена от"><input name="max_price" type="number" min="0" placeholder="Цена до" aria-label="Цена до">
<select name="sort" aria-label="Сортировка"><option value="newest">Сначала новые</option><option value="price_asc">Сначала дешёвые</option><option value="price_desc">Сначала дорогие</option><option value="name">По названию</option></select><button class="btn">Найти</button></form></section>
<div id="gl" class="grid"></div><div class="more"><button class="btn ghost" id="mr" hidden>Показать ещё</button></div>`;
  const f=$('#sf'),load=()=>{const q=Object.fromEntries(new FormData(f));return grid($('#gl'),$('#mr'),async(offset,limit)=>(await api('/catalog',{q:{...q,limit,offset}})).announcements)};
  f.onsubmit=e=>{e.preventDefault();load()};
  await load();
}
async function like(b){
  if(!S.me)return go('/login');
  const id=+b.dataset.like;
  try{await api(`/catalog/${id}/like`,{method:'POST'});S.likes.has(id)?S.likes.delete(id):S.likes.add(id);
    $$(`[data-like="${id}"]`).forEach(x=>x.classList.toggle('on',S.likes.has(id)));toast(S.likes.has(id)?'Добавлено в избранное':'Убрано из избранного')}
  catch(e){toast(e.message,1)}
}
const modal=h=>{dlg.innerHTML=`<div class="dl">${h}<button class="x" data-close aria-label="Закрыть">×</button></div>`};
async function open(id){
  modal('<p class="muted">Загрузка…</p>');if(!dlg.open)dlg.showModal();
  try{
    const {announcement:a}=await api('/catalog/'+id);if(a.provider_username)S.names[a.user_id]=a.provider_username;await names([a.user_id]);
    modal(`<h2>${esc(a.name)}</h2><div class="meta"><span class="chip">${esc(a.type)}</span><span class="chip">${dur(a.duration_minutes)}</span><span class="chip">Отмена за ${a.cancel_before_hours} ч до начала</span></div>
<p class="by">Мастер: <a data-l href="/user/${a.user_id}">${esc(S.names[a.user_id])}</a></p>${a.description?`<p class="desc">${esc(a.description)}</p>`:''}<div class="foot"><b>${RUB(a.price)}</b></div><div id="bk"></div><section class="revs" id="rv" aria-labelledby="rvh"></section>`);
    await Promise.all([booking(a,$('#bk')),reviews(a,$('#rv'))]);
  }catch(e){modal(`<h2>Не удалось открыть услугу</h2><p>${esc(e.message)}</p>`)}
}
function slotList(d){
  let a=Array.isArray(d)?d:d&&(d.slots||d.free_slots);
  if(a&&!Array.isArray(a)&&typeof a==='object')a=Object.values(a).flat();
  return Array.isArray(a)?a.map(x=>typeof x==='string'?x:x&&(x.start_at||x.start)).filter(Boolean):null;
}
async function booking(a,box){
  if(!S.me)return void(box.innerHTML='<a data-l class="btn" href="/login">Войдите, чтобы записаться</a>');
  if(S.me.user.id===a.user_id)return void(box.innerHTML='<p class="muted">Это ваша услуга.</p>');
  const load=async()=>{try{return slotList(await api(`/catalog/${a.id}/slots`))}catch{return null}};
  let sl=await load(),day=null,pick=null;const key=s=>new Date(s).toLocaleDateString('sv');
  const send=async()=>{
    const g=$('#go',box);g.disabled=true;
    try{const r=await api(`/catalog/${a.id}/book`,{method:'POST',q:{start_at:pick}});if(!r||!r.booking)throw new Error('Бронь не создана. Попробуйте ещё раз.');dlg.close();toast('Запись создана');go('/me/bookings')}
    catch(e){toast(e.message,1);if(e.status===409){sl=await load();day=pick=null;draw()}else g.disabled=false}};
  const draw=()=>{
    if(!sl)return void(box.innerHTML='<p class="muted">Не удалось загрузить свободное время. Попробуйте позже.</p>');
    else if(!sl.length)return void(box.innerHTML='<p class="muted">Свободных окон пока нет. Загляните позже.</p>');
    else{
      const g={};sl.forEach(s=>(g[key(s)]??=[]).push(s));day??=Object.keys(g)[0];
      box.innerHTML=`<div class="slotbox"><b>Выберите день и время</b><div class="days">${Object.keys(g).map(k=>`<button data-d="${k}" aria-pressed="${k===day}">${D(g[k][0],{weekday:'short',day:'numeric',month:'short'})}</button>`).join('')}</div><div class="times">${g[day].map(s=>`<button data-t="${s}" aria-pressed="${s===pick}">${D(s,{timeStyle:'short'})}</button>`).join('')}</div></div><button class="btn sun" id="go" ${pick?'':'disabled'}>${pick?'Записаться на '+D(pick,{dateStyle:'long',timeStyle:'short'}):'Выберите время'}</button>`;
      $$('[data-d]',box).forEach(b=>b.onclick=()=>{day=b.dataset.d;pick=null;draw()});
      $$('[data-t]',box).forEach(b=>b.onclick=()=>{pick=b.dataset.t;draw()});
    }
    $('#go',box).onclick=send;
  };
  draw();
}

/* ---------- reviews ---------- */
const reviewItem=r=>`<article class="rev"><div class="rh"><a data-l href="/user/${r.author_id}">${esc(r.author_username)}</a>${stars(r.rating)}<time datetime="${esc(r.created_at)}">${D(r.created_at,{dateStyle:'medium'})}</time></div>${r.text?`<p>${esc(r.text)}</p>`:''}</article>`;
async function reviews(a,box){
  const L=10;let off=0,total=0;
  const draw=(avg,items)=>{
    const mine=S.me&&S.me.user.id!==a.user_id;
    box.innerHTML=`<div class="rtop"><h3 id="rvh">Отзывы</h3>${total?`<span class="avg"><b>${String(avg).replace('.',',')}</b>${stars(avg)}<small>${plural(total,'отзыв','отзыва','отзывов')}</small></span>`:''}</div>
${mine?`<button class="btn sm ghost" data-review data-anc="${a.id}" data-name="${esc(a.name)}" data-after="open">Оставить отзыв</button>`:''}
${total?`<div class="rlist">${items}</div><button class="btn sm ghost" id="rm" ${off<total?'':'hidden'}>Показать ещё</button>`:'<p class="hint">Отзывов пока нет. Их можно оставить после визита.</p>'}`;
  };
  try{
    let d=await api(`/catalog/${a.id}/reviews`,{q:{limit:L,offset:0}});
    total=d.total;off=d.reviews.length;let html=d.reviews.map(reviewItem).join('');
    draw(d.average_rating,html);
    const more=()=>{const b=$('#rm',box);if(b)b.onclick=async()=>{b.disabled=true;
      try{d=await api(`/catalog/${a.id}/reviews`,{q:{limit:L,offset:off}});off+=d.reviews.length;html+=d.reviews.map(reviewItem).join('');draw(d.average_rating,html);more()}
      catch(e){toast(e.message,1);b.disabled=false}}};
    more();
  }catch(e){box.innerHTML=`<h3 id="rvh">Отзывы</h3><p class="muted">Не удалось загрузить отзывы.</p>`}
}
function reviewForm({anc,name,booking,after}){
  let val=0;
  modal(`<h2>Оставить отзыв</h2><p class="by">${esc(name)}</p>
<form id="rf2" class="form"><div><span class="lbl" id="rl">Ваша оценка</span><div class="pick" role="radiogroup" aria-labelledby="rl">${[1,2,3,4,5].map(n=>`<button type="button" role="radio" aria-checked="false" aria-label="${plural(n,'звезда','звезды','звёзд')}" data-star="${n}">★</button>`).join('')}</div></div>
<label>Комментарий <small class="muted">необязательно</small><textarea name="text" rows="4" maxlength="1000" placeholder="Как всё прошло? Что понравилось?"></textarea></label><small class="hint" id="cnt">0 / 1000</small>
<p class="err" role="alert"></p><button class="btn sun">Отправить отзыв</button></form>`);
  if(!dlg.open)dlg.showModal();
  const f=$('#rf2'),paint=n=>$$('[data-star]',f).forEach(b=>{const on=+b.dataset.star<=n;b.classList.toggle('on',on);b.setAttribute('aria-checked',+b.dataset.star===val)});
  $$('[data-star]',f).forEach(b=>{b.onclick=()=>{val=+b.dataset.star;paint(val);$('.err',f).textContent=''};
    b.onmouseenter=()=>paint(+b.dataset.star);b.onfocus=()=>paint(+b.dataset.star);b.onblur=()=>paint(val);
    b.onkeydown=e=>{const k={ArrowRight:1,ArrowUp:1,ArrowLeft:-1,ArrowDown:-1}[e.key];if(!k)return;e.preventDefault();val=Math.min(5,Math.max(1,(val||0)+k));paint(val);$(`[data-star="${val}"]`,f).focus()}});
  f.onmouseleave=()=>paint(val);
  const ta=$('textarea',f);ta.oninput=()=>$('#cnt').textContent=ta.value.length+' / 1000';
  f.onsubmit=async e=>{e.preventDefault();const er=$('.err',f),b=$('button.btn',f);er.textContent='';
    if(!val)return void(er.textContent='Поставьте оценку от 1 до 5');
    b.disabled=true;
    try{await api(`/catalog/${anc}/reviews`,{method:'POST',body:{rating:val,text:ta.value.trim()||null,booking_id:booking}});
      toast('Спасибо! Отзыв опубликован');if(after==='open'){await open(anc)}else{dlg.close();render()}}
    catch(x){er.textContent=x.message;b.disabled=false}};
}

/* ---------- public profile ---------- */
async function profile(id){
  const [p,an,om]=await Promise.all([api(`/user/${id}/profile`),api(`/user/${id}/announcements`),api(`/user/${id}/operating_mode`)]);
  const u=p.user,items=an.announcements,sh=DAYS.map(d=>d.slice(0,2));
  app.innerHTML=`<section class="hero"><h1>${esc(u.username)}</h1><p>На BookLet с ${D(u.created_at,{month:'long',year:'numeric'})}. Почта: ${esc(u.email)}</p></section>
<div class="panel"><h2 style="font-size:20px;margin-bottom:10px">Часы приёма</h2>${om.rules.length?om.rules.map(r=>`<span class="chip" style="margin:0 6px 6px 0">${sh[r.weekday]} ${r.start_time.slice(0,5)}–${r.end_time.slice(0,5)}</span>`).join(''):'<p class="hint">Режим работы не задан.</p>'}</div>
<div class="h2" style="margin-top:28px"><h2>Услуги</h2></div><div id="gl" class="grid" style="margin-top:0"></div><div class="more"><button class="btn ghost" id="mr" hidden>Показать ещё</button></div>`;
  S.names[id]=u.username;
  await grid($('#gl'),$('#mr'),async(o,l)=>items.slice(o,o+l),{by:false,empty:'Пока нет услуг',hint:'Мастер ещё ничего не опубликовал.'});
}

/* ---------- account ---------- */
const TABS=[['bookings','Мои записи'],['requests','Записи ко мне'],['calendar','Календарь'],['announcements','Мои услуги'],['favourites','Избранное'],['notifications','Уведомления'],['schedule','Режим работы'],['settings','Настройки']];
async function account(tab='bookings'){
  if(!S.me)return go('/login',1);
  const T={bookings:el=>bookings(el,'/me/my_bookings','Мои записи',1),requests:el=>bookings(el,'/me/my_announcements/booked','Записи ко мне',0),calendar,announcements,favourites,notifications,schedule,settings}[tab];
  if(!T)return go('/me/bookings',1);
  app.innerHTML=`<div class="layout"><aside class="side" aria-label="Личный кабинет">${TABS.map(([k,n])=>`<a data-l href="/me/${k}"${k===tab?' aria-current="page"':''}>${n}${k==='notifications'?badge():''}</a>`).join('')}</aside><section id="pane"></section></div>`;
  await T($('#pane'));
}
async function bookings(el,path,title,asClient){
  const d=await api(path,{q:{limit:100}});
  const fmt={dateStyle:'medium',timeStyle:'short'};
  const done=b=>['confirmed','completed'].includes(b.status)&&b.end_at&&new Date(b.end_at)<=new Date();
  const mine={};
  if(asClient){
    const ids=[...new Set(d.bookings.filter(done).map(b=>b.announcement_id))];
    await Promise.all(ids.map(async id=>{try{(await api(`/catalog/${id}/reviews`,{q:{limit:150}})).reviews.forEach(r=>{if(r.author_id===S.me.user.id)mine[r.booking_id]=r})}catch{}}));
  }
  const row=b=>{
    const live=['pending','confirmed'].includes(b.status)&&b.start_at&&new Date(b.start_at)>new Date();
    const who=asClient?`<small>Мастер: <a data-l href="/user/${b.provider_id}">${esc(b.provider_username)}</a></small>`:`<small>Клиент: <a data-l href="/user/${b.client_id}">${esc(b.client_username)}</a></small>`;
    let act='';
    if(b.can_cancel)act=`<button class="btn sm bad" data-cancel="${b.id}" data-as="${asClient?'client':'provider'}">Отменить</button>`;
    else if(asClient&&mine[b.id])act=`<span class="mine">Ваша оценка ${stars(mine[b.id].rating)}</span>`;
    else if(asClient&&done(b))act=`<button class="btn sm sun" data-review="${b.id}" data-anc="${b.announcement_id}" data-name="${esc(b.announcement_name)}">Оставить отзыв</button>`;
    else if(live&&asClient)act=`<small>Отмена была возможна до ${D(new Date(new Date(b.start_at)-b.cancel_before_hours*36e5),fmt)}</small>`;
    return `<div class="row"><div><b>${esc(b.announcement_name)}</b><small>${b.start_at?D(b.start_at,{dateStyle:'long',timeStyle:'short'}):'Время не выбрано'}</small>${who}${b.can_cancel&&asClient?`<small>Бесплатная отмена до ${D(new Date(new Date(b.start_at)-b.cancel_before_hours*36e5),fmt)}</small>`:''}</div><div class="act"><b>${RUB(b.price)}</b> <span class="st ${esc(b.status)}">${ST[b.status]||esc(b.status)}</span>${act}</div></div>`;
  };
  el.innerHTML=`<div class="h2"><h2>${title}</h2></div>`+(d.bookings.length?d.bookings.map(row).join(''):E(asClient?'Записей пока нет':'Пока никто не записался',asClient?'<a data-l href="/">Выберите услугу в каталоге</a>':'Когда клиенты запишутся, они появятся здесь.'));
}
async function cancelBooking(b){
  const asClient=b.dataset.as==='client';
  if(!confirm(asClient?'Отменить запись? Время освободится, мастер получит уведомление.':'Отменить запись клиента? Клиент получит уведомление.'))return;
  b.disabled=true;
  try{
    const r=await api(asClient?`/me/my_bookings/${b.dataset.cancel}/cancel`:`/me/my_announcements/booked/${b.dataset.cancel}/cancel`,{method:'POST'});
    toast(r.msg);
  }catch(e){toast(e.message,1)}
  render();
}
async function announcements(el){
  let st='active';
  const draw=()=>{
    el.innerHTML=`<div class="h2"><h2>Мои услуги</h2><button class="btn sm" id="nw">Новая услуга</button></div>
<div class="tabs"><button aria-pressed="${st==='active'}" data-s="active">Активные</button><button aria-pressed="${st==='archived'}" data-s="archived">Архив</button></div><div id="gl" class="grid" style="margin-top:0"></div><div class="more"><button class="btn ghost" id="mr" hidden>Показать ещё</button></div>`;
    $$('[data-s]',el).forEach(b=>b.onclick=()=>{st=b.dataset.s;draw()});
    $('#nw').onclick=create;
    grid($('#gl'),$('#mr'),async(offset,limit)=>(await api(`/me/my_announcements/${st}`,{q:{limit,offset}})).announcements,
      {by:false,like:false,empty:st==='active'?'Активных услуг нет':'Архив пуст',hint:st==='active'?'Нажмите «Новая услуга», чтобы опубликовать первую.':'',extra:a=>st==='active'?`<button class="btn sm bad" data-arch="${a.id}">В архив</button>`:''});
  };
  const create=()=>{
    modal('<h2>Новая услуга</h2>'+F('cf',[['name','Название','text','minlength="3" maxlength="100"'],['type','Тип услуги','text','maxlength="100" placeholder="Например, маникюр"'],['price','Цена, ₽','number','min="0" value="1000"'],['duration_minutes','Длительность, мин','number','min="1" value="60"'],['cancel_before_hours','Отмена не позднее чем за, ч','number','min="1" value="24"']],'Опубликовать').replace('<p class="err"','<label>Описание<textarea name="description" rows="3" maxlength="1000"></textarea></label><p class="err"'));
    dlg.showModal();
    submit('cf',async d=>{await api('/me/my_announcements/create',{method:'POST',body:{...d,status:'active',price:+d.price,duration_minutes:+d.duration_minutes,cancel_before_hours:+d.cancel_before_hours}});dlg.close();toast('Опубликовано');st='active';draw()});
  };
  announcements.redraw=draw;draw();
}
async function archive(id){
  if(!confirm('Отправить услугу в архив? Клиенты перестанут её видеть.'))return;
  try{const r=await api(`/me/my_announcements/${id}/archive`,{method:'POST'});toast(r.msg);render()}catch(e){toast(e.message,1)}
}
async function favourites(el){
  el.innerHTML='<div class="h2"><h2>Избранное</h2></div><div id="gl" class="grid" style="margin-top:0"></div><div class="more"><button class="btn ghost" id="mr" hidden>Показать ещё</button></div>';
  await grid($('#gl'),$('#mr'),async(offset,limit)=>(await api('/me/my_favourites',{q:{limit,offset}})).announcements,{empty:'В избранном пусто',hint:'Нажмите на сердце у услуги, чтобы вернуться к ней позже.'});
}
async function notifications(el){
  let k='incoming';
  const draw=async()=>{
    const d=await api('/me/my_notifications/'+k),inc=k==='incoming',n0=inc?d.notifications.filter(n=>!n.is_read).length:0;
    if(inc)setUnread(n0);
    el.innerHTML=`<div class="h2"><h2>Уведомления</h2>${n0?'<button class="btn sm ghost" id="ra">Прочитать все</button>':''}</div><div class="tabs"><button data-k="incoming" aria-pressed="${inc}">Входящие</button><button data-k="sent" aria-pressed="${!inc}">Отправленные</button></div>`+
      (d.notifications.length?d.notifications.map(n=>{const nw=inc&&!n.is_read;return `<div class="row${nw?' unread':''}"${nw?` data-read="${n.id}" tabindex="0"`:''}><div><b>${nw?'<span class="dot" role="img" aria-label="Новое"></span>':''}${esc(n.title)}</b><small style="white-space:pre-wrap;color:var(--text)">${esc(n.text)}</small></div><small>${D(n.created_at,{dateStyle:'medium',timeStyle:'short'})}</small></div>`}).join(''):E('Здесь пока тихо','Уведомления о записях появятся в этом списке.'));
    $$('[data-k]',el).forEach(b=>b.onclick=()=>{k=b.dataset.k;draw()});
    const ra=$('#ra',el);if(ra)ra.onclick=async()=>{try{await api('/me/my_notifications/read_all',{method:'POST'});draw()}catch(e){toast(e.message,1)}};
    const mark=async r=>{try{await api(`/me/my_notifications/incoming/${r.dataset.read}/read`,{method:'POST'});r.classList.remove('unread');r.removeAttribute('data-read');r.removeAttribute('tabindex');$('.dot',r)?.remove();setUnread(Math.max(0,S.unread-1));if(!$('[data-read]',el))$('#ra',el)?.remove()}catch(e){toast(e.message,1)}};
    $$('[data-read]',el).forEach(r=>{r.onclick=()=>mark(r);r.onkeydown=e=>{if(e.key==='Enter')mark(r)}});
  };
  await draw();
}
async function calendar(el){
  const iso=d=>d.toLocaleDateString('sv');
  let from=new Date();from.setHours(0,0,0,0);from.setDate(from.getDate()-(from.getDay()+6)%7);
  const draw=async()=>{
    const d=await api('/account/me/calendar',{q:{date_from:iso(from),days:7}}),today=iso(new Date());
    const hm=t=>t.slice(0,5),dd=s=>new Date(s+'T12:00:00');
    const item=i=>i.kind==='free'
      ?`<div class="cit free"><b>${i.start}–${i.end}</b><span>Свободно</span></div>`
      :`<div class="cit busy ${i.role}"><b>${i.start}–${i.end}</b><span>${esc(i.announcement_name)}</span><small>${i.role==='provider'?'Клиент':'Мастер'}: <a data-l href="/user/${i.counterpart_id}">${esc(i.counterpart_username)}</a></small>${i.status==='pending'?'<span class="st pending">Ожидает</span>':''}</div>`;
    const day=x=>`<section class="cday${x.date===today?' today':''}"><h3>${dd(x.date).toLocaleDateString('ru-RU',{weekday:'short',day:'numeric',month:'short'})}</h3><small class="muted">${x.window_start?hm(x.window_start)+'–'+hm(x.window_end):'Нет приёма'}</small>${x.items.length?x.items.map(item).join(''):'<p class="hint">Выходной</p>'}</section>`;
    const last=d.days[d.days.length-1].date;
    el.innerHTML=`<div class="h2"><h2>Календарь</h2><div class="cnav"><button class="btn sm ghost" id="pv" aria-label="Предыдущая неделя">←</button><button class="btn sm ghost" id="td">Сегодня</button><button class="btn sm ghost" id="nx" aria-label="Следующая неделя">→</button></div></div>
<p class="hint" style="margin-bottom:6px">${dd(d.days[0].date).toLocaleDateString('ru-RU',{day:'numeric',month:'long'})} — ${dd(last).toLocaleDateString('ru-RU',{day:'numeric',month:'long',year:'numeric'})}</p>
<div class="legend"><span class="chip">Записи ко мне</span><span class="chip" style="background:#FFEFC0">Я записан к мастеру</span><span class="chip cfree">Свободно</span></div>
${d.has_operating_mode?'':'<p class="hint" style="margin-top:10px">Режим работы не задан, поэтому свободные окна не показываются. <a data-l href="/me/schedule">Задать режим работы</a></p>'}
<div class="cal">${d.days.map(day).join('')}</div>`;
    const go7=n=>{from.setDate(from.getDate()+n);draw().catch(e=>toast(e.message,1))};
    $('#pv',el).onclick=()=>go7(-7);$('#nx',el).onclick=()=>go7(7);
    $('#td',el).onclick=()=>{from=new Date();from.setHours(0,0,0,0);from.setDate(from.getDate()-(from.getDay()+6)%7);draw().catch(e=>toast(e.message,1))};
  };
  await draw();
}
async function schedule(el){
  const {rules}=await api('/account/me/operating_mode'),m=Object.fromEntries(rules.map(r=>[r.weekday,r]));
  el.innerHTML=`<div class="h2"><h2>Режим работы</h2></div><p class="hint" style="margin-bottom:12px">Когда клиенты могут записаться к вам. В дни без окна запись недоступна.</p><div class="panel" style="padding:12px 24px">${DAYS.map((n,i)=>{const r=m[i];return `<form class="wk${r?'':' off'}" data-wd="${i}"><b>${n}</b><input type="time" name="start_time" aria-label="Начало" value="${r?r.start_time.slice(0,5):'09:00'}" required><input type="time" name="end_time" aria-label="Конец" value="${r?r.end_time.slice(0,5):'18:00'}" required><span style="display:flex;gap:6px"><button class="btn sm">Сохранить</button>${r?'<button type="button" class="btn sm bad" data-rm>Убрать</button>':''}</span></form>`}).join('')}</div>`;
  $$('.wk',el).forEach(f=>{const i=+f.dataset.wd;
    f.onsubmit=async e=>{e.preventDefault();try{await api('/account/me/operating_mode',{method:'PUT',body:{weekday:i,...Object.fromEntries(new FormData(f))}});toast(DAYS[i]+': сохранено');schedule(el)}catch(x){toast(x.message,1)}};
    const rm=$('[data-rm]',f);if(rm)rm.onclick=async()=>{try{await api('/account/me/operating_mode/'+i,{method:'DELETE'});toast(DAYS[i]+': день убран');schedule(el)}catch(x){toast(x.message,1)}};
  });
}
async function settings(el){
  await loadMe();const {user:u,settings:s}=S.me,base='/me/account/settings/security';
  const tg=(id,t,on,h)=>`<div class="panel" style="margin-top:14px"><h3 style="font-size:17px;margin-bottom:6px">${t}</h3><p class="hint" style="margin-bottom:12px">${h}</p>`+F(id,[['password','Текущий пароль','password','autocomplete="current-password"']],on?'Выключить':'Включить')+'</div>';
  el.innerHTML=`<div class="h2"><h2>Настройки</h2><button class="btn sm ghost" id="lo">Выйти</button></div>
<div class="panel"><b>${esc(u.username)}</b><p class="hint" style="margin:4px 0 0">${esc(u.email)}</p></div>
${tg('f2',s.two_factor_enabled?'Двухфакторная защита включена':'Двухфакторная защита выключена',s.two_factor_enabled,'При входе мы будем присылать код на почту.')}
${tg('fs',s.show_email?'Почта видна другим':'Почта скрыта',s.show_email,'Покажем почту в вашем публичном профиле.')}
<div class="panel" style="margin-top:14px"><h3 style="font-size:17px;margin-bottom:12px">Смена пароля</h3>${F('fp',[['password','Текущий пароль','password','autocomplete="current-password"'],['new_password','Новый пароль','password','minlength="6" maxlength="20" autocomplete="new-password"']],'Сменить пароль')}</div>`;
  const tog=(id,path)=>submit(id,async d=>{const r=await api(base+path,{method:'POST',body:d});toast(r.msg);settings(el)});
  tog('f2','/2fa');tog('fs','/show_email');
  submit('fp',async d=>{const r=await api(base+'/change_password',{method:'POST',body:d});toast(r.msg);$('#fp').reset()});
  $('#lo').onclick=async()=>{await api('/logout',{method:'POST'}).catch(()=>{});S.me=null;S.likes=new Set();toast('Вы вышли из аккаунта');go('/')};
}

loadMe().then(render);