'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const app=fs.readFileSync('static/app.js','utf8');
const html=fs.readFileSync('static/index.html','utf8');
const translations=fs.readFileSync('static/translations.js','utf8');

const start=app.indexOf('  const localDate =');
const end=app.indexOf('  const schedule =',start);
assert(start>=0&&end>start);
const context={Date};
vm.createContext(context);
vm.runInContext(app.slice(start,end)+'\nthis.reminderReady=reminderReady;',context);
const med={
  times:['08:00','21:00'],
  reminderActivatedAt:{'08:00':'2026-10-27T20:00:00','21:00':'2026-10-27T20:00:00'}
};
assert.equal(context.reminderReady(med,'2026-10-27','08:00'),false,'no retroactive alert');
assert.equal(context.reminderReady(med,'2026-10-27','21:00'),true,'future time today still fires');
assert.equal(context.reminderReady(med,'2026-10-28','08:00'),true,'next morning fires');

const hStart=app.indexOf('  function renderToday() {');
const hEnd=app.indexOf('  function scheduleDescription(',hStart);
assert(hStart>0&&hEnd>hStart);
const nodes=new Map();
const node=(tag,cls,text)=>({tag,cls,text,children:[],textContent:'',append(...x){this.children.push(...x);},
  replaceChildren(...x){this.children=x;}});
const home={
  medicines:[{id:'m1',name:'Fictional tablet',times:[],strength:'',quantity:null}],
  todayDoses:()=>[],doseDescription:()=>'',interactionCountText:()=>'',interactionReport:null,
  localDate:()=>'2026-10-27',schedule:{isScheduled:()=>true,timesOn:()=>[]},
  $:id=>{if(!nodes.has(id))nodes.set(id,node('div',id));return nodes.get(id);},
  elt:node,t:key=>key,emptyState:()=>node('div','empty')
};
vm.createContext(home);
vm.runInContext(app.slice(hStart,hEnd)+'\nthis.renderToday=renderToday;',home);
home.renderToday();
assert.equal(nodes.get('today-list').children.length,1,'untimed medicine appears on home');
assert.equal(nodes.get('today-list').children[0].children[2].text,'noReminderScheduled');
assert.equal(nodes.get('stat-today').textContent,'0/0','untimed medicine is not a dose');

assert.ok(app.includes("calendarEntries.push({medId:med.id,name:med.name,date,time:'',status:'Unscheduled'})"),
          'untimed medicine must appear on relevant calendar dates');
assert.ok(app.includes("if(med&&x.time)"),'no mark-taken or missed controls for unset dose times');
assert.ok(app.includes("const selected=calendarEntries.filter(x=>x.date===chosenDay)"));
assert.ok(app.includes('gain.gain.exponentialRampToValueAtTime(.14,start+.035)'),
          'browser reminder ping is louder than original');
assert.ok(html.includes('id="stop-medimate"'));
assert.ok(app.includes("'/api/app/stop'"));
const i18n={window:{}};
vm.runInNewContext(translations,i18n);
for(const lang of ['en','ta','zh','ms']){
  for(const key of ['stopAppTitle','stopAppButton','stopAppConfirm','stopAppDoneDesc','noReminderScheduled'])
    assert.ok(i18n.window.I18N[lang][key],lang+'/'+key);
}
console.log('PASS: next-day activation, untimed home/calendar, accessible labels, louder alerts and Stop button');
