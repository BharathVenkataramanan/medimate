'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const code=fs.readFileSync(require('node:path').join(__dirname,'../static/app.js'),'utf8');
const start=code.indexOf('  async function checkDue() {'),end=code.indexOf('\n  function download(',start);
assert(start>0&&end>start);
const source=code.slice(start,end);
(async()=>{
  const store=new Map(), elements=new Map(), sample={id:'m1|2026-10-31|08:00',time:'08:00',med:{name:'Example medicine'},done:false};
  let clock='2026-10-31T08:00:00', soundCount=0;
  class Clock extends Date {constructor(...args){super(...(args.length?args:[clock]));}}
  const Notification=function(){throw Error('OS notifications should not be needed for on-page sound');};
  Notification.permission='denied';
  for(const id of ['due-reminder-banner','due-reminder-title','due-reminder-message','due-reminder-time','due-reminder-taken'])elements.set(id,{hidden:true,textContent:'',onclick:null});
  const context={
    Date:Clock,Notification,window:{Notification},navigator:{},macEnabled:false,macInstalled:false,
    safetyAudioEnabled:true,gentleMedicinePing:()=>{soundCount++;return true;},
    localDate:()=>'2026-10-31',todayDoses:()=>[sample],t:key=>key,
    reminderReady:()=>true,
    reminderText:med=>med.name,toggleDose:async()=>{},toast:()=>{},
    $:id=>elements.get(id),localStorage:{
      getItem:key=>store.get(key)||null,setItem:(key,value)=>store.set(key,value),
      removeItem:key=>store.delete(key)
    }
  };
  vm.createContext(context);vm.runInContext(source+'\nthis.checkDue=checkDue;',context);
  await context.checkDue();await context.checkDue();
  assert.equal(soundCount,1,'do not repeat the sound inside one interval');
  assert.equal(elements.get('due-reminder-time').textContent,'08:00');
  assert.equal(elements.get('due-reminder-banner').hidden,false);
  assert.equal(typeof elements.get('due-reminder-taken').onclick,'function');
  clock='2026-10-31T08:15:00';await context.checkDue();
  assert.equal(soundCount,2,'repeat the soft ping after 15 minutes');
  context.macEnabled=true;context.macInstalled=true;clock='2026-10-31T08:30:00';
  await context.checkDue();
  assert.equal(soundCount,2,'native OS helper owns the sound if installed');
  sample.done=true;await context.checkDue();
  assert.equal(elements.get('due-reminder-banner').hidden,true,'taken doses hide the banner');
  console.log('On-page ping, 15-minute deduplication, helper suppression and banner: PASS');
})().catch(error=>{console.error(error);process.exitCode=1});
