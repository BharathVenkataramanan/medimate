
const __medimate_root = require("node:path").resolve(__dirname,"..");

(function(){

const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const ctx=vm.createContext({window:{},TextEncoder,TextDecoder,Uint8Array,DataView,Date});
for(const f of ['schedule.js','report.js'])vm.runInContext(fs.readFileSync(__medimate_root+'/static/'+f,'utf8'),ctx);
const person={id:'self',name:'Demo'};
const medicines=Array.from({length:12},(_,i)=>({id:'med'+i,name:'Example medicine '+(i+1),profileId:'self',startDate:'2026-10-15',times:['08:00'],active:true,schedule:{frequency:'daily'}}));
medicines.push({id:'someone-else',name:'Private medicine',profileId:'family2',startDate:'2026-10-15',times:['08:00'],active:true,schedule:{frequency:'daily'}});
const doses=[
{id:'med0|2026-10-15|08:00',medId:'med0',date:'2026-10-15',time:'08:00',status:'taken'},
{id:'med1|2026-10-15|08:00',medId:'med1',date:'2026-10-15',time:'08:00',status:'missed'}];
const result=ctx.window.MedimateReport.build(person,medicines,doses,2026,10,new Date('2026-10-16T13:00:00+08:00'));
const files=new Map(),buf=Buffer.from(result.xlsx);let offset=0;
while(offset+30<buf.length&&buf.readUInt32LE(offset)===0x04034b50){
 const n=buf.readUInt16LE(offset+26),extra=buf.readUInt16LE(offset+28),size=buf.readUInt32LE(offset+18);
 const name=buf.subarray(offset+30,offset+30+n).toString(),pos=offset+30+n+extra;
 files.set(name,buf.subarray(pos,pos+size).toString());offset=pos+size;
}
const month=files.get('xl/worksheets/sheet1.xml'),detail=files.get('xl/worksheets/sheet2.xml'),styles=files.get('xl/styles.xml');
assert(month&&detail&&styles,'Both sheets and styles should exist');
for(let i=1;i<=12;i++)assert(month.includes('Example medicine '+i+' · 08:00'),`Missing dose ${i}`);
for(const value of ['Taken','Missed','Not logged']){assert(month.includes('· '+value));assert(detail.includes('>'+value+'</t>'));}
assert(!month.includes('Private medicine')&&!detail.includes('Private medicine'),'No family data leakage');
assert(!month.includes('Upcoming')&&!detail.includes('Upcoming'),'Future should display Not logged');
for(const [name,style] of [['Example medicine 1',3],['Example medicine 2',4],['Example medicine 3',5]]){
 assert(new RegExp(`<c r="[A-G]\\d+" s="${style}"[^>]*>[^<]*<is><t[^>]*>${name} · 08:00`).test(month),`Medicine ${name} does not have distinct background style ${style}`);
}
assert.equal((styles.match(/<name val="Arial"\/>/g)||[]).length,6,'Every font must use Arial');
for(const rgb of ['FFDDEFE3','FFFADBDD','FFFFE6A4'])assert(styles.includes(rgb),`Missing color ${rgb}`);
assert(!/Total doses|left to be taken|explanation/i.test(month+detail),'No counts or explanations');
assert.equal(result.summary.Taken,1);assert.equal(result.summary.Missed,1);
assert(result.summary['Not logged']>0&&result.summary.Upcoming>0,'Internal schedule statuses remain accurate');
assert.equal((detail.match(/<row r="\d+"/g)||[]).length-3,result.entries.length,'Every scheduled dose has a detail row');
console.log('Workbook: mixed status colors per medicine, all doses every day, Arial PASS');

})();

(function(){

const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const app=fs.readFileSync(__medimate_root+'/static/app.js','utf8');
const html=fs.readFileSync(__medimate_root+'/static/index.html','utf8');
const css=fs.readFileSync(__medimate_root+'/static/styles.css','utf8');
const tr=fs.readFileSync(__medimate_root+'/static/translations.js','utf8');
assert(html.includes('id="calendar-expand"'));
assert(css.includes('expanded-day .calendar-med-name') && css.includes('align-items:start'));
const i18n={window:{}};vm.runInNewContext(tr,i18n);
for(const locale of ['en','ta','zh','ms'])for(const key of ['calendarMore','calendarLess','calendarExpand','calendarCollapse'])assert(i18n.window.I18N[locale][key],locale+' lacks '+key);
const state={};
function elem(tag='',cls='',value=''){return {tag,className:cls,textContent:value,children:[],attributes:{},listeners:{},classList:{state:new Set(),toggle(k,on){if(on)this.state.add(k);else this.state.delete(k);},contains(k){return this.state.has(k);}},append(...x){this.children.push(...x);},replaceChildren(...x){this.children=[...x];},setAttribute(k,v){this.attributes[k]=v;},addEventListener(k,fn){this.listeners[k]=fn;}};}
const $=id=>state[id]||(state[id]=elem());
const chosenDay='2026-10-15';const entries=[];
for(const day of ['2026-10-15','2026-10-16'])for(let i=0;i<9;i++)entries.push({date:day,name:`Med ${day} #${i+1}`,time:'08:00',status:i===0?'Missed':'Taken',medId:`${day}|${i}`});
const data={days:new Map(),entries};
const context=vm.createContext({$,elt:elem,localDate:()=>chosenDay,chosenMonth:'2026-10',chosenDay,
 people:[{id:'self',name:'Me'}],currentProfile:'self',allMedicines:[],allDoses:[],
 window:{MedimateReport:{records:()=>data}},t:k=>i18n.window.I18N.en[k]||k,Date,Number,String,Math,Set});
const start=app.indexOf('  let calendarExpanded=false;'),stop=app.indexOf('  async function markCalendarDose',start);
assert(start>0&&stop>start,'Calendar segment must exist');
vm.runInContext(app.slice(start,stop)+'\nthis.functions={renderAdherence,toggleCalendarExpanded};',context);
const getDay=day=>$('monthly-calendar').children.find(x=>x.id==='calendar-day-'+day);
const pills=day=>getDay(day).children.filter(c=>c.className.startsWith('calendar-med-name'));
const button=day=>getDay(day).children.find(c=>c.className==='calendar-more');
context.functions.renderAdherence();
assert.equal(pills('2026-10-15').length,5);
assert.equal(pills('2026-10-16').length,5);
assert(button('2026-10-15').textContent.includes('+4'));
let stopped=false;button('2026-10-15').listeners.click({stopPropagation(){stopped=true;}});
assert(stopped);
assert.equal(pills('2026-10-15').length,9,'Clicked date expands');
assert.equal(pills('2026-10-16').length,5,'Other date must stay compact');
assert(getDay('2026-10-15').className.includes('expanded-day'));
assert(!getDay('2026-10-16').className.includes('expanded-day'));
assert.equal(button('2026-10-15').textContent,'Show less');
assert.equal(button('2026-10-15').attributes['aria-expanded'],'true');
assert.equal(button('2026-10-16').attributes['aria-expanded'],'false');
assert.equal($('calendar-expand').attributes['aria-expanded'],'false','Global toggle must not be changed');
button('2026-10-16').listeners.click({stopPropagation(){}});
assert.equal(pills('2026-10-15').length,9);
assert.equal(pills('2026-10-16').length,9);
button('2026-10-15').listeners.click({stopPropagation(){}});
assert.equal(pills('2026-10-15').length,5,'Per-day collapse works');
assert.equal(pills('2026-10-16').length,9,'Other expanded date remains expanded');
context.functions.toggleCalendarExpanded();
assert.equal($('calendar-expand').attributes['aria-expanded'],'true','Explicit Show all expands whole month');
assert.equal(pills('2026-10-15').length,9);
assert.equal(pills('2026-10-16').length,9);
context.functions.toggleCalendarExpanded();
assert.equal($('calendar-expand').attributes['aria-expanded'],'false');
assert.equal(pills('2026-10-15').length,5);
assert.equal(pills('2026-10-16').length,5);
console.log('Single-day +4 expansion/collapse, independent dates, global toggle and four translations: PASS');

})();
