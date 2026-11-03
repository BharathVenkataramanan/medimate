
(() => {
  'use strict';
  let lang = localStorage.getItem('mm_lang') || 'en';
  if (!window.I18N[lang]) lang = 'en';
  let db, medicines = [], doseRecords = [], allMedicines=[], allDoses=[], people=[], currentProfile=localStorage.getItem('mm_profile')||'self', currentPage = 'home', sending = false;
  let interactionSeq=0, interactionReport=null, chosenDay='', chosenMonth='';
  let onlineReport=null, onlineSeq=0, onlineKey='', onlineFetchedAt=0, onlinePendingKey='';
  let onlineConsent=true;
  let suggestionSeq=0, suggestionTimer=null, suggestionItems=[], selectedSuggestion=-1;
  let selectedRxNorm=null;
  const selectedRxNormIds=()=>Object.fromEntries(medicines.filter(m=>m.rxnormId && /^\d{1,12}$/.test(m.rxnormId)).map(m=>[m.name,m.rxnormId]));
  let previousConflictSignature = null;
  let interactionReviews = new Map();
  let safetyAudioContext = null;
  let safetyAudioEnabled = false;
  const safetyReviewStore = 'interactionReviews';
  function unlockSafetyAudio() {
    if (safetyAudioEnabled) return;
    const Audio = window.AudioContext || window.webkitAudioContext;
    if (!Audio) return;
    try {
      safetyAudioContext = safetyAudioContext || new Audio();
      void safetyAudioContext.resume().then(()=>{safetyAudioEnabled=true;}).catch(()=>{});
    } catch (_) {                                               }
  }
  function gentleSafetyChime() {
    if (!safetyAudioEnabled || !safetyAudioContext || safetyAudioContext.state!=='running') return;
    try {
      const now=safetyAudioContext.currentTime;
      for (const [i,frequency] of [523.25,659.25].entries()) {
        const tone=safetyAudioContext.createOscillator();
        const gain=safetyAudioContext.createGain();
        tone.type='sine';tone.frequency.value=frequency;
        gain.gain.setValueAtTime(0.0001,now+i*0.13);
        gain.gain.exponentialRampToValueAtTime(0.023,now+i*0.13+0.018);
        gain.gain.exponentialRampToValueAtTime(0.0001,now+i*0.13+0.22);
        tone.connect(gain);gain.connect(safetyAudioContext.destination);
        tone.start(now+i*0.13);tone.stop(now+i*0.13+0.24);
      }
    } catch (_) {                                            }
  }
  function gentleMedicinePing(){
    // Original two-tone acknowledgement sound, not an external audio download.
    // Browsers require a prior user interaction before Web Audio can play.
    if(!safetyAudioEnabled||!safetyAudioContext||safetyAudioContext.state!=='running')return false;
    try{
      const now=safetyAudioContext.currentTime;
      for(const [i,freq] of [740,988,880].entries()){
        const tone=safetyAudioContext.createOscillator(), gain=safetyAudioContext.createGain();
        tone.type='sine';tone.frequency.value=freq;
        const start=now+i*.22;
        gain.gain.setValueAtTime(.0001,start);
        gain.gain.exponentialRampToValueAtTime(.14,start+.035);
        gain.gain.exponentialRampToValueAtTime(.0001,start+.32);
        tone.connect(gain);gain.connect(safetyAudioContext.destination);
        tone.start(start);tone.stop(start+.33);
      }
      return true;
    }catch(_){return false;}
  }
  let quietAfterArchive = false;
  let pendingFamilyDelete = null;
  let deletingFamily = false;
  const $ = id => document.getElementById(id);
  const t = key => (window.I18N[lang] && window.I18N[lang][key]) || window.I18N.en[key] || key;
  const elt = (tag, cls, text) => { const node=document.createElement(tag); if(cls) node.className=cls; if(text!==undefined) node.textContent=text; return node; };
  const localDate = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  const localStamp = (d = new Date()) => `${localDate(d)}T${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`;
  const activationFor = (med,time) => {
    if(typeof med.reminderActivatedAt?.[time]==='string')return med.reminderActivatedAt[time];
    const edited=med.updatedAt?new Date(med.updatedAt):null;
    return edited&&Number.isFinite(edited.getTime())?localStamp(edited):localStamp();
  };
  const reminderReady = (med,day,time) => `${day}T${time}:00`>=activationFor(med,time);
  const notifyKey = (mId,day,time) => `${mId}|${day}|${time}`;
  const schedule = window.MedimateSchedule;
  const sortTimes = times => [...new Set(times)].sort((a,b)=>a.localeCompare(b));
  const doseUnits=new Set(['tablet','capsule','mL','drop','puff','sachet','patch','spray','other']);
  const doseDescription=(m, language=lang) => {
    if(m.quantity==null || m.quantity==='' || !Number.isFinite(Number(m.quantity)) || Number(m.quantity)<=0)return '';
    const qty=Number(m.quantity); const unit=m.doseUnit||'tablet';
    if(!doseUnits.has(unit))return '';
    const singular=qty===1;
    const map={en:{tablet:['tablet','tablets'],capsule:['capsule','capsules'],mL:['mL','mL'],drop:['drop','drops'],puff:['puff','puffs'],sachet:['sachet','sachets'],patch:['patch','patches'],spray:['spray','sprays'],other:['unit','units']},
      ta:{tablet:['மாத்திரை','மாத்திரைகள்'],capsule:['காப்ஸ்யூல்','காப்ஸ்யூல்கள்'],mL:['மி.லி.','மி.லி.'],drop:['சொட்டு','சொட்டுகள்'],puff:['உள்ளிழுப்பு','உள்ளிழுப்புகள்'],sachet:['பொட்டலம்','பொட்டலங்கள்'],patch:['ஒட்டுப் பட்டை','ஒட்டுப் பட்டைகள்'],spray:['தெளிப்பு','தெளிப்புகள்'],other:['அலகு','அலகுகள்']},
      zh:{tablet:['片','片'],capsule:['粒胶囊','粒胶囊'],mL:['毫升','毫升'],drop:['滴','滴'],puff:['吸','吸'],sachet:['袋','袋'],patch:['贴','贴'],spray:['喷','喷'],other:['单位','单位']},
      ms:{tablet:['tablet','tablet'],capsule:['kapsul','kapsul'],mL:['mL','mL'],drop:['titis','titis'],puff:['sedutan','sedutan'],sachet:['sachet','sachet'],patch:['tampalan','tampalan'],spray:['semburan','semburan'],other:['unit','unit']}};
    const word=(map[language]||map.en)[unit][singular?0:1];return language==='zh'?`${qty}${word}`:`${qty} ${word}`;
  };
  const reminderText=(m,language=lang)=>{
    const amount=doseDescription(m,language), notes=(m.notes||'').trim();
    const core=language==='ta'?(amount?`${m.name} மருந்தின் ${amount} எடுத்துக்கொள்ள நினைவூட்டல்`:`${m.name} எடுத்துக்கொள்ள நினைவூட்டல்`):
      language==='zh'?(amount?`提醒服用 ${m.name} ${amount}`:`提醒服用 ${m.name}`):
      language==='ms'?(amount?`Peringatan untuk mengambil ${amount} ${m.name}`:`Peringatan untuk mengambil ${m.name}`):
      amount?`Reminder to take ${amount} of ${m.name}`:`Reminder to take ${m.name}`;
    return notes?`${core}\n${notes}`:core;
  };
  let toastTimer;
  let macEnabled=false, macInstalled=false, macSupported=false, macSyncTimer=null, macSyncBusy=false;
  let appStopping=false;


  function toast(message) {
    const el=$('toast');el.textContent=message;el.classList.add('show');
    clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove('show'),4000);
  }

  function database() {
    return new Promise((resolve,reject)=>{
      const request=indexedDB.open('medimate-local-v1',3);
      request.onupgradeneeded=()=>{
        const db=request.result;
        if(!db.objectStoreNames.contains('medicines'))db.createObjectStore('medicines',{keyPath:'id'});
        if(!db.objectStoreNames.contains('doses'))db.createObjectStore('doses',{keyPath:'id'});
        if(!db.objectStoreNames.contains('people'))db.createObjectStore('people',{keyPath:'id'});
        if(!db.objectStoreNames.contains(safetyReviewStore))db.createObjectStore(safetyReviewStore,{keyPath:'id'});
      };
      request.onsuccess=()=>resolve(request.result);
      request.onerror=()=>reject(request.error);
    });
  }
  function tx(name,mode,run) {
    return new Promise((resolve,reject)=>{
      const tr=db.transaction(name,mode);const store=tr.objectStore(name);
      let result; let req;
      try {req=run(store); } catch(e){reject(e);return;}
      if(req){req.onsuccess=()=>{result=req.result;};req.onerror=()=>reject(req.error);}
      tr.oncomplete=()=>resolve(result);
      tr.onerror=()=>reject(tr.error);
      tr.onabort=()=>reject(tr.error);
    });
  }
  async function refresh() {
    people=await tx('people','readonly',st=>st.getAll());
    if(!people.some(p=>p.id==='self')) {await tx('people','readwrite',st=>st.put({id:'self',name:t('meLabel'),system:true}));people=await tx('people','readonly',st=>st.getAll());}
    if(!people.some(p=>p.id===currentProfile))currentProfile='self';
    allMedicines=await tx('medicines','readonly',st=>st.getAll());
    allDoses=await tx('doses','readonly',st=>st.getAll());
    interactionReviews = new Map((await tx(safetyReviewStore,'readonly',st=>st.getAll())).map(x=>[x.id,x]));

    medicines=allMedicines.filter(m=>(m.profileId||'self')===currentProfile && m.active!==false);
    doseRecords=allDoses.filter(d=>(d.profileId||'self')===currentProfile);
    medicines.sort((a,b)=>a.name.localeCompare(b.name));
    renderProfiles();render();scheduleMacSync();
  }
  function macPayload(enabled=true){
    return {enabled,profiles:people.map(p=>({id:p.id,name:p.id==='self'?t('meLabel'):p.name,language:lang,
      medicines:allMedicines.filter(m=>(m.profileId||'self')===p.id && m.active!==false).map(m=>({
        id:m.id,name:m.name,quantity:m.quantity??null,doseUnit:m.doseUnit||'',notes:m.notes||'',startDate:m.startDate||m.updatedAt?.slice(0,10)||localDate(),
        courseEndDate:m.courseEndDate||'',times:m.times,
        reminderActivatedAt:Object.fromEntries((m.times||[]).map(time=>[time,activationFor(m,time)])),schedule:m.schedule||{frequency:'daily'},
        scheduleVersions:m.scheduleVersions||[],periods:m.periods||[]
      }))
    })),taken:allDoses.filter(d=>(d.status==='taken'||!d.status)).slice(-800).map(d=>d.id)};
  }
  async function postMacPayload(enabled){
    const response=await fetch('/api/reminders/sync',{method:'POST',headers:{'Content-Type':'application/json','X-MediMate-Request':'1'},body:JSON.stringify(macPayload(enabled))});
    if(!response.ok)throw new Error('sync_failed');
  }
  function updateMacStatus(message){
    const btn=$('mac-reminders-toggle');
    if(!btn)return;
    btn.textContent=t(macEnabled?'macDisable':!macInstalled?'macInstallEnable':'macEnable');
    $('mac-reminders-status').textContent=message||t(!macSupported?'macNotMac':!macInstalled?'macUnavailable':macEnabled?'macReady':'macOff');
    btn.disabled=macSyncBusy || !macSupported;
  }
  async function readMacStatus(){
    try{
      const response=await fetch('/api/reminders/status');
      if(!response.ok)throw new Error('status');
      const status=await response.json();
      macSupported=Boolean(status.supported);macInstalled=Boolean(status.helper_installed);macEnabled=Boolean(status.enabled&&status.helper_installed);
      updateMacStatus();
      if(macEnabled) scheduleMacSync();
    }catch(_){macSupported=false;updateMacStatus(t('macSyncFailed'));}
  }
  function scheduleMacSync(){
    if(!macEnabled||appStopping)return;
    clearTimeout(macSyncTimer);
    macSyncTimer=setTimeout(async()=>{
      if(!macEnabled||appStopping)return;
      try {await postMacPayload(true);if(!appStopping)updateMacStatus();}
      catch(_){if(!appStopping)updateMacStatus(t('macSyncFailed'));}
    },650);
  }
  async function toggleMacReminders(){
    if(!macSupported||macSyncBusy||appStopping)return;
    const newValue=!macEnabled;
    // Background helpers are included in the one-download repository.
    // Explicit consent is required before registering an OS background task.
    if(newValue&&!window.confirm(t('macInstallConfirm')))return;
    macSyncBusy=true;updateMacStatus(t('macSyncing'));
    let failed=false;
    try {
      if(newValue){
        const response=await fetch('/api/reminders/install',{
          method:'POST',
          headers:{'Content-Type':'application/json','X-MediMate-Request':'1'},
          body:JSON.stringify({confirm:true})
        });
        if(!response.ok)throw new Error('install_failed');
        const result=await response.json();
        if(!result.installed)throw new Error('install_unverified');
        macInstalled=true;
      }else clearTimeout(macSyncTimer);
      await postMacPayload(newValue);
      macEnabled=newValue;
    }catch(_){failed=true;}
    finally{macSyncBusy=false;updateMacStatus(failed?t('macSyncFailed'):undefined);}
  }
  async function stopMedimate(){
    if(appStopping||!window.confirm(t('stopAppConfirm')))return;
    const button=$('stop-medimate');
    button.disabled=true;
    $('stop-medimate-status').textContent=t('stopAppStopping');
    appStopping=true;
    clearTimeout(macSyncTimer);
    try{
      const response=await fetch('/api/app/stop',{
        method:'POST',headers:{'Content-Type':'application/json','X-MediMate-Request':'1'},
        body:JSON.stringify({confirm:true})
      });
      if(!response.ok)throw Error('stop_failed');
      const result=await response.json();
      if(result.stopped!==true||result.reminders_disabled!==true)throw Error('stop_incomplete');
      macEnabled=false;macInstalled=false;
      const screen=elt('main','stopped-app-screen');
      const card=elt('section','paper-card stopped-app-card');
      card.append(elt('h1','',t('stopAppDoneTitle')),elt('p','',t('stopAppDoneDesc')));
      screen.append(card);
      document.body.replaceChildren(screen);
    }catch(_){
      appStopping=false;button.disabled=false;
      $('stop-medimate-status').textContent=t('stopAppFailed');
    }
  }
  function profileName(){return people.find(p=>p.id===currentProfile)?.name||t('meLabel');}
  function renderProfiles(){
    const picker=$('profile-selector');picker.replaceChildren();
    for(const p of people){const option=elt('option','',p.id==='self'?t('meLabel'):p.name);option.value=p.id;picker.append(option);}
    picker.value=currentProfile;
    $('active-profile-caption').textContent=profileName();
  }
  async function switchProfile(id){
    if(!people.some(p=>p.id===id))return;
    currentProfile=id;expandedCalendarDays.clear();calendarExpanded=false;localStorage.setItem('mm_profile',id);previousConflictSignature=null;quietAfterArchive=false;interactionReport=null;

    updateConflictNotice([],[],[]);
    onlineReport=null;onlineKey='';onlinePendingKey='';onlineFetchedAt=0;++onlineSeq;await refresh();
  }
  function renderFamily(){
    const root=$('family-list');root.replaceChildren();
    for(const person of people){
      const row=elt('article','paper-card family-card');
      const info=elt('div');info.append(elt('h3','',person.id==='self'?t('meLabel'):person.name));
      const n=allMedicines.filter(m=>(m.profileId||'self')===person.id && m.active!==false).length;
      info.append(elt('p','',`${n} ${t('navMeds').toLowerCase()}`));row.append(info);
      const buttons=elt('div','family-buttons');
      const select=elt('button','outline-button',person.id===currentProfile?t('selectedProfile'):t('chooseProfile'));
      select.disabled=person.id===currentProfile;select.addEventListener('click',()=>switchProfile(person.id));buttons.append(select);
      if(person.id!=='self'){
        const remove=elt('button','family-remove-button',t('removeFamily'));
        remove.type='button';
        remove.setAttribute('aria-label',`${t('removeFamily')}: ${person.name}`);
        remove.addEventListener('click',()=>openFamilyDelete(person));buttons.append(remove);
      }
      row.append(buttons);root.append(row);
    }
  }
  function openFamilyDelete(person){

    if(!person || person.id==='self' || !people.some(p=>p.id===person.id) || deletingFamily)return;
    pendingFamilyDelete=person.id;
    const medCount=allMedicines.filter(m=>(m.profileId||'self')===person.id).length;
    const doseCount=allDoses.filter(d=>(d.profileId||'self')===person.id).length;
    $('family-delete-title').textContent=t('familyRemoveTitle').replace('{name}',person.name);
    $('family-delete-impact').textContent=t('familyDeleteImpact')
      .replace('{medicines}',String(medCount)).replace('{doses}',String(doseCount));
    $('family-delete-dialog').showModal();
    $('family-delete-cancel').focus();
  }
  async function deleteFamily(){
    if(deletingFamily || !pendingFamilyDelete || pendingFamilyDelete==='self')return;
    const id=pendingFamilyDelete;
    if(!people.some(p=>p.id===id))return;
    deletingFamily=true;
    $('family-delete-confirm').disabled=true;


    try {
      await new Promise((resolve,reject)=>{
        let tr;
        try {
          tr=db.transaction(['people','medicines','doses',safetyReviewStore],'readwrite');
          tr.oncomplete=()=>resolve();
          tr.onerror=()=>reject(tr.error||new Error('storage_error'));
          tr.onabort=()=>reject(tr.error||new Error('storage_aborted'));
          const meds=tr.objectStore('medicines');
          const doses=tr.objectStore('doses');
          const personStore=tr.objectStore('people');
          for(const med of allMedicines.filter(m=>(m.profileId||'self')===id))meds.delete(med.id);
          for(const dose of allDoses.filter(d=>(d.profileId||'self')===id))doses.delete(dose.id);
          personStore.delete(id);
          for(const review of interactionReviews.values())if(review.profileId===id)tr.objectStore(safetyReviewStore).delete(review.id);
        }catch(error){if(tr)try{tr.abort();}catch(_){}reject(error);}
      });
      $('family-delete-dialog').close();
      pendingFamilyDelete=null;
      if(currentProfile===id)currentProfile='self';
      localStorage.setItem('mm_profile',currentProfile);


      resetSafetyAfterDataReplacement();
      await refresh();
    }catch(_){toast(t('localStorageFailed'));}
    finally{deletingFamily=false;$('family-delete-confirm').disabled=false;}
  }
  async function saveFamily(event){
    event.preventDefault();const name=$('family-name').value.trim().replace(/\s+/g,' ');
    if(!name)return;
    await tx('people','readwrite',st=>st.put({id:crypto.randomUUID(),name,system:false}));
    $('family-dialog').close();$('family-form').reset();toast(t('saved'));await refresh();
  }
  function switchPage(page) {
    if(!['home','medicines','adherence','family','interactions','chat','settings'].includes(page)) page='home';
    currentPage=page;


    if(page!=='interactions') hideConflictToast();
    document.querySelectorAll('.page').forEach(el=>el.classList.toggle('active',el.id===`page-${page}`));
    document.querySelectorAll('.nav-link').forEach(el=>{
      const active=el.dataset.page===page;el.classList.toggle('active',active);if(active)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');
    });
    window.scrollTo({top:0,behavior:'auto'});

    const section=document.getElementById(`page-${page}`);
    const heading=section && [...section.querySelectorAll('h1')].find(el=>!el.closest('[hidden]'));
    if(heading && typeof heading.focus==='function') {
      heading.setAttribute('tabindex','-1');heading.focus({preventScroll:true});
    }
    if(page==='settings') updateNotifyStatus();
    if(page==='adherence') renderAdherence();
  }
  function translate() {
    document.documentElement.lang=lang==='zh'?'zh-Hans':lang;
    document.querySelectorAll('[data-i18n]').forEach(el=>{
      const key=el.dataset.i18n;

      el.textContent=t(key);
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el=>el.placeholder=t(el.dataset.i18nPlaceholder));
    document.querySelectorAll('[data-i18n-aria-label]').forEach(el=>el.setAttribute('aria-label',t(el.dataset.i18nAriaLabel)));
    document.querySelectorAll('[data-i18n-title]').forEach(el=>el.setAttribute('title',t(el.dataset.i18nTitle)));
    $('language').value=lang;
    document.title=`${t('navMeds')} | MediMate`;
    $('conflict-toast-title').textContent=t('conflictToastTitle');
    $('conflict-toast-description').textContent=t('conflictToastDesc');
    $('conflict-close').setAttribute('aria-label',t('dismissWarning'));
    const active=Number($('safety-count').textContent)||0;
    document.querySelector('[data-page=interactions]').setAttribute('aria-label',active?`${t('navSafety')}: ${active} ${t('conflictCountLabel')}`:t('navSafety'));
    if(!$('medicine-dialog').open) $('dialog-title').textContent=t('dialogTitle');
    if(people.length)renderProfiles();
    if(onlineReport)displayOnlineReport();
  }
  function emptyState(title,body) {
    const root=elt('div','empty-state');root.append(elt('span','empty-icon','✳'),elt('strong','',t(title)),elt('p','',t(body)));return root;
  }
  function doseDone(id) {return doseRecords.some(x=>x.id===id && (x.status==='taken'||!x.status));}
  function todayDoses() {
    const today=localDate();
    return medicines.flatMap(m=>schedule.timesOn(m,today).map(time=>({med:m,time,id:notifyKey(m.id,today,time),done:doseDone(notifyKey(m.id,today,time))}))).sort((a,b)=>a.time.localeCompare(b.time)||a.med.name.localeCompare(b.med.name));
  }
  async function toggleDose(d) {
    if(doseDone(d.id)) {
      await tx('doses','readwrite',st=>st.delete(d.id)); toast(t('doseUndone'));
    } else {
      await tx('doses','readwrite',st=>st.put({id:d.id,medId:d.med.id,profileId:currentProfile,date:localDate(),time:d.time,status:'taken',takenAt:new Date().toISOString()}));toast(t('doseTaken'));
    }
    await refresh();
    void checkDue();
  }
  function renderToday() {
    const doses=todayDoses();
    $('stat-meds').textContent=String(medicines.length);
    $('stat-today').textContent=`${doses.filter(d=>d.done).length}/${doses.length}`;
    $('stat-flags').textContent=interactionCountText(interactionReport);
    const list=$('today-list');list.replaceChildren();
    const unscheduled=medicines.filter(m=>schedule.isScheduled(m,localDate())&&schedule.timesOn(m,localDate()).length===0);
    if(!doses.length&&!unscheduled.length){list.append(emptyState('emptyTodayTitle','emptyTodayText'));return;}
    doses.forEach(d=>{
      const row=elt('div','dose-row');
      row.append(elt('span','dose-time',d.time),elt('span','dose-pill','✿'));
      const info=elt('div','dose-info');info.append(elt('strong','',d.med.name),elt('small','',[doseDescription(d.med),d.med.strength].filter(Boolean).join(' · ')||t('timeLabel')));row.append(info);
      const btn=elt('button','tiny-button'+(d.done?' taken':''),t(d.done?'taken':'markTaken'));
      btn.type='button';btn.addEventListener('click',()=>toggleDose(d));row.append(btn);list.append(row);
    });
    // An untimed medicine still belongs on the home schedule. Never invent a
    // dose time, mark it missed, or create a reminder for an unset time.
    for(const med of unscheduled){
      const row=elt('div','dose-row dose-row-unscheduled');
      row.append(elt('span','dose-time','—'),elt('span','dose-pill','✿'));
      const info=elt('div','dose-info');
      info.append(elt('strong','',med.name),elt('small','',[doseDescription(med),med.strength].filter(Boolean).join(' · ')||' '));
      row.append(info,elt('small','reminder-unscheduled',t('noReminderScheduled')));
      list.append(row);
    }
  }
  function scheduleDescription(med) {
    const s=schedule.normalize(med.schedule);
    if(s.frequency==='daily')return t('freqDaily');
    if(s.frequency==='interval')return `${t('freqEvery')} ${s.everyDays} ${t('freqDays')}`;
    if(s.frequency==='weekly'){
      const keys=['weekdaysun','weekdaymon','weekdaytue','weekdaywed','weekdaythu','weekdayfri','weekdaysat'];
      const days=s.weekdays?.length?s.weekdays:[schedule.weekday(med.startDate||localDate())];
      return `${t('freqWeekly')}: ${days.map(d=>t(keys[d])).join(', ')}`;
    }
    return t('freqMonthly');
  }
  function updateFrequencyControls(){
    const freq=$('medicine-frequency').value;
    $('interval-options').hidden=freq!=='interval';
    $('weekly-options').hidden=freq!=='weekly';
    if(freq==='weekly'&&!document.querySelector('input[name="weekly-day"]:checked')){
      const date=$('medicine-start').value||localDate();
      const day=schedule.weekday(date);
      const box=document.querySelector(`input[name="weekly-day"][value="${day}"]`);
      if(box)box.checked=true;
    }
  }
  function renderMedicines() {
    const list=$('medication-list');list.replaceChildren();
    if(!medicines.length)list.append(emptyState('emptyMedsTitle','emptyMedsText'));
    for(const med of medicines){
      const card=elt('article','paper-card med-card');const top=elt('div','med-card-top');top.append(elt('span','med-symbol','✳'));
      const heading=elt('div');heading.append(elt('h3','',med.name),elt('small','',[med.strength,doseDescription(med)].filter(Boolean).join(' · ')||' '));top.append(heading);card.append(top);
      card.append(elt('p','med-notes',med.notes||' '));const times=elt('div','time-tags');
      for(const time of med.times) times.append(elt('span','time-tag','◷ '+time));
      if(!med.times.length)times.append(elt('small','reminder-unscheduled',t('noReminderScheduled')));
      card.append(times);
      card.append(elt('small','schedule-caption',scheduleDescription(med)));
      const course=schedule.progress(med,localDate());
      if(course){
        const progress=elt('div','course-progress');
        const captions=elt('div','course-progress-label');
        captions.append(elt('span','',t('durationLabel')),elt('span','',`${course.percent}%`));
        const bar=elt('div','course-track');bar.setAttribute('role','progressbar');bar.setAttribute('aria-valuemin','0');bar.setAttribute('aria-valuemax','100');bar.setAttribute('aria-valuenow',String(course.percent));bar.setAttribute('aria-label',`${med.name}: ${t('durationLabel')}`);
        const fill=elt('div','course-fill');fill.style.width=course.percent+'%';bar.append(fill);
        progress.append(captions,bar,elt('small','course-dates',`${course.start} → ${course.end}`));card.append(progress);
      }
      const actions=elt('div','med-actions');const edit=elt('button','',t('edit'));edit.addEventListener('click',()=>openEditor(med));
      const remove=elt('button','delete-med',t('archive'));remove.addEventListener('click',()=>removeMedicine(med));actions.append(edit,remove);card.append(actions);list.append(card);
    }
    const archived=allMedicines.filter(m=>(m.profileId||'self')===currentProfile && m.active===false);
    $('archived-wrapper').hidden=!archived.length;const old=$('archived-list');old.replaceChildren();
    for(const med of archived){const row=elt('article','paper-card archived-med');
      row.append(elt('strong','',med.name),elt('span','',` ${med.strength||''}`));
      const restore=elt('button','outline-button',t('restore'));restore.addEventListener('click',async()=>{
        med.active=true;delete med.endDate;med.interactionReviewVersion=(med.interactionReviewVersion||0)+1;med.periods=med.periods||[];med.periods.push({start:localDate(),end:null});await tx('medicines','readwrite',st=>st.put(med));await refresh();
      });row.append(restore);old.append(row);
    }
  }


  const actionableInteractionWarnings = alerts => (Array.isArray(alerts) ? alerts : []).filter(hit => {
    if(!hit || typeof hit !== 'object' || hit.reason === 'no_documented_pair' || hit.reason === 'level_unknown') return false;
    if(hit.finding_type === 'duplicate_ingredient') return true;
    if(hit.finding_type === 'documented_interaction') return ['Contraindicated','Major','Moderate','Minor'].includes(hit.level);
    return hit.finding_type === 'ddinter_severity_only' && ['Major','Moderate','Minor'].includes(hit.level);
  });


  const warningSeverityRank = {'Contraindicated':0,'Major':1,'Review duplicate ingredient':1,
    'Moderate':2,'Minor':3};
  const warningPairKey = hit => JSON.stringify([
    hit.finding_type==='duplicate_ingredient'?'duplicate':'interaction',
    ...[String(hit.first||'').trim().toLocaleLowerCase(),
        String(hit.second||'').trim().toLocaleLowerCase()].sort()
  ]);
  const warningLedgerKey = hit => {
    const identity = [hit.first,hit.second].map(name=>{
      const matches=medicines.filter(m=>m.name.trim().toLowerCase()===String(name||'').trim().toLowerCase());
      return matches.length===1 ? [matches[0].id,matches[0].rxnormId||'',matches[0].strength||'',matches[0].quantity??'',matches[0].doseUnit||'',matches[0].interactionReviewVersion||0].join('#') : 'name:'+String(name||'').trim().toLowerCase();
    }).sort();
    return JSON.stringify([currentProfile,hit.finding_type==='duplicate_ingredient'?'duplicate':'interaction',...identity,hit.level]);
  };
  const isReviewedWarning = hit => interactionReviews.get(warningLedgerKey(hit))?.reviewedAt != null;
  const newWarnings = alerts => mergeActionableWarnings(alerts).filter(hit=>!isReviewedWarning(hit));
  const mergeActionableWarnings = alerts => {
    const groups=new Map();
    for(const hit of actionableInteractionWarnings(alerts)){
      const key=warningPairKey(hit);
      const members=Array.isArray(hit.findings)&&hit.findings.length?hit.findings:[hit];
      if(!groups.has(key)){
        groups.set(key,{...hit,findings:[...members]});
        continue;
      }
      const pair=groups.get(key);
      pair.findings.push(...members);


      if((warningSeverityRank[hit.level]??9)<(warningSeverityRank[pair.level]??9)){
        pair.level=hit.level;
      }


      if(pair.finding_type!=='documented_interaction' && hit.finding_type==='documented_interaction'){
        pair.finding_type='documented_interaction';
        pair.effects=hit.effects;pair.advice=hit.advice;pair.rule_code=hit.rule_code;
      }
    }
    return [...groups.values()];
  };
  const interactionCountText = report => report?.status === 'ready'
    ? String(newWarnings(report.alerts).length)
    : report?.status === 'unavailable' ? '–' : '…';
  function hideConflictToast() {
    $('conflict-toast').hidden=true;
  }
  function updateConflictNotice(problems, preservePrevious=false, suppressPopup=false) {


    problems=newWarnings(problems);
    const hasNotice=problems.length>0;
    $('conflict-nav-badge').hidden=!hasNotice;
    $('conflict-stat-dot').hidden=!hasNotice;
    $('conflict-nav-badge').classList.toggle('needs-review',false);
    $('conflict-stat-dot').classList.toggle('needs-review',false);
    $('conflict-toast').classList.toggle('needs-review',false);
    $('conflict-toast').setAttribute('role',hasNotice?'alert':'status');
    $('conflict-toast').setAttribute('aria-live',hasNotice?'assertive':'polite');
    const nav=document.querySelector('[data-page="interactions"]');
    nav.setAttribute('aria-label',hasNotice?`${t('navSafety')}: ${problems.length} ${t('conflictCountLabel')}`:t('navSafety'));


    const keys=new Set(problems.map(warningLedgerKey));


    const unseen=problems.filter(hit=>!interactionReviews.has(warningLedgerKey(hit)));
    if(!hasNotice) hideConflictToast();
    else if(unseen.length && suppressPopup!==true){
      const observedAt=new Date().toISOString();
      for(const hit of unseen){
        const id=warningLedgerKey(hit);
        const entry={id,profileId:currentProfile,seenAt:observedAt,reviewedAt:null};
        interactionReviews.set(id,entry);


        void tx(safetyReviewStore,'readwrite',st=>st.put(entry)).catch(()=>{});
      }
      $('conflict-toast-title').textContent=t('conflictToastTitle');
      $('conflict-toast-description').textContent=t('conflictToastDesc');
      $('conflict-toast').hidden=false;
      gentleSafetyChime();
    }
    if(preservePrevious!==true)previousConflictSignature=keys;
  }
  let lastRequestKey='',localLookupPendingKey='',localLookupFetchedAt=0;
  async function renderInteractions(){
    const results=$('interaction-results');results.replaceChildren();
    const names=medicines.map(m=>m.name);
    const currentKey=currentProfile+'|'+names.map(n=>n+'#'+(selectedRxNormIds()[n]||'')).join('\n');
    if(currentKey!==lastRequestKey){
      ++interactionSeq;interactionReport=null;localLookupFetchedAt=0;localLookupPendingKey='';


      updateConflictNotice([],true);
      $('stat-flags').textContent='…';
      onlineReport=null;onlineKey='';onlinePendingKey='';onlineFetchedAt=0;++onlineSeq;
      const el=$('online-label-results');if(el)el.replaceChildren();
    }
    lastRequestKey=currentKey;
    if(names.length<2){interactionReport={status:'ready',alerts:[],uncertain:[],unrecognized:[],pairs_checked:0};drawInteractions();return;}

    if(names.length<=10 && (onlineKey!==currentKey || !onlineReport || Date.now()-onlineFetchedAt>15*60*1000)) {
      void checkLabelsOnline();
    }


    if(interactionReport?.status==='ready' && Date.now()-localLookupFetchedAt<5*60*1000){drawInteractions();return;}
    if(localLookupPendingKey===currentKey){if(interactionReport?.status==='ready')drawInteractions();return;}
    if(interactionReport?.status==='ready')drawInteractions();
    localLookupPendingKey=currentKey;
    $('safety-count').textContent='…';
    const seq=++interactionSeq;
    try{
      const res=await fetch('/api/interactions',{method:'POST',headers:{'Content-Type':'application/json','X-MediMate-Request':'1'},body:JSON.stringify({medicines:names,rxnorm_ids:selectedRxNormIds(),resolve_online:false})});
      if(!res.ok)throw Error('lookup');
      const output=await res.json();if(output.status!=='ready')throw Error('lookup');
      if(seq!==interactionSeq||lastRequestKey!==currentKey)return;
      interactionReport=output;
      localLookupFetchedAt=Date.now();
      if(output.unrecognized?.length)void resolveUnknownInteractions(names,currentKey,seq);
    }catch(_){if(seq!==interactionSeq)return;interactionReport={status:'unavailable',alerts:[],uncertain:[],unrecognized:[]};}
    finally{if(localLookupPendingKey===currentKey)localLookupPendingKey='';}
    if(seq===interactionSeq)drawInteractions();
  }
  async function resolveUnknownInteractions(names,key,seq){

    try{
      const res=await fetch('/api/interactions',{
        method:'POST',headers:{'Content-Type':'application/json','X-MediMate-Request':'1'},
        body:JSON.stringify({medicines:names,rxnorm_ids:selectedRxNormIds(),resolve_online:true})
      });
      if(!res.ok)return;
      const result=await res.json();
      if(seq!==interactionSeq||key!==lastRequestKey||result.status!=='ready')return;
      interactionReport=result;drawInteractions();
      if(Object.keys(result.rxnorm_resolved||{}).length && names.length<=10){
        onlineKey='';onlineReport=null;onlineFetchedAt=0;

        if(onlinePendingKey!==key)void checkLabelsOnline();
      }
    }catch(_){                                                              }
  }

  async function checkLabelsOnline(){
    const list=$('online-label-results');
    if(!onlineConsent || medicines.length<2 || medicines.length>10)return;
    const names=medicines.map(m=>m.name);
    const key=currentProfile+'|'+names.map(n=>n+'#'+(selectedRxNormIds()[n]||'')).join('\n');
    if(onlinePendingKey===key)return;
    onlinePendingKey=key;
    const req=++onlineSeq;
    onlineReport=null;onlineKey='';
    list.replaceChildren();
    try {
      const res=await fetch('/api/interactions/fda',{
        method:'POST',headers:{'Content-Type':'application/json','X-MediMate-Request':'1'},
        body:JSON.stringify({medicines:names,rxnorm_ids:selectedRxNormIds()})
      });
      if(!res.ok)throw Error('network');
      const report=await res.json();
      if(req!==onlineSeq||key!==lastRequestKey||!onlineConsent)return;
      onlineKey=key;onlineReport=report;onlineFetchedAt=Date.now();
      displayOnlineReport();
    } catch(_){

      if(req===onlineSeq && onlineConsent)list.replaceChildren();
    } finally {if(onlinePendingKey===key)onlinePendingKey='';}
  }
  function displayOnlineReport(){
    const list=$('online-label-results');
    if(!list)return;
    const previouslyOpen=Boolean(list.querySelector('details')?.open);
    list.replaceChildren();
    if(!onlineConsent || !onlineReport || onlineKey!==lastRequestKey)return;
    const data=onlineReport;


    if(!data.mentions?.length)return;
    const extra=elt('details','online-evidence-details');extra.open=previouslyOpen;
    const head=elt('summary','online-review-title',`${t('combinedFdaResults')} (${data.mentions.length})`);
    extra.append(head);list.append(extra);
    for(const hit of data.mentions){
      const row=elt('article','online-mention');
      const title=elt('div','online-mention-head');
      title.append(elt('span','online-source-tag',t('combinedMentionOnly')),
        elt('strong','',hit.first+' + '+hit.second));
      row.append(title);
      row.append(elt('p','online-hit-context',`${hit.label_for} · ${hit.section.replaceAll('_',' ')}`));
      row.append(elt('p','online-excerpt',hit.excerpt));
      if(hit.source_url){
        const link=elt('a','source-link',t('onlineViewSource'));
        link.href=hit.source_url;link.target='_blank';link.rel='noopener noreferrer';row.append(link);
      }
      row.append(elt('p','online-limit-note',t('onlineMentionCaution')));
      extra.append(row);
    }

  }
  async function toggleInteractionReview(hit){
    const id=warningLedgerKey(hit), existing=interactionReviews.get(id);
    if(existing?.reviewedAt){
      const changed={...existing,reviewedAt:null};
      await tx(safetyReviewStore,'readwrite',st=>st.put(changed));
      interactionReviews.set(id,changed);
    }else{

      if(!window.confirm(t('archiveInteractionConfirm')))return;
      const changed={id,profileId:currentProfile,seenAt:existing?.seenAt||new Date().toISOString(),reviewedAt:new Date().toISOString()};
      await tx(safetyReviewStore,'readwrite',st=>st.put(changed));
      interactionReviews.set(id,changed);
    }
    hideConflictToast();drawInteractions();
  }
  function drawInteractions(){
    const results=$('interaction-results');results.replaceChildren();
    const data=interactionReport||{status:'unavailable',alerts:[],uncertain:[],unrecognized:[]};
    const allFound=mergeActionableWarnings(data.alerts);
    const found=allFound.filter(x=>!isReviewedWarning(x));
    const reviewed=allFound.filter(isReviewedWarning);
    const documented=found.filter(x=>x.finding_type!=='duplicate_ingredient');
    const duplicates=found.filter(x=>x.finding_type==='duplicate_ingredient');
    const unmatched=data.unrecognized||[];
    const reviewPairs=new Map();
    for(const item of data.uncertain||[]){


      if(item.reason!=='level_unknown')continue;
      const key=JSON.stringify([item.first,item.second]);
      if(!reviewPairs.has(key))reviewPairs.set(key,{first:item.first,second:item.second,items:[]});
      reviewPairs.get(key).items.push(item);
    }


    $('safety-count').textContent=interactionCountText(data);
    $('stat-flags').textContent=interactionCountText(data);


    updateConflictNotice(found,false,quietAfterArchive);
    if(data.status==='ready'||data.status==='unavailable')quietAfterArchive=false;
    if(data.status!=='ready'){
      const panel=elt('section','safety-group safety-group--unavailable');
      panel.append(elt('h3','safety-group-title',t('safetyUnavailable')),
        elt('p','unverified-message',t('interactionUnavailable')));
      results.append(panel);return;
    }
    if(medicines.length<2){results.append(emptyState('emptyMedsTitle','noMedsCheck'));return;}
    const category=(key,count,style)=>{
      const section=elt('section','safety-group safety-group--'+style);
      const head=elt('h3','safety-group-title',t(key));
      if(count!==null)head.append(elt('span','safety-group-count',String(count)));
      section.append(head);results.append(section);return section;
    };
    const priority={'Contraindicated':0,'Major':1,'Review duplicate ingredient':1,
      'Moderate':2,'Minor':3};
    const appendAlert=(parent,hit)=>{
      const row=elt('div','interaction-row');row.append(elt('span','interaction-alert','!'));
      const info=elt('div','interaction-detail');
      const levelKey='level'+hit.level.replaceAll(' ','');
      const level=t(levelKey)!==levelKey?t(levelKey):hit.level;
      info.append(elt('span','risk-tag',level),elt('strong','interaction-pair',`${hit.first} + ${hit.second}`));
      const findings=hit.findings?.length?hit.findings:[hit];
      const components=[...new Set(findings.map(item=>
        [item.ingredient_a,item.ingredient_b].filter(Boolean).join(' + ')).filter(Boolean))];
      info.append(elt('p','interaction-ingredients',`${t('recognized')} ${components.join('; ')}`));
      const translated=(item,kind)=>{
        const key=kind+'_'+item.rule_code;
        return item.rule_code&&t(key)!==key?t(key):item[kind==='effect'?'effects':'advice'];
      };


      const curated=findings.filter(item=>item.finding_type==='documented_interaction');
      const described=curated.length?curated:findings;
      const uniqueText=(list,kind)=>[...new Set(list.map(item=>translated(item,kind)).filter(Boolean))];
      const effects=uniqueText(described,'effect').filter(s=>!(/recorded.*DDInter|DDInter.*does not (specify|provide)|DDInter has no mechanism/i.test(s)));
      const advices=uniqueText(described,'advice');
      if(effects.length)info.append(elt('span','interaction-subhead',t('potentialEffects')));
      for(const effect of effects){
        info.append(elt('p','interaction-effect',effect));
      }
      if(advices.length){info.append(elt('span','interaction-subhead',t('whatToDo')));
        for(const advice of advices)info.append(elt('p','interaction-advice',advice));}
      const links=elt('div','interaction-sources');
      const sources=findings.flatMap(item=>item.evidence_sources?.length?item.evidence_sources:
        [{label:item.source||'DDInter 2.0',url:item.source_url}]);
      const seen=new Set();
      for(const ref of sources){
        if(!ref.url||seen.has(ref.url))continue;seen.add(ref.url);
        const link=elt('a','source-link',ref.label+' ↗');
        link.href=ref.url;link.target='_blank';link.rel='noopener noreferrer';
        links.append(link);
      }
      if(links.children.length){
        const details=elt('details','safety-extra-details');
        details.append(elt('summary','interaction-subhead',t('evidenceSources')),links);
        info.append(details);
      }
      if(typeof interactionReviews!=='undefined'){
        const actions=elt('div','review-warning-actions');
        const button=elt('button','outline-button review-warning-button',isReviewedWarning(hit)?t('restoreInteraction'):t('archiveInteraction'));
        button.type='button';
        button.addEventListener('click',()=>{void toggleInteractionReview(hit).catch(()=>toast(t('localStorageFailed')));});
        actions.append(button);
        if(isReviewedWarning(hit)) actions.append(elt('small','review-datestamp',t('reviewedWarningNote')));
        info.append(actions);
      }
      row.append(info);parent.append(row);
    };
    if(documented.length){
      const group=category('safetyDocumented',documented.length,'documented');
      for(const hit of [...documented].sort((a,b)=>(priority[a.level]??4)-(priority[b.level]??4)))appendAlert(group,hit);
    }
    if(duplicates.length){
      const group=category('safetyDuplicates',duplicates.length,'duplicate');
      for(const hit of duplicates)appendAlert(group,hit);
    }
    if(reviewed.length){
      const group=elt('details','safety-group safety-group--reviewed safety-extra-details');
      group.append(elt('summary','safety-group-title',`${t('reviewedWarnings')} (${reviewed.length})`));
      group.append(elt('p','safety-group-explanation',t('reviewedWarningsCaution')));
      for(const hit of reviewed)appendAlert(group,hit);
      results.append(group);
    }
    if(reviewPairs.size){
      const group=elt('details','safety-group safety-group--review safety-extra-details');
      group.append(elt('summary','safety-group-title',`${t('safetyReview')} (${reviewPairs.size})`));
      results.append(group);
      group.append(elt('p','safety-group-explanation',t('safetyCollapsedReviewText')));
      const list=elt('ul','safety-review-list');
      for(const pair of reviewPairs.values()){
        list.append(elt('li','',`${pair.first} + ${pair.second}`));
      }
      group.append(list);
      group.append(elt('p','safety-review-advice',t('safetyReviewAdvice')));
    }
    if(unmatched.length){
      const group=elt('details','safety-group safety-group--unknown safety-extra-details');
      group.append(elt('summary','safety-group-title',`${t('safetyUnrecognized')} (${unmatched.length})`));
      results.append(group);
      group.append(elt('p','safety-group-explanation',t('safetyUnrecognizedAdvice')));
      const items=elt('ul','safety-unknown-list');
      for(const name of unmatched)items.append(elt('li','',name));
      group.append(items);
    }

  }
  function render(){
    $('welcome-hero').hidden=medicines.length>=2;
    $('active-overview').hidden=medicines.length<2;
    renderToday();renderMedicines();renderFamily();renderInteractions();renderAdherence();
  }
  function openEditor(med=null) {
    $('medicine-form').reset();$('medicine-id').value=med?.id||'';
    selectedRxNorm=med?.rxnormId?{name:med.name,rxcui:med.rxnormId}:null;
    $('medicine-name').value=med?.name||'';$('medicine-strength').value=med?.strength||'';window.MedimateReminderUI.setTimes(med?.times||[],t);$('medicine-quantity').value=med?.quantity??'';$('medicine-dose-unit').value=med?.doseUnit||'tablet';
    $('medicine-start').value=med?.startDate||med?.updatedAt?.slice(0,10)||localDate();
    $('medicine-end').value=med?.courseEndDate||'';
    const recurrence=schedule.normalize(med?.schedule);$('medicine-frequency').value=recurrence.frequency;
    $('medicine-interval').value=recurrence.everyDays||2;
    for(const box of document.querySelectorAll('input[name="weekly-day"]'))box.checked=(recurrence.weekdays||[]).includes(Number(box.value));
    updateFrequencyControls();
    $('medicine-instructions').value=med?.notes||'';$('dialog-title').textContent=t(med?'dialogEdit':'dialogTitle');
    closeMedicineSuggestions();++suggestionSeq;$('medicine-search-status').textContent='';
    $('medicine-dialog').showModal();$('medicine-name').focus();
  }
  function closeMedicineSuggestions(){
    suggestionItems=[];selectedSuggestion=-1;
    const dropdown=$('medicine-suggestions');dropdown.hidden=true;dropdown.replaceChildren();
    $('medicine-name').setAttribute('aria-expanded','false');
    $('medicine-name').removeAttribute('aria-activedescendant');
  }
  function displayMedicineSuggestions(matches, source){
    const dropdown=$('medicine-suggestions');dropdown.replaceChildren();
    const needle=$('medicine-name').value.trim().toLocaleLowerCase();
    const rank=item=>{const n=String(item.name||'').trim().toLocaleLowerCase();return n===needle?0:n.startsWith(needle+' ')?1:n.startsWith(needle)?2:3;};
    suggestionItems=[...(matches||[])].sort((a,b)=>rank(a)-rank(b)).slice(0,9);selectedSuggestion=-1;
    if(!suggestionItems.length){closeMedicineSuggestions();$('medicine-search-status').textContent=t(source==='online'?'onlineNameEmpty':'nameSearchEmpty');return;}
    for(const [i,item] of suggestionItems.entries()){
      const button=elt('button','med-suggestion');button.type='button';button.id='med-suggestion-'+i;button.setAttribute('role','option');button.setAttribute('aria-selected','false');
      const label=elt('span','suggestion-name',item.name);
      const desc=item.ingredient && item.ingredient.toLowerCase()!==item.name.toLowerCase()?item.ingredient:'';
      button.append(label,elt('span','suggestion-note',desc));
      button.addEventListener('mousedown',ev=>ev.preventDefault());
      button.addEventListener('click',()=>selectMedicineSuggestion(i));
      dropdown.append(button);
    }
    dropdown.hidden=false;$('medicine-name').setAttribute('aria-expanded','true');
    $('medicine-search-status').textContent='';
  }
  function selectMedicineSuggestion(index){
    const item=suggestionItems[index];if(!item)return;
    $('medicine-name').value=item.name;
    selectedRxNorm=(item.rxcui && /^\d{1,12}$/.test(item.rxcui))?{name:item.name,rxcui:item.rxcui}:null;
    closeMedicineSuggestions();$('medicine-search-status').textContent=t('confirmLabel');
    $('medicine-name').focus();
  }
  async function loadMedicineSuggestions(){
    const q=$('medicine-name').value.trim();
    const id=++suggestionSeq;
    if(q.length<2){closeMedicineSuggestions();$('medicine-search-status').textContent='';return;}
    try {
      const res=await fetch('/api/medicines/suggest?q='+encodeURIComponent(q));
      if(!res.ok)throw Error('lookup');const result=await res.json();
      if(id!==suggestionSeq||$('medicine-name').value.trim()!==q)return;
      if(result.matches?.length){
        displayMedicineSuggestions(result.matches,'local');
      } else if(q.length>=3){
        void searchRxNorm();
      } else {
        closeMedicineSuggestions();$('medicine-search-status').textContent=t('nameSearchLonger');
      }
    } catch(_) {if(id===suggestionSeq){closeMedicineSuggestions();$('medicine-search-status').textContent=t('nameUnavailable');}}
  }
  async function searchRxNorm(){
    const query=$('medicine-name').value.trim();
    if(query.length<3){toast(t('nameSearchLonger'));return;}
    const request=++suggestionSeq;clearTimeout(suggestionTimer);

    closeMedicineSuggestions();$('medicine-search-status').textContent=t('onlineNameLoading');
    let errKey='onlineNameUnavailable';
    try{
      const res=await fetch('/api/medicines/rxnorm',{method:'POST',headers:{'Content-Type':'application/json','X-MediMate-Request':'1'},body:JSON.stringify({query})});
      const data=await res.json().catch(()=>({}));
      if(request!==suggestionSeq||query!==$('medicine-name').value.trim())return;
      if(res.status===429 || data.error==='local_rate_limit')errKey='onlineNameLocalLimit';
      else if(res.status===400)errKey='onlineNameInvalid';
      else if(res.status===503)errKey='onlineNameServerError';
      else if(!res.ok)errKey='onlineNameServerError';
      else if(data.status==='unavailable'){
        const byReason={remote_rate_limit:'onlineNameRemoteLimit',access_denied:'onlineNameAccess',
          remote_error:'onlineNameServerError',timeout:'onlineNameTimeout',
          dns_error:'onlineNameNetwork',network_error:'onlineNameNetwork',
          certificate_error:'onlineNameCertificate',invalid_response:'onlineNameServerError'};
        errKey=byReason[data.reason]||'onlineNameUnavailable';
      }else if(data.status==='ready'){
        displayMedicineSuggestions(data.matches,'online');
        return;
      }

      try{
        const local=await fetch('/api/medicines/suggest?q='+encodeURIComponent(query));
        if(local.ok){
          const found=await local.json();
          if(request===suggestionSeq && query===$('medicine-name').value.trim())displayMedicineSuggestions(found.matches,'local');
        }
      }catch(_){                                     }
      if(request===suggestionSeq && query===$('medicine-name').value.trim())$('medicine-search-status').textContent=t(errKey);
    }catch(_){
      if(request===suggestionSeq && query===$('medicine-name').value.trim())$('medicine-search-status').textContent=t(errKey);
    }finally{                                                                }
  }
  function handleMedicineNameKey(e){
    if($('medicine-suggestions').hidden)return;
    if(e.key==='Escape'){e.preventDefault();closeMedicineSuggestions();return;}
    if(e.key==='ArrowDown'||e.key==='ArrowUp'){
      e.preventDefault();selectedSuggestion=(selectedSuggestion+(e.key==='ArrowDown'?1:-1)+suggestionItems.length)%suggestionItems.length;
      for(const [i,el] of [...$('medicine-suggestions').children].entries())el.setAttribute('aria-selected',i===selectedSuggestion?'true':'false');
      $('medicine-name').setAttribute('aria-activedescendant','med-suggestion-'+selectedSuggestion);
    }
    if(e.key==='Enter'&&selectedSuggestion>=0){e.preventDefault();selectMedicineSuggestion(selectedSuggestion);}
  }
  function parseTimes(s) {
    const values=s.split(',').map(v=>v.trim()).filter(Boolean);
    if(values.length>12||values.some(v=>!/^([01]\d|2[0-3]):[0-5]\d$/.test(v))) return null;
    return sortTimes(values);
  }
  async function saveMedicine(event) {
    event.preventDefault();const name=$('medicine-name').value.trim().replace(/\s+/g,' ');
    window.MedimateReminderUI.sync();const times=parseTimes($('medicine-times').value);
    if(!name){toast(t('nameError'));return;}
    if(name.length>90){toast(t('nameLengthError'));return;}
    if(!times){toast(t('timeError'));return;}
    const quantityRaw=$('medicine-quantity').value.trim();
    const quantity=quantityRaw===''?null:Number(quantityRaw);
    if(quantity!==null && (!Number.isFinite(quantity)||quantity<0.25||quantity>50||Math.round(quantity*4)!==quantity*4)){toast(t('quantityError'));return;}
    const doseUnit=$('medicine-dose-unit').value;
    if(!doseUnits.has(doseUnit)){toast(t('quantityError'));return;}
    const id=$('medicine-id').value||crypto.randomUUID();
    const existing=allMedicines.find(m=>m.id===id);
    const start=$('medicine-start').value||localDate();
    const end=$('medicine-end').value||'';
    if(!Number.isFinite(schedule.dayNumber(start))||(end&&(!Number.isFinite(schedule.dayNumber(end))||end<start))){toast(t('dateRangeError'));return;}
    const frequency=$('medicine-frequency').value;
    const everyDays=Number($('medicine-interval').value);
    if(frequency==='interval'&&(!Number.isInteger(everyDays)||everyDays<1||everyDays>365)){toast(t('intervalError'));return;}
    const weekdays=[...document.querySelectorAll('input[name="weekly-day"]:checked')].map(el=>Number(el.value));
    if(frequency==='weekly'&&!weekdays.length){toast(t('weekdayError'));return;}
    const recurrence=schedule.normalize({frequency,everyDays,weekdays});


    const today=localDate();
    const previous=existing?.scheduleVersions?.length?existing.scheduleVersions:[...(existing?[{effectiveFrom:existing.startDate||existing.updatedAt?.slice(0,10)||today,startDate:existing.startDate||today,courseEndDate:existing.courseEndDate||'',schedule:schedule.normalize(existing.schedule),times:existing.times||[]}]:[])];
    const latest=previous.at(-1);
    const changed=!existing||JSON.stringify(schedule.normalize(latest?.schedule))!==JSON.stringify(recurrence)||JSON.stringify(latest?.times)!==JSON.stringify(times)||latest?.startDate!==start||latest?.courseEndDate!==end;
    let scheduleVersions=previous;
    if(changed){
      const effectiveFrom=existing?today:start;
      scheduleVersions=previous.filter(v=>v.effectiveFrom<effectiveFrom);
      scheduleVersions.push({effectiveFrom,startDate:start,courseEndDate:end,schedule:recurrence,times});
    }
    const periods=existing?.periods?.length?existing.periods:[{start:existing?.startDate||start,end:null}];
    const rxnormId=selectedRxNorm?.name===name?selectedRxNorm.rxcui:null;
    const createdAt=localStamp();
    const scheduleChanged=existing && (JSON.stringify(schedule.normalize(existing.schedule))!==JSON.stringify(recurrence) || existing.startDate!==start || existing.courseEndDate!==end);
    const reminderActivatedAt=Object.fromEntries(times.map(time=>[time,
      existing && !scheduleChanged && (existing.times||[]).includes(time)?activationFor(existing,time):createdAt]));
    const med={id,profileId:currentProfile,name,rxnormId,reminderActivatedAt,strength:$('medicine-strength').value.trim(),quantity,doseUnit,times,notes:$('medicine-instructions').value.trim(),startDate:start,courseEndDate:end,schedule:recurrence,scheduleVersions,periods,active:true,updatedAt:new Date().toISOString()};
    await tx('medicines','readwrite',st=>st.put(med));closeMedicineSuggestions();$('medicine-dialog').close();toast(t('saved'));await refresh();
  }
  async function removeMedicine(med){
    if(!window.confirm(t('archiveConfirm')))return;

    med.active=false;med.endDate=localDate();


    if(!Array.isArray(med.periods)||!med.periods.length)
      med.periods=[{start:med.startDate||med.updatedAt?.slice(0,10)||localDate(),end:null}];
    med.periods[med.periods.length-1].end=localDate();
    await tx('medicines','readwrite',st=>st.put(med));


    quietAfterArchive=true;++interactionSeq;hideConflictToast();await refresh();
  }
  let calendarExpanded=false;


  const expandedCalendarDays=new Set();
  function toggleCalendarExpanded(){
    calendarExpanded=!calendarExpanded;
    expandedCalendarDays.clear();
    renderAdherence();
  }
  function renderAdherence(){
    if(!$('monthly-calendar'))return;
    const dateNow=localDate();if(!chosenMonth)chosenMonth=dateNow.slice(0,7);
    if(!chosenDay)chosenDay=dateNow;
    $('calendar-month').value=chosenMonth;
    const [year,month]=chosenMonth.split('-').map(Number);
    if(!year||month<1||month>12)return;
    const member=people.find(p=>p.id===currentProfile)||{id:'self',name:t('meLabel')};
    const data=window.MedimateReport.records(member,allMedicines,allDoses,year,month);
    // Display medicines without a selected reminder time on the calendar,
    // but do not turn these into adherence doses or missed-dose records.
    const calendarEntries=[...data.entries];
    for(const med of allMedicines.filter(m=>(m.profileId||'self')===currentProfile)){
      for(let day=1;day<=new Date(year,month,0).getDate();day++){
        const date=`${chosenMonth}-${String(day).padStart(2,'0')}`;
        if(schedule.isScheduled(med,date)&&schedule.timesOn(med,date).length===0)
          calendarEntries.push({medId:med.id,name:med.name,date,time:'',status:'Unscheduled'});
      }
    }
    const calendarStatus=x=>x.status==='Unscheduled'?t('noReminderScheduled'):t('status'+(x.status==='Not logged'?'NotLogged':x.status));
    const headers=$('calendar-week-head');headers.replaceChildren();
    for(const key of ['mon','tue','wed','thu','fri','sat','sun'])headers.append(elt('span','',t('weekday'+key)));
    const calendarPage=$('page-adherence');
    calendarPage.classList.toggle('calendar-expanded',calendarExpanded);
    const expandButton=$('calendar-expand');
    expandButton.setAttribute('aria-expanded',String(calendarExpanded));
    expandButton.textContent=t(calendarExpanded?'calendarCollapse':'calendarExpand');
    const root=$('monthly-calendar');root.replaceChildren();
    const count=new Date(year,month,0).getDate(),shift=(new Date(year,month-1,1).getDay()+6)%7;
    for(let i=0;i<Math.ceil((shift+count)/7)*7;i++){
      const n=i-shift+1;if(n<1||n>count){root.append(elt('span','calendar-blank'));continue;}
      const day=`${chosenMonth}-${String(n).padStart(2,'0')}`;const stats=data.days.get(day);
      const expandedDay=calendarExpanded||expandedCalendarDays.has(day);
      const cell=elt('div','calendar-cell'+(day===chosenDay?' selected':'')+(expandedDay?' expanded-day':''));
      cell.id='calendar-day-'+day;
      const dayButton=elt('button','calendar-day-button',String(n));dayButton.type='button';
      cell.append(dayButton);
      const daily=calendarEntries.filter(x=>x.date===day).sort((a,b)=>{
        const rank={'Missed':0,'Taken':1,'Not logged':2,'Upcoming':3};
        return (rank[a.status]??4)-(rank[b.status]??4)||a.time.localeCompare(b.time);
      });
      for(const x of (expandedDay?daily:daily.slice(0,5))){
        const status=x.status==='Missed'?'pill-missed':x.status==='Taken'?'pill-taken':'pill-unconfirmed';
        const pill=elt('span','calendar-med-name '+status,`${x.name} · ${calendarStatus(x)}`);
        pill.title=`${x.name}${x.time?' · '+x.time:''} · ${calendarStatus(x)}`;
        cell.append(pill);
      }
      if(!calendarExpanded && daily.length>5){


        const more=elt('button','calendar-more',expandedDay?t('calendarLess'):`+${daily.length-5} ${t('calendarMore')}`);
        more.type='button';
        more.setAttribute('aria-label',`${day} · ${expandedDay?t('calendarLess'):`${daily.length-5} ${t('calendarMore')}`}`);
        more.setAttribute('aria-controls',cell.id);
        more.setAttribute('aria-expanded',String(expandedDay));
        more.addEventListener('click',event=>{
          event.stopPropagation();
          chosenDay=day;
          if(expandedCalendarDays.has(day))expandedCalendarDays.delete(day);
          else expandedCalendarDays.add(day);
          renderAdherence();

          const updated=typeof document==='undefined'?null:document.getElementById('calendar-day-'+day);
          const toggle=updated?.querySelector('.calendar-more');
          if(toggle && typeof toggle.focus==='function')toggle.focus({preventScroll:true});
        });
        cell.append(more);
      }
      dayButton.setAttribute('aria-label',[day,...daily.map(x=>`${x.name}, ${x.time||t('noReminderScheduled')}, ${calendarStatus(x)}`)].join('; ').slice(0,700));
      cell.addEventListener('click',()=>{chosenDay=day;renderAdherence();});
      root.append(cell);
    }
    $('day-log-title').textContent=`${t('dayTitle')} · ${chosenDay}`;
    const list=$('day-log-list');list.replaceChildren();
    const selected=calendarEntries.filter(x=>x.date===chosenDay);
    if(!selected.length){list.append(elt('p','med-notes',t('noScheduledDoses')));return;}
    for(const x of selected){
      const row=elt('div','day-dose-row');const copy=elt('div');
      copy.append(elt('strong','',x.name+(x.time?' · '+x.time:'')),elt('small','dose-state '+(x.status==='Missed'?'state-missed':x.status==='Taken'?'state-taken':'state-neutral'),calendarStatus(x)));row.append(copy);
      const actions=elt('div','day-actions');const med=allMedicines.find(m=>(m.profileId||'self')===currentProfile&&m.id===x.medId);
      if(med&&x.time){
        for(const [status,key] of [['taken','statusTaken'],['missed','statusMissed']]){
          const btn=elt('button','tiny-button',t(key));btn.disabled=x.status.toLowerCase()===status;
          btn.addEventListener('click',()=>markCalendarDose(med,chosenDay,x.time,status));actions.append(btn);
        }
        if(x.status==='Taken'||x.status==='Missed'){
          const undo=elt('button','tiny-button subtle',t('undoDose'));undo.addEventListener('click',()=>markCalendarDose(med,chosenDay,x.time,'undo'));actions.append(undo);
        }
      }
      row.append(actions);list.append(row);
    }
  }
  async function markCalendarDose(med,date,time,status){
    if(date>localDate()||(date===localDate()&&time>`${String(new Date().getHours()).padStart(2,'0')}:${String(new Date().getMinutes()).padStart(2,'0')}`)){toast(t('futureDoseWarning'));return;}
    const id=notifyKey(med.id,date,time);
    if(status==='undo')await tx('doses','readwrite',st=>st.delete(id));
    else await tx('doses','readwrite',st=>st.put({id,medId:med.id,profileId:currentProfile,date,time,status,takenAt:status==='taken'?new Date().toISOString():''}));
    await refresh();
  }
  function downloadExcel(){
    const [year,month]=chosenMonth.split('-').map(Number);
    if(!year||month<1||month>12)return;
    const person=people.find(p=>p.id===currentProfile);
    try{const report=window.MedimateReport.build(person,allMedicines,allDoses,year,month);
      download(report.filename,report.xlsx,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');toast(t('excelReady'));
    }catch(_){toast(t('excelFailed'));}
  }
  function addChatBubble(who,text) {
    const welcome=document.querySelector('.chat-welcome');if(welcome)welcome.remove();
    const bubble=elt('div',`chat-bubble ${who}`);bubble.append(elt('span','bubble-label',t(who==='user'?'you':'assistant')),document.createTextNode(text));
    $('messages').append(bubble);$('messages').scrollTop=$('messages').scrollHeight;
    return bubble;
  }
  const errors={outside_scope:'scopeError',not_configured:'aiNotConfigured',invalid_api_key:'aiKeyInvalid',rate_limited_or_billing:'aiLimited',local_rate_limit:'aiRateLimit'};
  async function chatSend(event) {
    event?.preventDefault();if(sending)return;
    const input=$('chat-input');const question=input.value.trim();if(!question)return;
    input.value='';addChatBubble('user',question);sending=true;$('send-button').disabled=true;
    const waiting=addChatBubble('assistant',t('aiWorking'));
    try{
      const response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json','X-MediMate-Request':'1'},body:JSON.stringify({question,language:lang})});
      const data=await response.json();
      waiting.lastChild.textContent=data.answer||t(errors[data.error]||'aiUnavailable');
    }catch(_){waiting.lastChild.textContent=t('noInternet');}
    finally{sending=false;$('send-button').disabled=false;$('messages').scrollTop=$('messages').scrollHeight;}
  }
  async function enableNotifications() {
    if(!('Notification' in window)){toast(t('notificationsUnsupported'));return;}
    try {
      const permission=await Notification.requestPermission();toast(t(permission==='granted'?'notificationsEnabled':'notificationsDenied'));
    } catch (_) {toast(t('notificationsUnsupported'));}
    updateNotifyStatus();
    void checkDue();
  }
  function updateNotifyStatus() {
    $('notification-status').textContent=t('notificationsClosed');
    const status=typeof Notification==='undefined'?'unsupported':Notification.permission;
    $('notification-status').textContent += ` (${status})`;
  }
  async function checkDue() {
    if(typeof appStopping!=='undefined'&&appStopping)return;
    const now=new Date(), minutes=now.getHours()*60+now.getMinutes(), today=localDate();
    const doses=todayDoses();
    const overdue=doses.filter(d=>!d.done && reminderReady(d.med,today,d.time) && minutes>=Number(d.time.slice(0,2))*60+Number(d.time.slice(3,5)));
    const banner=$('due-reminder-banner');
    if(banner){
      const item=overdue[0];
      banner.hidden=!item;
      if(item){
        $('due-reminder-title').textContent=t('reminderDueTitle');
        $('due-reminder-message').textContent=reminderText(item.med);
        $('due-reminder-time').textContent=item.time;
        $('due-reminder-taken').textContent=t('markTaken');
        $('due-reminder-taken').onclick=()=>toggleDose(item).catch(()=>toast(t('localStorageFailed')));
      }
    }
    // One soft ping per 15-minute dose interval while the website handles alerts.
    // When the OS helper is active its native system sound owns notification audio.
    if(!(macEnabled&&macInstalled)&&safetyAudioEnabled&&overdue.length){
      const key='mm_pings_'+today;
      let played={};
      try{played=JSON.parse(localStorage.getItem(key)||'{}')||{}}catch(_){}
      const slots=overdue.map(d=>({id:d.id,slot:Math.floor(
        (minutes-Number(d.time.slice(0,2))*60-Number(d.time.slice(3,5)))/15)}));
      if(slots.some(x=>played[x.id]!==x.slot)&&gentleMedicinePing()){
        for(const slot of slots)played[slot.id]=slot.slot;
        try{localStorage.setItem(key,JSON.stringify(played))}catch(_){}
      }
      Object.keys(localStorage).filter(k=>k.startsWith('mm_pings_')&&k!==key)
        .forEach(k=>localStorage.removeItem(k));
    }
    // The in-page reminder works whether browser/OS permissions are enabled.
    if(macEnabled&&macInstalled)return;
    if(!('Notification' in window)||Notification.permission!=='granted')return;
    const key='mm_alerts_'+today;
    let sent={};
    try {
      const stored=JSON.parse(localStorage.getItem(key)||'{}');
      if(stored&&!Array.isArray(stored)&&typeof stored==='object')sent=stored;
    }catch(_){}
    let changed=false;
    for(const d of overdue){
      const target=Number(d.time.slice(0,2))*60+Number(d.time.slice(3,5));
      const slot=Math.floor((minutes-target)/15);
      if(sent[d.id]===slot)continue;
      try {
        const registration=await navigator.serviceWorker?.getRegistration?.();
        if(registration?.showNotification)await registration.showNotification('Medicine reminder',{body:reminderText(d.med),tag:d.id,renotify:true,icon:'/icon.svg',badge:'/icon.svg'});
        else new Notification('Medicine reminder',{body:reminderText(d.med),tag:d.id,icon:'/icon.svg'});
        sent[d.id]=slot;changed=true;
      }catch(_){ /* The in-page reminder remains active. */ }
    }
    if(changed)localStorage.setItem(key,JSON.stringify(sent));
    Object.keys(localStorage).filter(k=>k.startsWith('mm_alerts_')&&k!==key).forEach(k=>localStorage.removeItem(k));
  }

  function download(filename,content,mime) {
    const blob=new Blob([content],{type:mime});const url=URL.createObjectURL(blob);const a=elt('a');a.href=url;a.download=filename;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  const icsEscape=s=>String(s).replace(/\\/g,'\\\\').replace(/\r?\n/g,'\\n').replace(/,/g,'\\,').replace(/;/g,'\\;');
  function calendarExport() {
    if(!medicines.length){toast(t('noCalendar'));return;}
    const now=new Date();const today=localDate(now), stamp=now.toISOString().replaceAll('-','').replaceAll(':','').replace(/\.\d+Z$/,'Z');
    const lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//MediMate//Local-first reminders//EN','CALSCALE:GREGORIAN','METHOD:PUBLISH'];
    const group=new Map();


    const startDay=schedule.dayNumber(today);
    for(let offset=0;offset<366;offset++){
      const date=schedule.fromDay(startDay+offset);
      for(const med of medicines)for(const time of schedule.timesOn(med,date)){
        const key=med.id+'|'+time;
        if(!group.has(key))group.set(key,{med,time,dates:[]});
        group.get(key).dates.push(date.replaceAll('-','')+'T'+time.replace(':','')+'00');
      }
    }
    for(const {med,time,dates} of group.values()){
      if(!dates.length)continue;
      const uid=med.id+'-'+time.replace(':','')+'-'+currentProfile+'@medimate.local';
      lines.push('BEGIN:VEVENT',`UID:${icsEscape(uid)}`,`DTSTAMP:${stamp}`,`DTSTART:${dates[0]}`);
      for(let i=1;i<dates.length;i+=3)lines.push('RDATE:'+dates.slice(i,i+3).join(','));
      lines.push(`SUMMARY:${icsEscape(reminderText(med,'en').split('\n')[0])}`,
        `DESCRIPTION:${icsEscape([doseDescription(med,'en'),med.strength,med.notes].filter(Boolean).join(' · '))}`,
        'BEGIN:VALARM','ACTION:DISPLAY','TRIGGER:PT0M',
        `DESCRIPTION:${icsEscape(reminderText(med,'en').split('\n')[0])}`,'END:VALARM','END:VEVENT');
    }
    lines.push('END:VCALENDAR');download('medimate-reminders.ics',lines.join('\r\n')+'\r\n','text/calendar;charset=utf-8');toast(t('calendarReadyYear'));
  }
  function exportData() {
    const data={app:'MediMate',version:3,exportedAt:new Date().toISOString(),people,medicines:allMedicines,doses:allDoses,interactionReviews:[...interactionReviews.values()]};
    download(`medimate-backup-${localDate()}.json`,JSON.stringify(data,null,2),'application/json');toast(t('backupReady'));
  }
  function validateBackup(data) {
    if(!data||data.app!=='MediMate'||![1,2,3].includes(data.version)||!Array.isArray(data.medicines)||!Array.isArray(data.doses)||data.medicines.length>500||data.doses.length>100000)return false;
    if(data.medicines.some(m=>typeof m.id!=='string'||m.id.length>150||typeof m.name!=='string'||m.name.length>90||!m.name.trim()||typeof m.strength!=='string'||m.strength.length>80||typeof m.notes!=='string'||m.notes.length>240||!Array.isArray(m.times)||m.times.length>12||m.times.some(v=>typeof v!=='string'||!/^([01]\d|2[0-3]):[0-5]\d$/.test(v))))return false;
    if(data.medicines.some(m=> ((m.quantity!=null && (typeof m.quantity!=='number'||!Number.isFinite(m.quantity)||m.quantity<0.25||m.quantity>50||Math.round(m.quantity*4)!==m.quantity*4)) || (m.doseUnit!=null && !doseUnits.has(m.doseUnit))) ))return false;
    if(data.medicines.some(m=> (m.courseEndDate && (!Number.isFinite(schedule.dayNumber(m.courseEndDate))||m.courseEndDate<(m.startDate||'0000-00-00'))) ||
      (m.schedule && !['daily','interval','weekly','monthly'].includes(m.schedule.frequency)) ||
      (m.schedule?.frequency==='interval' && (!Number.isInteger(m.schedule.everyDays)||m.schedule.everyDays<1||m.schedule.everyDays>365)) ||
      (m.schedule?.frequency==='weekly' && (!Array.isArray(m.schedule.weekdays)||m.schedule.weekdays.some(x=>!Number.isInteger(x)||x<0||x>6))) ||
      (m.scheduleVersions && (!Array.isArray(m.scheduleVersions)||m.scheduleVersions.length>100||m.scheduleVersions.some(v=>typeof v.effectiveFrom!=='string'||!Number.isFinite(schedule.dayNumber(v.effectiveFrom))||!Number.isFinite(schedule.dayNumber(v.startDate))||!Array.isArray(v.times)||v.times.some(time=>!/^([01]\d|2[0-3]):[0-5]\d$/.test(time))))) ))return false;
    if(data.doses.some(d=>typeof d.id!=='string'||d.id.length>220||typeof d.medId!=='string'||typeof d.date!=='string'||typeof d.time!=='string'||typeof d.takenAt!=='string'))return false;
    const ids=new Set(data.medicines.map(m=>m.id));if(ids.size!==data.medicines.length)return false;
    if(data.version>=2 && (!Array.isArray(data.people)||data.people.length>100||data.people.some(p=>typeof p.id!=='string'||!p.id.trim()||p.id.length>150||typeof p.name!=='string'||!p.name.trim()||p.name.length>60)))return false;


    const profileIds=data.version>=2?new Set(data.people.map(p=>p.id)):new Set(['self']);
    if(data.version>=2 && (profileIds.size!==data.people.length||!profileIds.has('self')))return false;
    if(data.version===3){
      if(!Array.isArray(data.interactionReviews)||data.interactionReviews.length>10000)return false;
      const reviewIds=new Set();
      for(const r of data.interactionReviews){
        if(!r||typeof r.id!=='string'||r.id.length>1100||!r.id||reviewIds.has(r.id)||!profileIds.has(r.profileId)||typeof r.seenAt!=='string'||r.seenAt.length>64||(r.reviewedAt!==null && (typeof r.reviewedAt!=='string'||r.reviewedAt.length>64)))return false;
        reviewIds.add(r.id);
      }
    }
    const medProfiles=new Map(data.medicines.map(m=>[m.id,m.profileId||'self']));
    if([...medProfiles.values()].some(profile=>!profileIds.has(profile)))return false;
    const doseIds=new Set();
    for(const dose of data.doses){
      if(!dose.id||doseIds.has(dose.id)||!medProfiles.has(dose.medId))return false;
      doseIds.add(dose.id);
      if(!Number.isFinite(schedule.dayNumber(dose.date))||!/^([01]\d|2[0-3]):[0-5]\d$/.test(dose.time))return false;
      if((dose.profileId||'self')!==medProfiles.get(dose.medId))return false;
      if(dose.status!=null && !['taken','missed'].includes(dose.status))return false;
    }
    return true;
  }
  function replaceLocalData(nextPeople, nextMedicines, nextDoses, nextReviews=[]) {


    return new Promise((resolve,reject)=>{
      let tr;
      try {
        tr=db.transaction(['people','medicines','doses',safetyReviewStore],'readwrite');
        tr.oncomplete=()=>resolve();
        tr.onerror=()=>reject(tr.error||new Error('storage_error'));
        tr.onabort=()=>reject(tr.error||new Error('storage_aborted'));
        const peopleStore=tr.objectStore('people');
        const medicinesStore=tr.objectStore('medicines');
        const dosesStore=tr.objectStore('doses');
        const reviewsStore=tr.objectStore(safetyReviewStore);
        peopleStore.clear();medicinesStore.clear();dosesStore.clear();reviewsStore.clear();
        for(const person of nextPeople)peopleStore.put(person);
        for(const med of nextMedicines)medicinesStore.put(med);
        for(const dose of nextDoses)dosesStore.put(dose);
        for(const review of nextReviews)reviewsStore.put(review);
      } catch(error) {
        if(tr)try{tr.abort();}catch(_){                                           }
        reject(error);
      }
    });
  }
  function resetSafetyAfterDataReplacement(){


    ++interactionSeq;++onlineSeq;
    interactionReport=null;lastRequestKey='';localLookupPendingKey='';localLookupFetchedAt=0;
    onlineReport=null;onlineKey='';onlinePendingKey='';onlineFetchedAt=0;
    interactionReviews=new Map();previousConflictSignature=new Set();quietAfterArchive=true;
    updateConflictNotice([],true,true);hideConflictToast();
  }
  async function importData(file) {
    if(!file||file.size>8_000_000){toast(t('backupInvalid'));return;}
    try {
      const data=JSON.parse(await file.text());if(!validateBackup(data)){toast(t('backupInvalid'));return;}
      if(!confirm(t('importConfirm')))return;
      const importedPeople=data.version>=2?data.people:[{id:'self',name:t('meLabel'),system:true}];
      try {
        await replaceLocalData(importedPeople,data.medicines,data.doses,data.version===3?data.interactionReviews:[]);
      } catch(_) {toast(t('localStorageFailed'));return;}
      currentProfile='self';localStorage.setItem('mm_profile','self');
      resetSafetyAfterDataReplacement();
      toast(t('backupLoaded'));await refresh();
    }catch(_){toast(t('backupInvalid'));}
  }
  async function clearData() {
    if(!confirm(t('clearConfirm')))return;
    try{
      await replaceLocalData([],[],[]);
      currentProfile='self';localStorage.setItem('mm_profile','self');
      resetSafetyAfterDataReplacement();toast(t('cleared'));await refresh();
    }catch(_){toast(t('localStorageFailed'));}
  }
  async function checkAI(){
    try{const r=await fetch('/api/health');const j=await r.json();$('ai-status').textContent=t(j.ai_configured?'aiReady':'aiOffline')+' · '+j.model;}
    catch(_){$('ai-status').textContent=t('aiOffline');}
  }
  function bindEvents(){
    document.addEventListener('pointerdown',unlockSafetyAudio,{once:true});
    document.addEventListener('keydown',unlockSafetyAudio,{once:true});
    document.querySelectorAll('[data-page]').forEach(el=>el.addEventListener('click',()=>switchPage(el.dataset.page)));
    document.querySelectorAll('[data-go]').forEach(el=>el.addEventListener('click',()=>switchPage(el.dataset.go)));
    document.querySelectorAll('[data-route]').forEach(el=>el.addEventListener('click',e=>{e.preventDefault();switchPage(el.dataset.route);}));
    ['hero-add','med-add','overview-add'].forEach(id=>$(id).addEventListener('click',()=>openEditor()));
    $('profile-selector').addEventListener('change',e=>switchProfile(e.target.value));
    $('family-add').addEventListener('click',()=>{$('family-dialog').showModal();$('family-name').focus();});
    $('family-close').addEventListener('click',()=>$('family-dialog').close());
    $('family-form').addEventListener('submit',e=>saveFamily(e).catch(()=>toast(t('chatSendError'))));
    $('family-delete-dialog').addEventListener('close',()=>{if(!deletingFamily)pendingFamilyDelete=null;});
    $('family-delete-close').addEventListener('click',()=>$('family-delete-dialog').close());
    $('family-delete-cancel').addEventListener('click',()=>$('family-delete-dialog').close());
    $('family-delete-confirm').addEventListener('click',deleteFamily);
    $('calendar-month').addEventListener('change',e=>{chosenMonth=e.target.value;chosenDay=chosenMonth+'-01';expandedCalendarDays.clear();calendarExpanded=false;renderAdherence();});
    $('calendar-expand').addEventListener('click',toggleCalendarExpanded);
    $('export-xlsx').addEventListener('click',downloadExcel);
    $('close-dialog').addEventListener('click',()=>$('medicine-dialog').close());$('cancel-dialog').addEventListener('click',()=>$('medicine-dialog').close());
    window.MedimateReminderUI.init(t);
    $('medicine-form').addEventListener('submit',e=>saveMedicine(e).catch(()=>toast(t('chatSendError'))));
    $('medicine-name').addEventListener('input',()=>{selectedRxNorm=null;clearTimeout(suggestionTimer);const value=$('medicine-name').value.trim();if(value.length<2){closeMedicineSuggestions();$('medicine-search-status').textContent='';return;}suggestionTimer=setTimeout(loadMedicineSuggestions,420);});
    $('medicine-name').addEventListener('keydown',handleMedicineNameKey);
    $('medicine-frequency').addEventListener('change',updateFrequencyControls);
    $('medicine-start').addEventListener('change',()=>{if($('medicine-frequency').value==='weekly'){for(const box of document.querySelectorAll('input[name="weekly-day"]'))box.checked=false;updateFrequencyControls();}});

    document.addEventListener('click',e=>{if(!e.target.closest('.autocomplete-wrap') && true)closeMedicineSuggestions();});
    $('language').addEventListener('change',e=>{lang=e.target.value;localStorage.setItem('mm_lang',lang);translate();render();checkAI();updateNotifyStatus();updateMacStatus();if(macEnabled)scheduleMacSync();});
    $('conflict-review').addEventListener('click',()=>{hideConflictToast();switchPage('interactions');});
    $('conflict-close').addEventListener('click',hideConflictToast);
    $('chat-form').addEventListener('submit',chatSend);
    $('chat-input').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('chat-form').requestSubmit();}});
    document.querySelectorAll('[data-prompt]').forEach(el=>el.addEventListener('click',()=>{$('chat-input').value=t(el.dataset.prompt);$('chat-input').focus();}));
    $('mac-reminders-toggle').addEventListener('click',toggleMacReminders);
    $('stop-medimate').addEventListener('click',stopMedimate);
    $('test-notifications').addEventListener('click',async()=>{
      unlockSafetyAudio();
      const sample=t('notificationTestMessage');
      try {
        if(!('Notification' in window)||Notification.permission!=='granted'){toast(t('notificationsDenied'));return;}
        const registration=await navigator.serviceWorker?.getRegistration?.();
        if(registration?.showNotification)await registration.showNotification('Medicine reminder',{body:sample,tag:'medimate-test-'+Date.now()});
        else new Notification('Medicine reminder',{body:sample,tag:'medimate-test-'+Date.now()});
        toast(t('notificationTestRequested'));
      }catch(_){toast(t('notificationsUnsupported'));}
    });
    $('allow-notifications').addEventListener('click',enableNotifications);$('notification-button').addEventListener('click',()=>{switchPage('settings');enableNotifications();});
    $('export-calendar').addEventListener('click',calendarExport);$('export-data').addEventListener('click',exportData);
    $('import-data').addEventListener('click',()=>$('import-file').click());$('import-file').addEventListener('change',async e=>{await importData(e.target.files?.[0]);e.target.value='';});
    $('clear-data').addEventListener('click',clearData);
    window.addEventListener('focus',()=>{if(appStopping)return;checkDue();refresh().catch(()=>{});});
    document.addEventListener('visibilitychange',()=>{if(!appStopping&&document.visibilityState==='visible')checkDue();});
  }
  async function init(){
    chosenDay=localDate();chosenMonth=chosenDay.slice(0,7);translate();bindEvents();try{db=await database();await refresh();}catch(e){toast('Local browser storage could not be opened. Check private browsing settings.');console.error('IndexedDB could not be opened');}
    await readMacStatus();await checkAI();updateNotifyStatus();if(navigator.serviceWorker?.register){
      // The service worker handles notifications, never serves cached HTML/CSS/JS.
      // A previous version cached the application shell and could show an old UI.
      navigator.serviceWorker.register('/sw.js',{updateViaCache:'none'}).then(r=>r.update()).catch(()=>{});
    }
    setInterval(checkDue,20000);setTimeout(checkDue,1200);
  }
  document.addEventListener('DOMContentLoaded',init);
})();
