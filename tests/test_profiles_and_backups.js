
const __medimate_root = require("node:path").resolve(__dirname,"..");

(function(){

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const read = name => fs.readFileSync(path.join(__medimate_root, 'static', name), 'utf8');
const elements = new Map();
function element(id) {
  if (!elements.has(id)) {
    const classes = new Set();
    elements.set(id, {
      id, value: '', textContent: '', hidden: true, open: false,
      classList: {toggle: (key, yes) => yes ? classes.add(key) : classes.delete(key),
                  contains: key => classes.has(key)},
      replaceChildren() {}, setAttribute(key, value) { this[key] = value; },
      removeAttribute(key) { delete this[key]; },
      close() { this.open = false; }, showModal() { this.open = true; }, reset() {}, focus() {},
    });
  }
  return elements.get(id);
}
const nav = element('nav-interactions');
const localValues = new Map();
let allowConfirm = true;
let seq = 0;
const environment = {
  window: {MedimateReminderUI: {sync() {}, setTimes() {}}, confirm: () => allowConfirm},
  document: {
    addEventListener() {}, getElementById: element,
    querySelector: query => query === '[data-page="interactions"]' ? nav : null,
    querySelectorAll: () => [],
  },
  localStorage: {getItem: key => localValues.get(key) ?? null,
                 setItem: (key, val) => localValues.set(key, val),
                 removeItem: key => localValues.delete(key)},
  confirm: () => allowConfirm,
  crypto: {randomUUID: () => 'test-id-' + ++seq},
  setTimeout, clearTimeout, Date,
};
const context = vm.createContext(environment);
vm.runInContext(read('translations.js'), context);
vm.runInContext(read('schedule.js'), context);
const marker = "  document.addEventListener('DOMContentLoaded',init);";
const source = read('app.js');
assert(source.includes(marker), 'Unable to expose app handlers to synthetic workflow tests');
const hook = `
  window.fixture = {
    saveMedicine, removeMedicine, saveFamily, openFamilyDelete, deleteFamily, switchProfile,
    cancelPendingDelete: () => {pendingFamilyDelete=null;},
    updateConflictNotice, importData, clearData,
    getState: () => ({currentProfile, allMedicines, allDoses, people}),
    setSelected: x => {selectedRxNorm=x;},
    install(stores, fakeDb) {
      db=fakeDb;
      tx=async(name, mode, run) => {
        const entries=stores[name];
        const req=run({
          put(value) {entries.set(value.id, value);return {result:value.id};},
          delete(id) {entries.delete(id);return {result:undefined};},
          getAll() {return {result:[...entries.values()]};},
          clear() {entries.clear();return {result:undefined};},
        });
        return req?.result;
      };
      refresh=async()=>{
        interactionReviews=new Map(stores.interactionReviews);
        people=[...stores.people.values()];
        allMedicines=[...stores.medicines.values()];
        allDoses=[...stores.doses.values()];
        medicines=allMedicines.filter(m=>(m.profileId||'self')===currentProfile&&m.active!==false);
        doseRecords=allDoses.filter(d=>(d.profileId||'self')===currentProfile);
      };
      toast=message=>{window.testToasts.push(message);};
      return refresh();
    },
  };
`;
environment.window.testToasts = [];
vm.runInContext(source.replace(marker, hook), context);
const fixture = environment.window.fixture;
const initialMed = {
  id: 'existing-self', profileId: 'self', name: 'Unchanged medicine',
  strength: '', notes: '', times: ['08:00'], startDate: '2026-10-01',
  schedule: {frequency: 'daily'}, active: true,
};
const stores = {
  people: new Map([['self', {id: 'self', name: 'Me'}]]),
  medicines: new Map([[initialMed.id, initialMed]]),
  doses: new Map([['historical', {id: 'historical', medId: initialMed.id,
    profileId: 'self', date: '2026-10-01', time: '08:00', takenAt: ''}]]),
  interactionReviews: new Map(),
};


let failNextWrite = false;
let transactionCount = 0;
const fakeDb = {
  transaction(names, mode) {
    transactionCount++;
    assert.deepEqual(Array.from(names), ['people', 'medicines', 'doses', 'interactionReviews']);
    assert.equal(mode, 'readwrite');
    const staged = Object.fromEntries(names.map(n => [n, new Map(stores[n])]));
    let aborted = false;
    const tr = {
      abort() { aborted = true; queueMicrotask(() => tr.onabort?.()); },
      objectStore(name) {
        return {
          clear() {
            if (failNextWrite) {failNextWrite = false;throw Error('Simulated quota failure');}
            staged[name].clear();
          },
          put(value) {
            if (failNextWrite) {failNextWrite = false;throw Error('Simulated quota failure');}
            staged[name].set(value.id, value);
          },
          delete(id) {
            if (failNextWrite) {failNextWrite = false;throw Error('Simulated quota failure');}
            staged[name].delete(id);
          },
        };
      },
    };
    queueMicrotask(() => {
      if (aborted) return;
      for (const name of names) {
        stores[name].clear();
        for (const [id, value] of staged[name]) stores[name].set(id, value);
      }
      tr.oncomplete?.();
    });
    return tr;
  },
};

function input(id, value) {element(id).value = value;}
const saveEvent = {preventDefault() {}};
function populateMedicine(name, id = '') {
  input('medicine-id', id);
  input('medicine-name', name);
  input('medicine-times', '08:00, 20:00');
  input('medicine-quantity', '1');
  input('medicine-dose-unit', 'tablet');
  input('medicine-start', '2026-10-01');
  input('medicine-end', '');
  input('medicine-frequency', 'daily');
  input('medicine-interval', '2');
  input('medicine-strength', 'Example strength');
  input('medicine-instructions', 'As directed');
}

async function run() {
  await fixture.install(stores, fakeDb);


  populateMedicine('Viagra');
  fixture.setSelected({name: 'Viagra', rxcui: '12345'});
  await fixture.saveMedicine(saveEvent);
  const added = [...stores.medicines.values()].find(m => m.name === 'Viagra');
  assert(added && added.id === 'test-id-1');
  assert.equal(added.rxnormId, '12345');
  assert.deepEqual(Array.from(added.times), ['08:00', '20:00']);
  assert.equal(added.profileId, 'self');
  assert.equal(added.scheduleVersions.length, 1);
  populateMedicine('Viagra', added.id);
  input('medicine-instructions', 'Edited instruction');
  await fixture.saveMedicine(saveEvent);
  assert.equal(stores.medicines.size, 2);
  assert.equal(stores.medicines.get(added.id).notes, 'Edited instruction');
  await fixture.removeMedicine(stores.medicines.get(added.id));
  assert.equal(stores.medicines.get(added.id).active, false);
  assert.equal(stores.doses.size, 1);
  assert.equal(stores.medicines.get(initialMed.id).name, initialMed.name);


  input('family-name', 'Test member');
  await fixture.saveFamily(saveEvent);
  const member = [...stores.people.values()].find(p => p.name === 'Test member');
  assert(member && member.id === 'test-id-2');
  fixture.updateConflictNotice([{first: 'Example A', second: 'Example B',
    ingredient_a: 'Example ingredient A', ingredient_b: 'Example ingredient B',
    level: 'Major', finding_type: 'documented_interaction'}], [], []);
  assert.equal(element('conflict-nav-badge').hidden, false);
  await fixture.switchProfile(member.id);
  assert.equal(element('conflict-nav-badge').hidden, true,
    'A previous profile warning badge must disappear immediately when switching profiles');
  assert.equal(element('conflict-stat-dot').hidden, true);
  assert.equal(element('conflict-toast').hidden, true);
  populateMedicine('Panadol');
  fixture.setSelected(null);
  await fixture.saveMedicine(saveEvent);
  const familyMed = [...stores.medicines.values()].find(m => m.name === 'Panadol');
  assert.equal(familyMed.profileId, member.id);
  assert.equal(stores.medicines.get(initialMed.id).profileId, 'self');
  fixture.openFamilyDelete(member);
  fixture.cancelPendingDelete();
  await fixture.deleteFamily();
  assert(stores.people.has(member.id));
  fixture.openFamilyDelete(member);
  failNextWrite = true;
  await fixture.deleteFamily();
  assert(stores.people.has(member.id), 'Failed family deletion must roll back');
  assert(stores.medicines.has(familyMed.id));
  await fixture.deleteFamily();
  assert(!stores.people.has(member.id));
  assert(!stores.medicines.has(familyMed.id));
  assert(stores.medicines.has(initialMed.id));
  assert(stores.doses.has('historical'));


  fixture.updateConflictNotice([], [], [{first: 'Percocet Pill', second: 'Adderall'}]);
  assert.equal(element('conflict-nav-badge').hidden, true);
  assert.equal(element('conflict-toast').hidden, true);
  assert.equal(element('conflict-toast')['aria-live'], 'polite');
  fixture.updateConflictNotice([{first: 'Viagra', second: 'nitroglycerin',
    ingredient_a: 'Sildenafil', ingredient_b: 'Nitroglycerin',
    level: 'Major', finding_type: 'documented_interaction'}], [], []);
  assert.equal(element('conflict-nav-badge').hidden, false);
  assert(!element('conflict-nav-badge').classList.contains('needs-review'));
  assert(!element('conflict-toast').classList.contains('needs-review'));
  assert.equal(element('conflict-toast')['aria-live'], 'assertive');
  fixture.updateConflictNotice([], [], []);
  assert.equal(element('conflict-nav-badge').hidden, true);
  assert.equal(element('conflict-toast').hidden, true);


  const imported = {
    app: 'MediMate', version: 2, people: [{id: 'self', name: 'Me'}],
    medicines: [{id: 'import-1', profileId: 'self', name: 'Example imported',
      strength: '', notes: '', times: ['09:00']}],
    doses: [{id: 'import-1|2026-10-01|09:00', medId: 'import-1',
      date: '2026-10-01', time: '09:00', takenAt: ''}],
  };
  const file = {size: 400, text: async () => JSON.stringify(imported)};
  failNextWrite = true;
  await fixture.importData(file);
  assert(stores.medicines.has(initialMed.id));
  assert(stores.doses.has('historical'));
  assert(!stores.medicines.has('import-1'));
  assert(environment.window.testToasts.some(s => s.includes('existing local records')));
  await fixture.importData(file);
  assert.equal(stores.medicines.size, 1);
  assert(stores.medicines.has('import-1'));
  assert(!stores.doses.has('historical'));
  assert.equal(stores.doses.size, 1);

  failNextWrite = true;
  await fixture.clearData();
  assert(stores.medicines.has('import-1'));
  await fixture.clearData();
  assert.equal(stores.medicines.size, 0);
  assert.equal(stores.doses.size, 0);
  assert.equal(stores.people.size, 0);
  assert.equal(transactionCount, 6);
  console.log('Synthetic create/edit/archive, family isolation, review-notice suppression, and atomic backup/clear checks passed');
}

run().catch(error => {console.error(error);process.exitCode = 1;});

})();

(function(){

const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const src=fs.readFileSync(__medimate_root+'/static/app.js','utf8');
const first=src.indexOf('  function renderFamily(){');
const last=src.indexOf('  async function saveFamily(',first);
assert(first>0 && last>first);
const html=fs.readFileSync(__medimate_root+'/static/index.html','utf8');
for(const id of ['family-delete-dialog','family-delete-title','family-delete-impact','family-delete-confirm','family-delete-cancel','family-delete-close'])
  assert(html.includes(`id="${id}"`),'Missing dialog element '+id);
const sw=fs.readFileSync(__medimate_root+'/static/sw.js','utf8');
assert.match(sw,/caches\.keys\(\)/,'stale caches are removed');
assert.doesNotMatch(sw,/addEventListener\('fetch'/,'never serve stale UI');
const trContext={window:{}};vm.runInNewContext(fs.readFileSync(__medimate_root+'/static/translations.js','utf8'),trContext);
for(const language of ['en','ta','zh','ms'])assert(trContext.window.I18N[language].removeFamily,'Missing translated Remove family label in '+language);
function fakeElement(tag='',cls='',text=''){
  return {tag,cls,textContent:text,disabled:false,attributes:{},children:[],events:{},open:false,
    append(...c){this.children.push(...c);},replaceChildren(...c){this.children=c;},
    setAttribute(k,v){this.attributes[k]=v;},addEventListener(k,f){this.events[k]=f;},
    showModal(){this.open=true;},close(){this.open=false;},focus(){this.focused=true;}
  };
}
async function scenario({fail=false,selected='kid',cancel=false}={}){
  const records={people:new Map([['self',{id:'self',name:'Me'}],['kid',{id:'kid',name:'Test'}],['other',{id:'other',name:'Sibling'}]]),
    medicines:new Map([['m1',{id:'m1',profileId:'kid',active:true}],['m2',{id:'m2',profileId:'kid',active:false}],['m3',{id:'m3',profileId:'other',active:true}],['m4',{id:'m4',profileId:'self',active:true}]]),
    doses:new Map([['d1',{id:'d1',profileId:'kid'}],['d2',{id:'d2',profileId:'kid'}],['d3',{id:'d3',profileId:'other'}]]),
    interactionReviews:new Map()};
  const fields=new Map();
  const $=key=>{if(!fields.has(key))fields.set(key,fakeElement('div'));return fields.get(key);};
  let resetCount=0,refreshCount=0,syncCount=0,errors=[];const settings=[];
  const db={transaction(names,mode){
    assert.equal(mode,'readwrite');assert.deepEqual(Array.from(names),['people','medicines','doses','interactionReviews']);
    const staged=[];
    const tr={error:Error('Synthetic write failure'),objectStore(table){return {delete:key=>staged.push([table,key])};},abort(){this.aborted=true;}};
    queueMicrotask(()=>{
      if(fail){tr.onabort?.();return;}
      for(const [table,key] of staged)records[table].delete(key);
      tr.oncomplete?.();
    });
    return tr;
  }};
  const context=vm.createContext({
    people:[...records.people.values()],allMedicines:[...records.medicines.values()],allDoses:[...records.doses.values()],
    currentProfile:selected,pendingFamilyDelete:null,deletingFamily:false,
    interactionReviews:records.interactionReviews,safetyReviewStore:'interactionReviews',
    db,$,elt:fakeElement,t:key=>({removeFamily:'Remove member',navMeds:'Medicines',meLabel:'Me',chooseProfile:'Switch',selectedProfile:'Selected',
      familyRemoveTitle:'Remove {name}?',familyDeleteImpact:'Remove {medicines} medicine records and {doses} dose records.'})[key]||key,
    resetSafetyAfterDataReplacement:()=>resetCount++,refresh:async()=>{refreshCount++;syncCount++;},
    toast:msg=>errors.push(msg),localStorage:{setItem:(k,v)=>settings.push([k,v])},Promise,Set,Map,String,
  });
  vm.runInContext(`${src.slice(first,last)}\nthis.handlers={renderFamily,openFamilyDelete,deleteFamily};`,context);
  const h=context.handlers;
  h.renderFamily();
  const cards=$('family-list').children;
  assert.equal(cards.length,3);
  assert.equal(cards[0].children.at(-1).children.length,1,'Primary Me profile must not be removable');
  assert.equal(cards[1].children.at(-1).children.length,2,'Removal button must be visible on the card');
  const removeButton=cards[1].children.at(-1).children[1];
  assert.equal(removeButton.textContent,'Remove member');
  assert.equal(removeButton.attributes['aria-label'],'Remove member: Test');
  h.openFamilyDelete({id:'self',name:'Me'});
  assert.equal($('family-delete-dialog').open,false,'Cannot remove primary profile');
  removeButton.events.click();
  assert.equal($('family-delete-dialog').open,true);
  assert.equal($('family-delete-title').textContent,'Remove Test?');
  assert.equal($('family-delete-impact').textContent,'Remove 2 medicine records and 2 dose records.','Include archived medicines');
  if(cancel){
    $('family-delete-dialog').close();context.pendingFamilyDelete=null;
    await h.deleteFamily();
    assert.equal(records.people.size,3);assert.equal(records.medicines.size,4);
    assert.equal(refreshCount,0);
    return;
  }
  await h.deleteFamily();
  if(fail){
    assert.equal(records.people.size,3);assert.equal(records.medicines.size,4);
    assert.deepEqual(errors,['localStorageFailed']);assert.equal(refreshCount,0);
    return;
  }
  assert.equal(records.people.has('kid'),false);
  assert.equal(records.medicines.has('m1'),false);assert.equal(records.medicines.has('m2'),false);
  assert.equal(records.doses.has('d1'),false);assert.equal(records.doses.has('d2'),false);
  assert.equal(records.people.has('self'),true);assert.equal(records.people.has('other'),true);
  assert.equal(records.medicines.has('m3'),true);assert.equal(records.medicines.has('m4'),true);
  assert.equal(records.doses.has('d3'),true);
  assert.equal(context.currentProfile,selected==='kid'?'self':selected);
  assert.equal(resetCount,1,'Delete resets safety without replaying old popups');
  assert.equal(refreshCount,1,'Refresh once for updated members and reminders');
  assert.equal(syncCount,1);
  assert.equal($('family-delete-dialog').open,false);
  assert.equal(context.pendingFamilyDelete,null);
  assert.equal(context.deletingFamily,false);
  assert.deepEqual(errors,[]);
  assert.equal(settings.length,1);
}
(async()=>{
  await scenario({cancel:true});
  await scenario({fail:true});
  await scenario({selected:'kid'});
  await scenario({selected:'self'});
  console.log('Family member removal: UI, guard, confirmation, atomic deletion, cross-profile isolation and quiet safety refresh PASS');
})().catch(e=>{console.error(e);process.exitCode=1;});

})();

(function(){

const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const code=fs.readFileSync(__medimate_root+'/static/app.js','utf8');
const scheduleSrc=fs.readFileSync(__medimate_root+'/static/schedule.js','utf8');
const start=code.indexOf('  function validateBackup(data) {');
const end=code.indexOf('  async function checkAI(){',start);
assert(start>0&&end>start,'Expected backup functions are present');
const status={notice:0,hidden:0,refreshed:0,stored:[],messages:[]};
const context=vm.createContext({
  window:{},localStorage:{setItem(){}},confirm:()=>true,
  t:key=>key,toast:m=>status.messages.push(m),
  updateConflictNotice:()=>status.notice++,hideConflictToast:()=>status.hidden++,
  refresh:async()=>{status.refreshed++;},
  db:{transaction:()=>{throw Error('Transaction intentionally not used in synthetic test');}},
  Date,Set,Map,Number,JSON,Promise,
});
vm.runInContext(scheduleSrc,context);
vm.runInContext(`
  const schedule=window.MedimateSchedule;
  const doseUnits=new Set(['tablet','capsule','mL','drop','puff','sachet','patch','spray','other']);
  let interactionSeq=2,onlineSeq=4,interactionReport={status:'ready'},lastRequestKey='old',
      localLookupPendingKey='old',localLookupFetchedAt=20,
      onlineReport={mentions:[]},onlineKey='old',onlinePendingKey='old',onlineFetchedAt=20,
      previousConflictSignature=new Set(['old']),quietAfterArchive=false,currentProfile='old';
  ${code.slice(start,end)}
  replaceLocalData=async(...args)=>{ globalTestWrites.push(args); };
  this.handlers={validateBackup,importData,clearData,
    state:()=>({interactionSeq,onlineSeq,interactionReport,lastRequestKey,
      localLookupPendingKey,onlineReport,onlineKey,onlinePendingKey,
      previousConflictSignature,quietAfterArchive,currentProfile})};
`,Object.assign(context,{globalTestWrites:status.stored}));
const h=context.handlers;
const original=()=>({app:'MediMate',version:2,people:[{id:'self',name:'Me'},{id:'kid',name:'Family'}],
  medicines:[{id:'med-1',profileId:'kid',name:'Example',strength:'',notes:'',times:['08:00']}],
  doses:[{id:'med-1|2026-10-21|08:00',medId:'med-1',profileId:'kid',date:'2026-10-21',time:'08:00',takenAt:'',status:'taken'}]});
const file=data=>({size:800,text:async()=>JSON.stringify(data)});
(async()=>{
  assert.equal(h.validateBackup(original()),true);
  const variations=[
    x=>x.people.pop(),
    x=>x.people[1].id='self',
    x=>x.people.shift(),
    x=>x.medicines[0].profileId='unknown',
    x=>x.doses[0].profileId='self',
    x=>x.doses[0].medId='missing',
    x=>x.doses[0].date='2026-02-30',
    x=>x.doses[0].time='26:00',
    x=>x.doses.push({...x.doses[0]}),
    x=>x.doses[0].status='mysterious',
  ];
  for(const change of variations){
    const altered=original();change(altered);
    assert.equal(h.validateBackup(altered),false,'Invalid backup must be rejected');
    await h.importData(file(altered));
    assert.equal(status.stored.length,0,'Invalid backup must not modify IndexedDB');
  }
  const legacy=original();legacy.version=1;delete legacy.people;
  legacy.medicines[0].profileId='self';legacy.doses[0].profileId='self';
  assert.equal(h.validateBackup(legacy),true,'Legacy primary-profile backup remains restorable');
  const current=original();
  await h.importData(file(current));
  assert.equal(status.stored.length,1);
  assert.equal(status.stored[0][2].length,1,'Valid doses must be restored without silent filtering');
  let s=h.state();
  assert.equal(s.currentProfile,'self');
  assert.equal(s.interactionReport,null);
  assert.equal(s.lastRequestKey,'');
  assert.equal(s.localLookupPendingKey,'');
  assert.equal(s.onlineReport,null);
  assert.equal(s.onlineKey,'');
  assert.equal(s.onlinePendingKey,'');
  assert.equal(s.quietAfterArchive,true);
  assert.equal(s.interactionSeq,3);
  assert.equal(s.onlineSeq,5);
  assert.equal(s.previousConflictSignature.size,0);
  assert(status.hidden>0&&status.notice>0);
  await h.clearData();
  assert.equal(status.stored.length,2);
  assert.equal(status.stored[1][1].length,0);
  assert.equal(status.stored[1][2].length,0);
  s=h.state();assert.equal(s.interactionSeq,4);assert.equal(s.onlineSeq,6);
  assert.equal(status.refreshed,2);
  console.log('Backup profile/dose integrity and stale-warning reset: PASS');
})().catch(error=>{console.error(error);process.exitCode=1;});

})();

(function(){
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const src=fs.readFileSync(__medimate_root+'/static/app.js','utf8');
const start=src.indexOf('  function validateBackup(data) {');
const end=src.indexOf('  function resetSafetyAfterDataReplacement(){',start);
assert(start>0&&end>start);
const records={people:new Map([['self',{id:'self',name:'Me'}]]),medicines:new Map(),doses:new Map(),interactionReviews:new Map()};
let txCount=0;
const mockDb={transaction(names,mode){
  assert.deepEqual(Array.from(names),['people','medicines','doses','interactionReviews']);
  assert.equal(mode,'readwrite');txCount++;
  const staged=Object.fromEntries(names.map(n=>[n,new Map(records[n])]));
  const obj={oncomplete:null,onerror:null,onabort:null,objectStore(name){return {clear(){staged[name].clear();},put(value){staged[name].set(value.id,value);}};},abort(){queueMicrotask(()=>obj.onabort?.());}};
  queueMicrotask(()=>{for(const n of names)records[n]=staged[n];obj.oncomplete?.();});
  return obj;
}};
const env={db:mockDb,safetyReviewStore:'interactionReviews',doseUnits:new Set(['tablet','capsule','mL','drop','puff','sachet','patch','spray','other']),schedule:{dayNumber:day=>Date.parse(day+'T00:00:00Z')/86400000},Date,Set,Map,Number,Promise};
vm.createContext(env);vm.runInContext(src.slice(start,end)+'\nthis.validate=validateBackup;this.replace=replaceLocalData;',env);
const valid={app:'MediMate',version:3,people:[{id:'self',name:'Me'}],medicines:[],doses:[],interactionReviews:[{id:'["self","interaction","n","w","Major"]',profileId:'self',seenAt:'2026-10-23T09:00:00Z',reviewedAt:'2026-10-23T09:10:00Z'}]};
(async()=>{
 assert.equal(env.validate(valid),true);
 const invalid=JSON.parse(JSON.stringify(valid));invalid.interactionReviews[0].profileId='deleted';
 assert.equal(env.validate(invalid),false,'Orphaned review records must be rejected');
 await env.replace(valid.people,valid.medicines,valid.doses,valid.interactionReviews);
 assert.equal(txCount,1);
 assert.equal(records.interactionReviews.size,1);
 await env.replace([{id:'self',name:'Me'}],[],[],[]);
 assert.equal(records.interactionReviews.size,0,'Clear or v2 restore must remove stale review records');
 console.log('PASS: backups retain reviewed statuses and reject orphan records; reset clears stale reviews');
})().catch(e=>{console.error(e);process.exitCode=1;});

})();
