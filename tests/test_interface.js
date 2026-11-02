
const __medimate_root = require("node:path").resolve(__dirname,"..");

(function(){
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
const src=fs.readFileSync(__medimate_root+'/static/app.js','utf8');const css=fs.readFileSync(__medimate_root+'/static/styles.css','utf8');
assert.match(src,/suggestionItems=\[\.\.\.\(matches\|\|\[\]\)\]\.sort\(\(a,b\)=>rank\(a\)-rank\(b\)\)/);
assert.match(css,/\.page#page-chat \.chat-layout\{width:100%;max-width:none/);
assert.match(css,/\.page#page-chat \.conversation-card\{height:clamp\(/);
assert.match(css,/\.page#page-chat \.chat-messages\{min-height:0;max-height:none/);
console.log('PASS: exact-name ranking and expanded chat layout rules present');

})();

(function(){

const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const root=__medimate_root;
const src=fs.readFileSync(root+'/static/translations.js','utf8');
const html=fs.readFileSync(root+'/static/index.html','utf8');
const app=fs.readFileSync(root+'/static/app.js','utf8');
const css=fs.readFileSync(root+'/static/styles.css','utf8');
const env={window:{}}; vm.runInNewContext(src,env);
const all=env.window.I18N;
const locales=['en','ta','zh','ms'];
const keys=Object.keys(all.en).sort();
for(const loc of locales){
 assert.deepEqual(Object.keys(all[loc]).sort(),keys,`dictionary parity for ${loc}`);
 for(const k of keys){
  const v=all[loc][k]; assert(typeof v==='string'&&v.trim(),`${loc}:${k} missing text`);
  const p=s=>[...s.matchAll(/\{([A-Za-z][\w]*)\}/g)].map(m=>m[1]).sort();
  assert.deepEqual(p(v),p(all.en[k]),`${loc}:${k} placeholder mismatch`);
 }
}
const matchAttrs=[...html.matchAll(/data-i18n(?:-placeholder|-aria-label|-title)?="([\w]+)"/g)].map(m=>m[1]);
for(const k of matchAttrs)assert(keys.includes(k),`missing translated attribute ${k}`);
for(const marker of ['navAria','navSectionsAria','profileAria','languageAria','notificationAria','closeAria','chatQuestionAria','chatSendAria'])assert(html.includes(`="${marker}"`),`missing aria UI binding ${marker}`);
assert(app.includes("document.querySelectorAll('[data-i18n-aria-label]')"),'translated aria labels must update at runtime');
assert(app.includes("document.querySelectorAll('[data-i18n-title]')"),'translated tooltips must update');
assert(!all.ta.calendarReady.includes('Calendar'),'Tamil calendar success message left in English');
assert(!all.ms.calendarLess.includes('hari ini'),'Malay collapse control wrongly says today');
assert(!all.zh.safetyMissingEvidence.includes('组成分配对'),'Unnatural Chinese interaction phrase');
for(const loc of locales){
 assert(all[loc].statusNotLogged!==all[loc].statusMissed,`${loc}: not logged must differ from missed`);
 assert(all[loc].safetyWarningText.trim(),`${loc}: no-warning safety caveat missing`);
}
assert(css.includes('[lang="ta"] .main-nav .nav-link'),'Tamil mobile layout rules missing');
assert(css.includes('[lang="ms"] .main-nav .nav-link'),'Malay mobile layout rules missing');
console.log(`Translations: ${keys.length} complete keys x 4 languages, placeholder parity, accessible controls and safety semantics: PASS`);

})();

(function(){


const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const text=fs.readFileSync(__medimate_root+'/static/translations.js','utf8');
const html=fs.readFileSync(__medimate_root+'/static/index.html','utf8');
const app=fs.readFileSync(__medimate_root+'/static/app.js','utf8');
const env={window:{}};vm.runInNewContext(text,env);
const d=env.window.I18N;assert(d && d.en && d.ta && d.zh && d.ms);
const expected=Object.keys(d.en);
const keys=[...html.matchAll(/data-i18n(?:-placeholder)?="([^"]+)"/g)].map(m=>m[1]);
keys.push(...[...app.matchAll(/\bt\('([\w]+)'\)/g)].map(m=>m[1]));
for(const key of new Set(keys))assert(expected.includes(key),'No English translation for UI key: '+key);
for(const locale of ['ta','zh','ms']){
 assert.deepEqual(Object.keys(d[locale]).sort(),expected.slice().sort(),`${locale}: keys differ from English`);
 for(const key of expected){
  assert(typeof d[locale][key]==='string' && d[locale][key].trim(),`${locale}: missing translation for ${key}`);
 }
 for(const key of ['calendarMore','calendarLess','calendarExpand','calendarCollapse','statusTaken','statusMissed','statusNotLogged'])
  assert(d[locale][key]!==d.en[key],`${locale}: calendar label left in English (${key})`);
}
const calendarBlock=app.slice(app.indexOf('  let calendarExpanded=false;'),app.indexOf('  async function markCalendarDose'));
assert(calendarBlock.includes('expandedCalendarDays'),'Calendar needs per-date expansion');
assert(calendarBlock.includes("pill.title=`${x.name} · ${x.time} · ${t('status'"),'Calendar tooltips must use localized statuses');
assert(calendarBlock.includes("dayButton.setAttribute('aria-label'"),'Calendar dates must have accessible labels');
console.log(`Translation coverage: ${expected.length} shared keys in English, Tamil, Simplified Chinese and Malay; UI references and calendar labels verified`);

})();

(function(){

const assert=require('node:assert/strict');
const fs=require('node:fs'), vm=require('node:vm'), path=require('node:path');
const get=x=>fs.readFileSync(path.join(__medimate_root,'static',x),'utf8');
const html=get('index.html'),app=get('app.js'),css=get('styles.css'),tr=get('translations.js');
const env={window:{}};vm.runInNewContext(tr,env);
for(const language of ['en','ta','zh','ms']){
 assert(env.window.I18N[language].skipToContent?.length>4);
 assert(env.window.I18N[language].settingsDataDesc?.length>30);
}
assert.match(html, /<a class="skip-link" href="#main" data-i18n="skipToContent">/);
assert.match(html, /<main class="workspace" id="main" tabindex="-1">/);
assert.match(css, /\.skip-link:focus/);
assert.match(css, /summary:focus-visible/);
assert.match(app, /focus\(\{preventScroll:true\}\)/);
assert.match(app, /const updated=typeof document==='undefined'/);

const start=app.indexOf('  let calendarExpanded=false;');
const end=app.indexOf('  async function markCalendarDose',start);
assert(start>0&&end>start);
let focusCount=0;
const state={};
function elem(tag='',cls='',value=''){return {tag,className:cls,textContent:value,children:[],attributes:{},listeners:{},classList:{toggle(){}},append(...x){this.children.push(...x);},replaceChildren(...x){this.children=[...x];},setAttribute(k,v){this.attributes[k]=v;},addEventListener(k,fn){this.listeners[k]=fn;},querySelector(cls){return this.children.find(c=>c.className===cls.slice(1));},focus(){focusCount++;}};}
const $=id=>state[id]||(state[id]=elem());
const entries=Array.from({length:9},(_,i)=>({date:'2026-10-15',name:'Test '+i,time:'08:00',status:'Taken',medId:'t'+i}));
const fixture={ $,elt:elem,localDate:()=> '2026-10-15',chosenMonth:'2026-10',chosenDay:'2026-10-15',
 people:[{id:'self',name:'Me'}],currentProfile:'self',allMedicines:[],allDoses:[],window:{MedimateReport:{records:()=>({days:new Map(),entries})}},
 t:k=>env.window.I18N.en[k]||k,Date,Number,String,Math,Set,document:{getElementById:ident=>$('monthly-calendar').children.find(x=>x.id===ident)}};
vm.createContext(fixture);vm.runInContext(app.slice(start,end)+'\nthis.draw=renderAdherence;',fixture);
fixture.draw();
let cell=$('monthly-calendar').children.find(x=>x.id==='calendar-day-2026-10-15');
const button=cell.children.find(x=>x.className==='calendar-more');
button.listeners.click({stopPropagation(){}});
assert.equal(focusCount,1,'New +N more/Show less control should recover keyboard focus');
console.log('Accessibility: skip-link, screen-reader translations, focused day expansion: PASS');

})();

(function(){

const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const read = name => fs.readFileSync(path.join(__medimate_root, 'static', name), 'utf8');
const app = read('app.js');
const html = read('index.html');
const translations = {window: {}};
vm.runInNewContext(read('translations.js'), translations);
const I18N = translations.window.I18N;


const uiKeys = [...html.matchAll(/data-i18n(?:-placeholder)?="([a-zA-Z0-9]+)"/g)].map(m => m[1]);
for (const locale of ['en', 'ta', 'zh', 'ms']) {
  for (const key of [...uiKeys, 'nameLengthError', 'safetyCollapsedReviewText']) {
    assert(I18N[locale][key]?.trim(), `${locale}: missing translation for ${key}`);
  }
  assert.match(I18N[locale].safetyWarningText, /\S/);
}
assert.match(html, /id="medicine-name"[^>]*maxlength="90"/);
const warning = /class="warning-banner safety-caution-line"[\s\S]*?<\/div>/.exec(html);
assert(warning, 'A single safety note should be visible before any results');
assert.equal((warning[0].match(/data-i18n=/g) || []).length, 1,
  'The always-visible caution should be one line, not a multi-part warning');
assert(html.indexOf('safety-caution-line') < html.indexOf('id="interaction-results"'));


const start = app.indexOf("  let lastRequestKey='");
const end = app.indexOf('  async function resolveUnknownInteractions', start);
assert(start > 0 && end > start);
const lookups = [];
let resets = 0;
const elements = new Map();
const getElement = id => {
  if (!elements.has(id)) elements.set(id, {textContent: '', replaceChildren() {}});
  return elements.get(id);
};
const fixture = {
  $: getElement,
  medicines: [{name: 'Sample A'}, {name: 'Sample B'}],
  currentProfile: 'self',
  selectedRxNormIds: () => ({}),
  onlineReport: null,
  onlineKey: '',
  onlinePendingKey: '',
  onlineFetchedAt: 0,
  onlineSeq: 0,
  interactionSeq: 0,
  interactionReport: null,
  drawCount: 0,
  drawInteractions() {this.drawCount++;},
  updateConflictNotice() {resets++;},
  async checkLabelsOnline() {},
  fetch: async (url, args) => {
    assert.equal(url, '/api/interactions');
    lookups.push(JSON.parse(args.body));
    return {ok: true, json: async () => ({status: 'ready', alerts: [], uncertain: [], unrecognized: []})};
  },
  Date,
};
vm.createContext(fixture);
vm.runInContext(`${app.slice(start, end)}\nthis.lookup = renderInteractions;`, fixture);
(async () => {
  await fixture.lookup();
  assert.equal(lookups.length, 1);
  await fixture.lookup();
  assert.equal(lookups.length, 1, 'Unchanged medicines should not cause repeat local lookups');
  fixture.medicines = [{name: 'Sample A'}, {name: 'Sample C'}];
  await fixture.lookup();
  assert.equal(lookups.length, 2, 'Changing a medicine requires fresh matching');
  fixture.currentProfile = 'sample-family';
  await fixture.lookup();
  assert.equal(lookups.length, 3, 'Family profiles cannot share cached results');
  assert(resets >= 3, 'Profile and identity changes must reset old warnings');


  const fdaStart = app.indexOf('  function displayOnlineReport(){');
  const fdaEnd = app.indexOf('  function drawInteractions(){', fdaStart);
  assert(fdaStart > 0 && fdaEnd > fdaStart);
  function node(tag, cls = '', text = '') {
    return {tag, className: cls, textContent: text, children: [],
      append(...items) {this.children.push(...items);},
      replaceChildren(...items) {this.children = [...items];},
      querySelector(selector) {return this.children.find(x => x.tag === selector) || null;}};
  }
  const list = node('div');
  const fda = {
    $: () => list, elt: node, t: key => I18N.en[key] || key,
    onlineConsent: true, lastRequestKey: 'same', onlineKey: 'same',
    onlineReport: {mentions: [{first: 'Sample A', second: 'Sample B', label_for: 'A',
      section: 'drug_interactions', excerpt: 'Synthetic mention only', source_url: 'https://example.test'}]},
  };
  vm.createContext(fda);
  vm.runInContext(`${app.slice(fdaStart, fdaEnd)}\nthis.display = displayOnlineReport;`, fda);
  fda.display();
  assert.equal(list.children[0].tag, 'details');
  assert.equal(list.children[0].open, false, 'Supplementary label excerpts must start collapsed');
  assert.equal(list.children[0].children[0].tag, 'summary');
  list.children[0].open = true;
  fda.display();
  assert.equal(list.children[0].open, true, 'Expanded references should stay open when rerendered');
  console.log('UI text, local lookup reuse, family isolation and collapsed evidence checks passed');
})().catch(err => {console.error(err);process.exitCode = 1;});

})();
