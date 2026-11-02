'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.resolve(__dirname,'..'),read=file=>fs.readFileSync(path.join(root,file),'utf8');
const html=read('static/index.html'),app=read('static/app.js'),sw=read('static/sw.js'),ui=read('static/reminder_ui.js');

assert.match(html,/id="medicine-times" type="hidden" value=""/,'a blank reminder time is the initial state');
assert.match(html,/styles\.css\?v=/,'stylesheet must request the current edition');
assert.match(html,/reminder_ui\.js\?v=/);
assert.match(html,/app\.js\?v=/);

function node(tag){
  const n={tag,children:[],listeners:{},className:'',value:'',disabled:false,
    append(...kids){for(const c of kids){c.parent=this;this.children.push(c);}},
    replaceChildren(...kids){for(const c of this.children)c.parent=null;this.children=[];this.append(...kids);},
    remove(){if(this.parent){this.parent.children=this.parent.children.filter(x=>x!==this);this.parent=null;}},
    addEventListener(name,fn){this.listeners[name]=fn;},
    setAttribute(name,value){this[name]=value;},
    querySelector(selector){return this.children.find(x=>selector.startsWith('.')?x.className===selector.slice(1):x.tag===selector);}};
  return n;
}
const elements={
  'medicine-times-picker':node('div'),
  'medicine-add-time':node('button'),
  'medicine-times':node('input')
};
const context={window:{},document:{
  getElementById:id=>elements[id],createElement:node
}};
vm.runInNewContext(ui,context);
const picker=context.window.MedimateReminderUI;
picker.init(k=>k);
assert.equal(elements['medicine-times-picker'].children.length,0,'new medicine has zero times');
assert.equal(elements['medicine-times'].value,'','hidden times input has no implicit 08:00');
assert.equal(elements['medicine-add-time'].disabled,false);
elements['medicine-add-time'].listeners.click();
assert.equal(elements['medicine-times-picker'].children.length,1,'time added only on explicit click');
assert.equal(elements['medicine-times'].value,'08:00');
const remove=elements['medicine-times-picker'].children[0].querySelector('button');
assert.equal(remove.disabled,false,'the final time can be removed');
remove.listeners.click();
assert.equal(elements['medicine-times-picker'].children.length,0);
assert.equal(elements['medicine-times'].value,'');
picker.setTimes(['16:30']);
assert.equal(elements['medicine-times'].value,'16:30','existing schedules remain unchanged');
picker.setTimes([]);
assert.equal(elements['medicine-times'].value,'','editing an unscheduled medicine stays unscheduled');

// Saving an empty list must be valid, not substituted with 8 AM.
const parseStart=app.indexOf('  function parseTimes(s) {');
const parseEnd=app.indexOf('  async function saveMedicine(',parseStart);
assert(parseStart>0&&parseEnd>parseStart);
const pctx={sortTimes:times=>[...new Set(times)].sort()};
vm.createContext(pctx);
vm.runInContext(app.slice(parseStart,parseEnd)+'\nthis.parseTimes=parseTimes;',pctx);
assert.deepEqual(Array.from(pctx.parseTimes('')),[]);
assert.deepEqual(Array.from(pctx.parseTimes('16:30')),['16:30']);
assert.equal(pctx.parseTimes('25:00'),null);

// No web cache should resurrect stale HTML/CSS/JS. Keep notification click support.
const events={},cacheDeleted=[];
const worker={
  self:{addEventListener:(name,fn)=>{events[name]=fn;},skipWaiting:()=>Promise.resolve(),
    clients:{claim:()=>Promise.resolve(),matchAll:()=>Promise.resolve([]),openWindow:()=>Promise.resolve()}},
  caches:{keys:async()=>['medimate-shell-reviewed-20261027','other-app'],
    delete:async(key)=>{cacheDeleted.push(key);return true;}}
};
vm.runInNewContext(sw,worker);
assert.equal(events.fetch,undefined,'service worker cannot serve an outdated app shell');
assert.equal(typeof events.notificationclick,'function');
let activated;
events.activate({waitUntil:p=>{activated=p;}});
(async()=>{
  await activated;
  assert.deepEqual(cacheDeleted,['medimate-shell-reviewed-20261027']);
  console.log('PASS: optional reminder times, existing schedules and fresh browser assets');
})().catch(err=>{console.error(err);process.exitCode=1});
