

(() => {
 'use strict';
 const utf8 = value => new TextEncoder().encode(value);
 const xml = s => String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&apos;').replace(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g,'');
 const dayString = (y,m,d) => `${y}-${String(m).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
 const colName=n => {let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
 const STYLE={normal:0,title:1,header:2,taken:3,missed:4,unconfirmed:5,upcoming:6,empty:7,info:8,day:9};
 function cell(r,c,value,style=0){
   if(value===null || value===undefined || value==='')return '';
   const ref=colName(c)+r, val=typeof value==='number'?`<v>${value}</v>`:`<is><t xml:space="preserve">${xml(value)}</t></is>`;
   return `<c r="${ref}" s="${style}" t="${typeof value==='number'?'n':'inlineStr'}">${val}</c>`;
 }
 function worksheet(rows, widths, merges=[], freezing=0, rowHeights=[]) {
   const rxml=rows.map((entries,idx)=>`<row r="${idx+1}" ht="${rowHeights[idx] || (idx===0?35:idx===1?25:22)}" customHeight="1">${entries.map(([v,sty],i)=>cell(idx+1,i,v,sty||0)).join('')}</row>`).join('');
   const cols=widths.map((w,i)=>`<col min="${i+1}" max="${i+1}" width="${w}" customWidth="1"/>`).join('');
   return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0">${freezing?`<pane ySplit="${freezing}" topLeftCell="A${freezing+1}" activePane="bottomLeft" state="frozen"/>`:''}</sheetView></sheetViews><sheetFormatPr defaultRowHeight="21"/><cols>${cols}</cols><sheetData>${rxml}</sheetData>${merges.length?`<mergeCells count="${merges.length}">${merges.map(x=>`<mergeCell ref="${x}"/>`).join('')}</mergeCells>`:''}<pageMargins left="0.25" right="0.25" top="0.35" bottom="0.35" header="0.2" footer="0.2"/></worksheet>`;
 }
 function records(person,medicines,doses,year,month,today=new Date()){
   const begin=dayString(year,month,1), end=dayString(year,month,new Date(year,month,0).getDate());
   const cutoff=dayString(today.getFullYear(),today.getMonth()+1,today.getDate());
   const timeNow=String(today.getHours()).padStart(2,'0')+':'+String(today.getMinutes()).padStart(2,'0');
   const byId=new Map(doses.map(x=>[x.id,x]));
   const schedule=window.MedimateSchedule;
   const entries=[], days=new Map();
   for(const med of medicines.filter(m=>(m.profileId||'self')===person.id)){
     for(let d=1;d<=new Date(year,month,0).getDate();d++){
       const date=dayString(year,month,d);
       for(const time of schedule.timesOn(med,date)){
         const id=`${med.id}|${date}|${time}`, rec=byId.get(id);
         let status;
         if(rec?.status==='missed')status='Missed';
         else if(rec?.status==='taken' || rec?.takenAt)status='Taken';
         else if(date>cutoff || (date===cutoff && time>timeNow))status='Upcoming';
         else status='Not logged';
         entries.push({medId:med.id,date, name:med.name, strength:med.strength||'',time,status});
         if(!days.has(date))days.set(date,{Taken:0,Missed:0,'Not logged':0,Upcoming:0});
         days.get(date)[status]++;
       }
     }
   }
   entries.sort((a,b)=>a.date.localeCompare(b.date)||a.time.localeCompare(b.time)||a.name.localeCompare(b.name));
   return {entries,days,begin,end};
 }
 const styles=`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="6"><font><sz val="11"/><name val="Arial"/><color rgb="FF33433E"/></font><font><sz val="18"/><b/><name val="Arial"/><color rgb="FF33433E"/></font><font><sz val="11"/><b/><name val="Arial"/><color rgb="FF39594C"/></font><font><sz val="11"/><b/><name val="Arial"/><color rgb="FFA33346"/></font><font><sz val="10"/><name val="Arial"/><color rgb="FF65756B"/></font><font><sz val="11"/><b/><name val="Arial"/><color rgb="FF855B00"/></font></fonts><fills count="8"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFE9F1E7"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFF0F4EE"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFDDEFE3"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFFADBDD"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFFFE6A4"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFF1F0ED"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="10"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="2" fillId="2" borderId="0" xfId="0"/><xf numFmtId="0" fontId="2" fillId="4" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf><xf numFmtId="0" fontId="3" fillId="5" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf><xf numFmtId="0" fontId="5" fillId="6" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf><xf numFmtId="0" fontId="4" fillId="7" borderId="0" xfId="0"/><xf numFmtId="0" fontId="4" fillId="3" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf><xf numFmtId="0" fontId="4" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="2" fillId="3" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center"/></xf></cellXfs></styleSheet>`;
 const enc32=v=>{const a=new Uint8Array(4);new DataView(a.buffer).setUint32(0,v,true);return a;};
 const enc16=v=>{const a=new Uint8Array(2);new DataView(a.buffer).setUint16(0,v,true);return a;};
 const crcTable=Array.from({length:256},(_,n)=>{for(let k=0;k<8;k++)n=(n&1)?0xEDB88320^(n>>>1):(n>>>1);return n>>>0;});
 const crc32=b=>{let crc=0xFFFFFFFF;for(const byte of b)crc=crcTable[(crc^byte)&255]^(crc>>>8);return (crc^0xFFFFFFFF)>>>0;};
 function zip(entries){
   const out=[],central=[];let offset=0;
   for(const [name,contents] of entries){const n=utf8(name),b=utf8(contents),crc=crc32(b);
    const local=[enc32(0x04034b50),enc16(20),enc16(0),enc16(0),enc16(0),enc16(0),enc32(crc),enc32(b.length),enc32(b.length),enc16(n.length),enc16(0),n,b];
    out.push(...local);
    central.push(enc32(0x02014b50),enc16(20),enc16(20),enc16(0),enc16(0),enc16(0),enc16(0),enc32(crc),enc32(b.length),enc32(b.length),enc16(n.length),enc16(0),enc16(0),enc16(0),enc16(0),enc32(0),enc32(offset),n);
    offset+=local.reduce((x,v)=>x+v.length,0);
   }
   const len=central.reduce((x,v)=>x+v.length,0);
   const parts=[...out,...central,enc32(0x06054b50),enc16(0),enc16(0),enc16(entries.length),enc16(entries.length),enc32(len),enc32(offset),enc16(0)];
   const data=new Uint8Array(parts.reduce((x,v)=>x+v.length,0));let p=0;for(const part of parts){data.set(part,p);p+=part.length;}return data;
 }
 function build(person,medicines,doses,year,month,today=new Date()){
   const {entries}=records(person,medicines,doses,year,month,today);
   if(entries.length>45000)throw new Error('too_many_rows');
   const tag=`${year}-${String(month).padStart(2,'0')}`;
   const summary={Taken:0,Missed:0,'Not logged':0,Upcoming:0};
   for(const row of entries)summary[row.status]++;


   const displayStatus=s=>s==='Upcoming'?'Not logged':s;
   const statusStyle=s=>s==='Missed'?STYLE.missed:s==='Taken'?STYLE.taken:STYLE.unconfirmed;
   const perDate=new Map();
   for(const item of entries){
     if(!perDate.has(item.date))perDate.set(item.date,[]);
     perDate.get(item.date).push(item);
   }
   const rows=[
     [[`Medication calendar · ${tag}`,STYLE.title]],
     [[`Family member: ${person.name}`,STYLE.info]],
     ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map(x=>[x,STYLE.header])
   ];
   const rowHeights=[36,25,26];
   const daysIn=new Date(year,month,0).getDate(),offset=(new Date(year,month-1,1).getDay()+6)%7;
   for(let week=0;week<Math.ceil((offset+daysIn)/7);week++){
     const dates=Array.from({length:7},(_,c)=>{
       const day=week*7+c-offset+1;
       return day>=1&&day<=daysIn?dayString(year,month,day):null;
     });


     rows.push(dates.map(day=>[day?String(Number(day.slice(-2))):'',day?STYLE.day:STYLE.empty]));
     rowHeights.push(28);
     const grouped=dates.map(day=>day?(perDate.get(day)||[]):[]);
     const maxEntries=Math.max(1,...grouped.map(list=>list.length));
     for(let r=0;r<maxEntries;r++){
       const line=grouped.map(list=>{
         const item=list[r];
         return item?[`${item.name} · ${item.time} · ${displayStatus(item.status)}`,statusStyle(item.status)]:['',STYLE.empty];
       });
       rows.push(line);
       const wrap=Math.max(1,...line.map(([value])=>value?Math.ceil(value.length/28):1));
       rowHeights.push(Math.min(130,Math.max(31,wrap*17+9)));
     }
   }
   const detail=[
     [[`Medication doses · ${tag}`,STYLE.title]],
     [[`Family member: ${person.name}`,STYLE.info]],
     [['Date',STYLE.header],['Medicine',STYLE.header],['Time',STYLE.header],['Status',STYLE.header]]
   ];
   const detailHeights=[36,25,26];
   for(const item of entries){
     const sty=statusStyle(item.status),label=displayStatus(item.status);

     detail.push([[item.date,sty],[item.name,sty],[item.time,sty],[label,sty]]);
     detailHeights.push(Math.min(65,Math.max(24,Math.ceil(item.name.length/42)*17+7)));
   }

   const payload=[
    ['[Content_Types].xml','<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'],
    ['_rels/.rels','<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'],
    ['xl/workbook.xml','<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Monthly calendar" sheetId="1" r:id="rId1"/><sheet name="Dose details" sheetId="2" r:id="rId2"/></sheets></workbook>'],
    ['xl/_rels/workbook.xml.rels','<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'],
    ['xl/styles.xml',styles],
    ['xl/worksheets/sheet1.xml',worksheet(rows,[34,34,34,34,34,34,34],['A1:G1','A2:G2'],3,rowHeights)],
    ['xl/worksheets/sheet2.xml',worksheet(detail,[17,43,14,20],['A1:D1','A2:D2'],3,detailHeights)],
   ];
   return {xlsx:zip(payload),filename:`medication-calendar-${tag}-${person.name.replace(/[^a-z0-9_-]/gi,'_').slice(0,30)||'family'}.xlsx`,summary,entries};
 }
 window.MedimateReport={build,records};
})();
