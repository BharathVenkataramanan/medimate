
(() => {
  'use strict';
  const DAY = 86400000;
  const datePattern = /^\d{4}-\d{2}-\d{2}$/;
  function dayNumber(iso){
    if(typeof iso!=='string'||!datePattern.test(iso))return NaN;
    const [y,m,d]=iso.split('-').map(Number);
    const stamp=Date.UTC(y,m-1,d);
    const chk=new Date(stamp);
    return chk.getUTCFullYear()===y&&chk.getUTCMonth()===m-1&&chk.getUTCDate()===d?Math.round(stamp/DAY):NaN;
  }
  function fromDay(n){return new Date(n*DAY).toISOString().slice(0,10);}
  function daysBetween(a,b){return dayNumber(b)-dayNumber(a);}
  function weekday(iso){return new Date(dayNumber(iso)*DAY).getUTCDay();}
  function normalize(s){
    if(!s || typeof s!=='object')return {frequency:'daily'};
    switch(s.frequency){
      case 'interval': return {frequency:'interval',everyDays:Number.isInteger(Number(s.everyDays))?Math.min(365,Math.max(1,Number(s.everyDays))):2};
      case 'weekly': return {frequency:'weekly',weekdays:[...new Set((Array.isArray(s.weekdays)?s.weekdays:[]).map(Number).filter(x=>Number.isInteger(x)&&x>=0&&x<=6))].sort((a,b)=>a-b)};
      case 'monthly':return {frequency:'monthly'};
      default:return {frequency:'daily'};
    }
  }
  function activeOn(m,date){
    const first=Array.isArray(m.scheduleVersions)&&m.scheduleVersions.length?m.scheduleVersions[0]:null;
    const start=first?.startDate||m.startDate||m.updatedAt?.slice(0,10)||date;
    if(!Number.isFinite(dayNumber(date)) || !Number.isFinite(dayNumber(start)) || date<start)return false;
    if(Array.isArray(m.periods)&&m.periods.length && !m.periods.some(p=>date>=p.start && date<=(p.end||'9999-12-31')))return false;
    if(m.active===false && m.endDate && date>m.endDate)return false;
    return true;
  }
  function versionOn(m,date){
    const versions=Array.isArray(m.scheduleVersions)?m.scheduleVersions:[];
    if(!versions.length)return {effectiveFrom:m.startDate||m.updatedAt?.slice(0,10)||date,startDate:m.startDate||m.updatedAt?.slice(0,10)||date,courseEndDate:m.courseEndDate||'',schedule:normalize(m.schedule),times:m.times||[]};
    return versions.filter(v=>v.effectiveFrom<=date).sort((a,b)=>a.effectiveFrom.localeCompare(b.effectiveFrom)).at(-1)||null;
  }
  function isScheduled(m,date){
    if(!activeOn(m,date))return false;
    const v=versionOn(m,date);if(!v)return false;
    const start=v.startDate||m.startDate||date;
    const elapsed=daysBetween(start,date);
    if(!Number.isFinite(elapsed)||elapsed<0||(v.courseEndDate&&date>v.courseEndDate))return false;
    const schedule=normalize(v.schedule);
    if(schedule.frequency==='daily')return true;
    if(schedule.frequency==='interval')return elapsed%schedule.everyDays===0;
    if(schedule.frequency==='weekly')return (schedule.weekdays.length?schedule.weekdays:[weekday(start)]).includes(weekday(date));
    if(schedule.frequency==='monthly'){
      const [sy,sm,sd]=start.split('-').map(Number),[y,mo,d]=date.split('-').map(Number);
      if(y<sy||(y===sy&&mo<sm))return false;
      const last=new Date(Date.UTC(y,mo,0)).getUTCDate();
      return d===Math.min(sd,last);
    }
    return false;
  }
  function timesOn(m,date){
    if(!isScheduled(m,date))return [];
    const v=versionOn(m,date);
    return Array.isArray(v.times)?v.times:(m.times||[]);
  }
  function progress(m,date){
    const start=m.startDate||m.updatedAt?.slice(0,10)||date;
    const end=m.courseEndDate||'';
    if(!end||!Number.isFinite(dayNumber(start))||!Number.isFinite(dayNumber(end))||end<start)return null;
    const total=daysBetween(start,end)+1;
    const elapsed=Math.min(total,Math.max(0,daysBetween(start,date)+1));
    return {total,elapsed,remaining:total-elapsed,percent:Math.round(elapsed/total*100),start,end};
  }
  window.MedimateSchedule={dayNumber,fromDay,daysBetween,weekday,normalize,activeOn,versionOn,isScheduled,timesOn,progress};
})();
