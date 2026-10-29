'use strict';
const $=(s,e=document)=>e.querySelector(s),$$=(s,e=document)=>[...e.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const app=$('#app'),dlg=$('#dlg'),S={me:null,likes:new Set(),names:{}};
const RUB=n=>new Intl.NumberFormat('ru-RU').format(n)+' ₽';
const dur=m=>m<60?m+' мин':Math.floor(m/60)+' ч'+(m%60?' '+m%60+' мин':'');
const D=(s,o)=>new Date(s).toLocaleString('ru-RU',o);
const DAYS=['Понедельник','Вторник','Среда','Четверг','Пятница','Суббота','Воскресенье'];
const ST={pending:'Ожидает',confirmed:'Подтверждена',cancelled:'Отменена',completed:'Завершена'};
const HEART='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-7-4.6-9.3-9.1C1.1 8.6 2.9 5 6.4 5c2 0 3.4 1.1 4.1 2.3h3C14.2 6.100 15.600 5 17.600 5c3.500 0 5.300 3.600 3.700 6.900C19 16.400 12 21 12 21z"/></svg>';
const E=(h,p='')=>`<div class="empty"><h2>${h}</h2><p>${p}</p></div>`;
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
async function loadMe(){
  try{S.me=await api('/account/me')}catch{S.me=null;S.likes=new Set();return}
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
  $('#nav').innerHTML=L('/','Каталог')+(S.me?L('/me/bookings','Мои записи')+L('/me/notifications','Уведомления')+L('/me/announcements',esc(S.me.user.username),'btn sm'):L('/login','Войти')+L('/register','Регистрация','btn sm'));
}
addEventListener('popstate',render);
document.addEventListener('click',e=>{
  const l=e.target.closest('a[data-l]');
  if(l&&!e.metaKey&&!e.ctrlKey&&!e.shiftKey){e.preventDefault();if(dlg.open)dlg.close();return go(l.getAttribute('href'))}
  if(e.target.closest('[data-close]')||e.target===dlg)return dlg.close();
  const lk=e.target.closest('[data-like]');if(lk)return like(lk);
  const ar=e.target.closest('[data-arch]');if(ar)return archive(ar.dataset.arch);
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
<p class="by">Мастер: <a data-l href="/user/${a.user_id}">${esc(S.names[a.user_id])}</a></p>${a.description?`<p class="desc">${esc(a.description)}</p>`:''}<div class="foot"><b>${RUB(a.price)}</b></div><div id="bk"></div>`);
    await booking(a,$('#bk'));
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
const TABS=[['bookings','Мои записи'],['requests','Записи ко мне'],['announcements','Мои услуги'],['favourites','Избранное'],['notifications','Уведомления'],['schedule','Режим работы'],['settings','Настройки']];
async function account(tab='bookings'){
  if(!S.me)return go('/login',1);
  const T={bookings:el=>bookings(el,'/me/my_bookings','Мои записи',1),requests:el=>bookings(el,'/me/my_announcements/booked','Записи ко мне',0),announcements,favourites,notifications,schedule,settings}[tab];
  if(!T)return go('/me/bookings',1);
  app.innerHTML=`<div class="layout"><aside class="side" aria-label="Личный кабинет">${TABS.map(([k,n])=>`<a data-l href="/me/${k}"${k===tab?' aria-current="page"':''}>${n}</a>`).join('')}</aside><section id="pane"></section></div>`;
  await T($('#pane'));
}
async function bookings(el,path,title,asClient){
  const d=await api(path,{q:{limit:100}});
  el.innerHTML=`<div class="h2"><h2>${title}</h2></div>`+(d.bookings.length?d.bookings.map(b=>`<div class="row"><div><b>${esc(b.announcement_name)}</b><small>${b.start_at?D(b.start_at,{dateStyle:'long',timeStyle:'short'}):'Время не выбрано'}</small>${asClient?`<small>Мастер: <a data-l href="/user/${b.provider_id}">${esc(b.provider_username)}</a></small>`:''}</div><div><b>${RUB(b.price)}</b> <span class="st ${esc(b.status)}">${ST[b.status]||esc(b.status)}</span></div></div>`).join(''):E(asClient?'Записей пока нет':'Пока никто не записался',asClient?'<a data-l href="/">Выберите услугу в каталоге</a>':'Когда клиенты запишутся, они появятся здесь.'));
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
    const d=await api('/me/my_notifications/'+k);
    el.innerHTML=`<div class="h2"><h2>Уведомления</h2></div><div class="tabs"><button data-k="incoming" aria-pressed="${k==='incoming'}">Входящие</button><button data-k="sent" aria-pressed="${k==='sent'}">Отправленные</button></div>`+
      (d.notifications.length?d.notifications.map(n=>`<div class="row"><div><b>${esc(n.title)}</b><small style="white-space:pre-wrap;color:var(--text)">${esc(n.text)}</small></div><small>${D(n.created_at,{dateStyle:'medium',timeStyle:'short'})}</small></div>`).join(''):E('Здесь пока тихо','Уведомления о записях появятся в этом списке.'));
    $$('[data-k]',el).forEach(b=>b.onclick=()=>{k=b.dataset.k;draw()});
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