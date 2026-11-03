/* Cross-platform browser activation and desktop notification UI regression. */
const assert=require('node:assert/strict');
const fs=require('fs');
const vm=require('vm');
const app=fs.readFileSync('static/app.js','utf8');
const html=fs.readFileSync('static/index.html','utf8');
const translations=fs.readFileSync('static/translations.js','utf8');

const start=app.indexOf('  const localDate =');
const end=app.indexOf('  const notifyKey =',start);
assert.ok(start>=0 && end>start);
const context={Date,window:{}};
vm.createContext(context);
vm.runInContext(app.slice(start,end)+'\nthis.eligible=reminderDueAfterActivation;',context);
const medicine={times:['08:00','21:00'],reminderActivatedAt:{
  '08:00':'2026-10-27T20:00:00','21:00':'2026-10-27T20:00:00'
}};
assert.equal(context.eligible(medicine,'2026-10-27','08:00'),false);
assert.equal(context.eligible(medicine,'2026-10-27','21:00'),true);
assert.equal(context.eligible(medicine,'2026-10-28','08:00'),true);

assert.ok(app.includes('reminderDueAfterActivation(d.med,today,d.time)'));
assert.ok(app.includes('reminderActivatedAt:activationTimes(m)'));
assert.ok(app.includes('const reminderActivatedAt=Object.fromEntries(times.map('));
assert.ok(app.includes('Boolean(status.enabled&&status.helper_installed)'));
assert.ok(app.includes("'/api/reminders/test'"));
assert.ok(html.includes('id="test-desktop-notifications"'));
assert.ok(html.includes('20261103-reminder-activation'));
const tr={window:{}};
vm.runInNewContext(translations,tr);
for(const lang of ['en','ta','zh','ms'])for(const key of ['desktopTestButton','desktopTestRequesting','desktopTestRequested','desktopTestFailed']){
  assert.ok(tr.window.I18N[lang][key],lang+'/'+key);
}
console.log('PASS: 8 AM added at 8 PM is deferred, future times remain active, direct desktop test and translations');
