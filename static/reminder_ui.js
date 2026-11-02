
window.MedimateReminderUI = (() => {
  const el=id=>document.getElementById(id);
  const pad=n=>String(n).padStart(2,'0');
  let translate=k=>({removeTime:'Remove time',timeHour:'Hour',timeMinute:'Minute',timeAmPm:'AM/PM'})[k]||k;
  function option(value,label){const o=document.createElement('option');o.value=String(value);o.textContent=String(label);return o;}
  function add(time='08:00'){
    const container=el('medicine-times-picker');if(container.children.length>=12)return;
    const match=/^([01]\d|2[0-3]):([0-5]\d)$/.exec(time);
    const h=match?Number(match[1]):8, m=match?Number(match[2]):0;
    const row=document.createElement('div');row.className='time-picker-row';
    const hour=document.createElement('select');hour.className='time-hour';hour.setAttribute('aria-label',translate('timeHour'));
    for(let i=1;i<=12;i++)hour.append(option(i,i));hour.value=String(h%12||12);
    const minute=document.createElement('select');minute.className='time-minute';minute.setAttribute('aria-label',translate('timeMinute'));
    for(let i=0;i<60;i++)minute.append(option(i,pad(i)));minute.value=String(m);
    const period=document.createElement('select');period.className='time-period';period.setAttribute('aria-label',translate('timeAmPm'));
    period.append(option('AM','AM'),option('PM','PM'));period.value=h>=12?'PM':'AM';
    const remove=document.createElement('button');remove.type='button';remove.className='time-remove';remove.textContent='×';remove.title=translate('removeTime');remove.setAttribute('aria-label',translate('removeTime'));
    remove.addEventListener('click',()=>{row.remove();sync();updateButtons();});
    for(const select of [hour,minute,period])select.addEventListener('change',sync);
    row.append(hour,minute,period,remove);container.append(row);sync();updateButtons();
  }
  function updateButtons(){const container=el('medicine-times-picker');for(const row of container.children)row.querySelector('button').disabled=false;el('medicine-add-time').disabled=container.children.length>=12;}
  function getTimes(){return [...el('medicine-times-picker').children].map(row=>{const hour=Number(row.querySelector('.time-hour').value),minute=Number(row.querySelector('.time-minute').value);return pad((hour%12)+(row.querySelector('.time-period').value==='PM'?12:0))+':'+pad(minute);}).sort();}
  function sync(){el('medicine-times').value=[...new Set(getTimes())].join(', ');}
  function setTimes(times,translator){translate=translator||translate;el('medicine-times-picker').replaceChildren();const safe=Array.isArray(times)?times:[];for(const time of safe.slice(0,12))add(time);sync();}
  function init(translator){translate=translator||translate;el('medicine-add-time').addEventListener('click',()=>add('08:00'));setTimes([]);}
  return {init,setTimes,getTimes,sync};
})();
