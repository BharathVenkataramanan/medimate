
const __medimate_root = require("node:path").resolve(__dirname,"..");

(function(){
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const app=fs.readFileSync(__medimate_root+'/static/app.js','utf8');
const from=app.indexOf('  const actionableInteractionWarnings =');
const to=app.indexOf('  let lastRequestKey=',from);
const toggleStart=app.indexOf('  async function toggleInteractionReview(hit){');
const toggleEnd=app.indexOf('  function drawInteractions(){',toggleStart);
assert(from>0&&to>from&&toggleStart>to&&toggleEnd>toggleStart);
const source=app.slice(from,to)+app.slice(toggleStart,toggleEnd)+'\nthis.fn={updateConflictNotice,interactionCountText,isReviewedWarning,toggleInteractionReview,warningLedgerKey};';
const known={first:'Warfarin',second:'Bactrim',level:'Major',finding_type:'documented_interaction'};
const store=new Map();let sounds=0,confirmOK=true;
function fixture(profile='self',meds=[{name:'Warfarin',id:'w1',strength:'5 mg'},{name:'Bactrim',id:'b1'}]){
 const nodes=new Map(['conflict-nav-badge','conflict-stat-dot','conflict-toast','conflict-toast-title','conflict-toast-description'].map(k=>[k,{hidden:true,attrs:{},classList:{toggle(){}},setAttribute(n,v){this.attrs[n]=v;}}]));
 const node=id=>nodes.get(id);const nav={setAttribute(){}};
 const ctx={currentProfile:profile,medicines:meds,interactionReviews:new Map(store),safetyReviewStore:'interactionReviews',
  $:node, t:s=>s,Date,console,window:{confirm:()=>confirmOK},
  document:{querySelector:()=>nav},gentleSafetyChime:()=>{sounds++;},
  tx:async(_table,_mode,fn)=>fn({put:(v)=>{store.set(v.id,v);return {};}}),drawInteractions:()=>{},toast:()=>{throw Error('Unexpected toast')}
 };
 vm.createContext(ctx);vm.runInContext(source,ctx);
 return {ctx,nodes,fn:ctx.fn};
}
(async()=>{
 const a=fixture();const f=a.fn;
 assert.equal(f.interactionCountText({status:'ready',alerts:[known]}),'1');
 f.updateConflictNotice([known]);
 assert.equal(a.nodes.get('conflict-toast').hidden,false);
 assert.equal(sounds,1,'first real finding plays one chime');
 assert.equal(store.size,1,'first seen event persists');
 a.nodes.get('conflict-toast').hidden=true;
 f.updateConflictNotice([known]);
 assert.equal(a.nodes.get('conflict-toast').hidden,true,'same request must not repeat');
 assert.equal(sounds,1);
 const reloaded=fixture();reloaded.fn.updateConflictNotice([known]);
 assert.equal(reloaded.nodes.get('conflict-toast').hidden,true,'page reload must not replay');
 assert.equal(sounds,1);
 confirmOK=false;
 await reloaded.fn.toggleInteractionReview(known);
 assert.equal(reloaded.fn.isReviewedWarning(known),false,'cancel must preserve warning');
 confirmOK=true;
 await reloaded.fn.toggleInteractionReview(known);
 assert.equal(reloaded.fn.isReviewedWarning(known),true);
 assert.equal(reloaded.fn.interactionCountText({status:'ready',alerts:[known]}),'0','reviewed risks not in active count');
 assert.equal(store.size,1);
 const afterReview=fixture();
 assert.equal(afterReview.fn.isReviewedWarning(known),true,'review must persist across reload');
 await afterReview.fn.toggleInteractionReview(known);
 assert.equal(afterReview.fn.isReviewedWarning(known),false,'reopening restores warning');
 afterReview.nodes.get('conflict-toast').hidden=true;
 afterReview.fn.updateConflictNotice([known]);
 assert.equal(afterReview.nodes.get('conflict-toast').hidden,true,'reopening does not replay chime');
 const escalated={...known,level:'Contraindicated'};
 afterReview.fn.updateConflictNotice([escalated]);
 assert.equal(afterReview.nodes.get('conflict-toast').hidden,false,'new higher risk warns once');
 assert.equal(sounds,2);
 const newMedicine=fixture('self',[{name:'Warfarin',id:'w2'},{name:'Bactrim',id:'b1'}]);
 newMedicine.fn.updateConflictNotice([known]);
 assert.equal(sounds,3,'new medicine instance warns once');
 const newProfile=fixture('test-profile');newProfile.fn.updateConflictNotice([known]);
 assert.equal(sounds,4,'each family profile gets its own warning history');
 const missing={...known,reason:'no_documented_pair'};
 const firstCount=store.size;newProfile.fn.updateConflictNotice([missing]);
 assert.equal(store.size,firstCount,'missing evidence does not trigger notifications');
 console.log('PASS: one-time chime, local persistence, per-profile review archive, cancellation, reactivation and escalation');
})().catch(e=>{console.error(e);process.exitCode=1;});

})();

(function(){

'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const app=fs.readFileSync(path.join(__medimate_root,'static/app.js'),'utf8');
const a=app.indexOf('  const actionableInteractionWarnings =');
const b=app.indexOf('  function hideConflictToast()',a);
const c=app.indexOf('  function drawInteractions(){');
const d=app.indexOf('\n  function render(){',c);
assert(a>=0 && b>a && c>b && d>c);
const source=app.slice(a,b)+'\n'+app.slice(c,d);
const translationContext={window:{}};
vm.runInNewContext(fs.readFileSync(path.join(__medimate_root,'static/translations.js'),'utf8'),translationContext);
const t=k=>translationContext.window.I18N.en[k]||k;
function node(tag,cl='',text=''){
  return {tag,className:cl,textContent:text,children:[],hidden:false,
    append(...nodes){this.children.push(...nodes);},addEventListener(){},replaceChildren(...nodes){this.children=[...nodes];},
    setAttribute(name,v){this[name]=v;}};
}
function descendants(root){return [root,...root.children.flatMap(descendants)];}
function text(root){return [root.textContent,...root.children.map(text)].join(' ');}
function run(alerts,uncertain=[]){
  const elements=new Map(['interaction-results','safety-count','stat-flags'].map(id=>[id,node('div')]));
  const notices=[];
  const context={elt:node,$:id=>elements.get(id),t,medicines:[{name:'Co-trimoxazole'},{name:'warfarin'},{name:'Anarex'}],
    interactionReport:{status:'ready',alerts,uncertain,unrecognized:[]},
    currentProfile:'self',interactionReviews:new Map(),
    quietAfterArchive:false,updateConflictNotice:problems=>notices.push(problems),
    emptyState:()=>node('p')};
  vm.runInNewContext(source+'\ndrawInteractions();',context);
  return {nodes:descendants(elements.get('interaction-results')),text:text(elements.get('interaction-results')),
    badge:elements.get('safety-count').textContent,stat:elements.get('stat-flags').textContent,
    problems:notices[0],merge:context.mergeActionableWarnings};
}
const sulfa={first:'Co-trimoxazole',second:'warfarin',ingredient_a:'Sulfamethoxazole',ingredient_b:'Warfarin',
  level:'Major',finding_type:'ddinter_severity_only',effects:'DDInter has no mechanism',
  advice:'Ask pharmacist',evidence_sources:[{label:'DDInter',url:'https://ddinter.test'}]};
const trim={first:'Co-trimoxazole',second:'warfarin',ingredient_a:'Trimethoprim',ingredient_b:'Warfarin',
  level:'Major',finding_type:'documented_interaction',rule_code:'test_bactrim',
  effects:'Increases anticoagulant effects and bleeding risk',
  advice:'Arrange INR monitoring',evidence_sources:[{label:'NHS',url:'https://nhs.test'}]};
const result=run([sulfa,trim]);
assert.equal(result.badge,'1','Two ingredient warnings should count once');
assert.equal(result.stat,'1');
assert.equal(result.nodes.filter(n=>n.className==='interaction-row').length,1,'Must show one card');
assert.equal(result.problems.length,1,'Only one notification is allowed for this medicine pair');
assert.match(result.text,/Sulfamethoxazole \+ Warfarin/);
assert.match(result.text,/Trimethoprim \+ Warfarin/);
assert.match(result.text,/Increases anticoagulant effects and bleeding risk/);
assert.doesNotMatch(result.text,/DDInter has no mechanism/,'Curated effect should replace the generic DDInter disclaimer');
assert.equal(result.nodes.filter(n=>n.tag==='a' && n.className==='source-link').length,2,
  'Both the DDInter and prescribing-reference sources must remain accessible');
const reverse=run([sulfa,{...trim,first:' WARFARIN ',second:'co-TRIMOXAZOLE'}]);
assert.equal(reverse.badge,'1','Order and case must not cause duplicate warnings');
const aspirin={...trim,first:'Anarex',second:'warfarin',ingredient_a:'Acetaminophen',
  effects:'An unrelated risk',evidence_sources:[{label:'Different source',url:'https://other.test'}]};
const another=run([sulfa,trim,aspirin]);
assert.equal(another.badge,'2','Different medicine pairs must NOT be merged');
assert.equal(another.nodes.filter(n=>n.className==='interaction-row').length,2);
const overlap={...sulfa,first:'Co-trimoxazole',second:'warfarin',finding_type:'duplicate_ingredient',
  ingredient_a:'Warfarin',ingredient_b:'Warfarin',level:'Review duplicate ingredient'};
const distinctCategory=run([sulfa,trim,overlap]);
assert.equal(distinctCategory.badge,'2','Duplicate active ingredients need a separate safety category');
assert.equal(distinctCategory.nodes.filter(n=>n.className==='interaction-row').length,2);
const noRecord=run([], [{first:'Co-trimoxazole',second:'warfarin',reason:'no_documented_pair'}]);
assert.equal(noRecord.badge,'0','Missing evidence must not become a warning');

assert.equal([sulfa,trim].length,2);
console.log('PASS: co-trimoxazole + warfarin is one visible warning; sources, ingredients, and unrelated safety alerts preserved');

})();

(function(){

const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const src=fs.readFileSync(__medimate_root+'/static/app.js','utf8');
const source=(from,to)=>{
  const begin=src.indexOf(from),end=src.indexOf(to,begin);
  assert(begin>=0&&end>begin, 'Missing app section: '+from);
  return src.slice(begin,end);
};
const filter=source('  const actionableInteractionWarnings =','  function hideConflictToast()');
const notices=source('  function hideConflictToast()','  let lastRequestKey=');
const make=()=>({hidden:true,textContent:'',attrs:{},classList:{toggle(){}},setAttribute(k,v){this.attrs[k]=v;}});
const nodes=Object.fromEntries(['conflict-nav-badge','conflict-stat-dot','conflict-toast',
  'conflict-toast-title','conflict-toast-description'].map(id=>[id,make()]));
const ctx={
  $:id=>nodes[id], t:key=>key,previousConflictSignature:null,
  currentProfile:'self',medicines:[],interactionReviews:new Map(),safetyReviewStore:'interactionReviews',Date,
  tx:()=>Promise.resolve(),gentleSafetyChime:()=>{},
  document:{querySelector:sel=>{assert.equal(sel,'[data-page="interactions"]');return make();}}
};
vm.createContext(ctx);
vm.runInContext(`${filter}\n${notices}\nthis.update=updateConflictNotice;this.policy=actionableInteractionWarnings;`,ctx);
const finding=(first,second)=>({first,second,ingredient_a:first,ingredient_b:second,
  finding_type:'ddinter_severity_only',level:'Moderate'});
const p=finding('Penicillin','Warfarin');
const unrelated=finding('Sample A','Sample B');
const missing={...p,reason:'no_documented_pair'};
const unknown={...p,reason:'level_unknown',level:'Unknown'};
ctx.update([missing,unknown]);
assert.equal(nodes['conflict-toast'].hidden,true,'Undocumented penicillin must not popup');
assert.equal(nodes['conflict-nav-badge'].hidden,true);
ctx.update([p]);
assert.equal(nodes['conflict-toast'].hidden,false,'Documented penicillin-warfarin pair must remain visible');
assert.equal(nodes['conflict-nav-badge'].hidden,false);

nodes['conflict-toast'].hidden=true;
ctx.update([p,unrelated]);
assert.equal(nodes['conflict-toast'].hidden,false,'New documented pair warrants notification');
nodes['conflict-toast'].hidden=true;


ctx.update([],true);
assert.equal(nodes['conflict-nav-badge'].hidden,true,'Old badge clears immediately');
ctx.update([unrelated]);
assert.equal(nodes['conflict-nav-badge'].hidden,false,'Real remaining warning still counted');
assert.equal(nodes['conflict-toast'].hidden,true,'Archiving must not re-trigger remaining pair');


ctx.update([unrelated, p],false,true);
assert.equal(nodes['conflict-nav-badge'].hidden,false);
assert.equal(nodes['conflict-toast'].hidden,true,'Archive-triggered async warning must be silent');

ctx.update([],true);
ctx.update([]);
assert.equal(nodes['conflict-nav-badge'].hidden,true);
assert.equal(nodes['conflict-toast'].hidden,true);

ctx.update([p]);
assert.equal(nodes['conflict-toast'].hidden,true,'Previously seen warning must never sound or popup again after refresh or archive');


const archive=source('  async function removeMedicine(med){','  function renderAdherence(){');
assert.match(archive,/quietAfterArchive=true;\+\+interactionSeq;hideConflictToast\(\);await refresh\(\)/);
assert.doesNotMatch(archive,/toast\(t\('archived'\)\)/);
const render=source('  async function renderInteractions(){','  async function resolveUnknownInteractions(');
assert.match(render,/updateConflictNotice\(\[\],true\)/);
const serviceWorker=fs.readFileSync(__medimate_root+'/static/sw.js','utf8');
assert.match(serviceWorker,/caches\.keys\(\)/,'old caches are purged');
assert.doesNotMatch(serviceWorker,/addEventListener\('fetch'/,'never return old app code or styling');
console.log('Archive/no-record/new-evidence notification regression checks passed');

})();

(function(){

const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const code = fs.readFileSync(require('node:path').join(__medimate_root, 'static/app.js'), 'utf8');
const start = code.indexOf('  async function checkDue() {');
const end = code.indexOf('\n  function download(', start);
assert(start >= 0 && end > start, 'checkDue function not found');
const checkDueSource = code.slice(start, end);

async function exercise({hidden, enabled = false, permission = 'granted'}) {
  const posted = [];
  const values = new Map();
  class TestDate extends Date {
    constructor(...args) { super(...(args.length ? args : ['2026-10-18T10:25:00'])); }
  }
  function TestNotification() {}
  TestNotification.permission = permission;
  const context = {
    Date: TestDate,
    macEnabled: enabled,
    macInstalled: enabled,
    safetyAudioEnabled: false,
    gentleMedicinePing: () => true,
    window: {Notification: TestNotification},
    Notification: TestNotification,
    document: {visibilityState: hidden ? 'hidden' : 'visible'},
    navigator: {serviceWorker: {getRegistration: async () => ({
      showNotification: async (_title, options) => { posted.push(options.tag); },
    })}},
    $: () => null,
    localDate: () => '2026-10-18',
    reminderDueAfterActivation: () => true,
    todayDoses: () => [{id: 'med1|2026-10-18|10:25', time: '10:25',
                        med: {name: 'Example medicine'}, done: false}],
    reminderText: med => `Reminder for ${med.name}`,
    localStorage: {
      getItem: key => values.get(key) ?? null,
      setItem: (key, value) => values.set(key, value),
      removeItem: key => values.delete(key),
    },
  };
  vm.createContext(context);
  vm.runInContext(`${checkDueSource}\nthis.invokeCheckDue = checkDue;`, context);
  await context.invokeCheckDue();
  await context.invokeCheckDue();
  return posted;
}

(async () => {
  assert.deepEqual(await exercise({hidden: true}), ['med1|2026-10-18|10:25']);
  assert.deepEqual(await exercise({hidden: false}), ['med1|2026-10-18|10:25']);
  assert.deepEqual(await exercise({hidden: true, enabled: true}), []);
  assert.deepEqual(await exercise({hidden: true, permission: 'denied'}), []);
  console.log('Background-tab reminder checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });

})();
