/* Test explicit Stop UI without launching a real server. */
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const app = fs.readFileSync('static/app.js', 'utf8');
const html = fs.readFileSync('static/index.html', 'utf8');
const translations = fs.readFileSync('static/translations.js', 'utf8');
const i18n = {window:{}};
vm.runInNewContext(translations, i18n);
const keys = ['stopAppTitle','stopAppDesc','stopAppButton','stopAppConfirm',
              'stopAppStopping','stopAppFailed','stopAppDoneTitle','stopAppDoneDesc'];
for (const language of ['en','ta','zh','ms']) {
  for (const key of keys) {
    assert.ok(i18n.window.I18N[language][key], language + ': missing ' + key);
  }
}
assert.ok(html.includes('id="stop-medimate"'));
assert.ok(html.includes('id="stop-medimate-status"'));
assert.ok(html.includes('data-i18n="stopAppTitle"'));
assert.ok(app.includes("'/api/app/stop'"));
assert.ok(app.includes('document.body.replaceChildren(screen)'));
assert.ok(!app.includes("addEventListener('beforeunload'"));

// Extract the actual stop function from the app and run it with test DOM/fetch.
const match = app.match(/  async function stopMedimate\(\)\{[\s\S]*?\n  \}/);
assert.ok(match, 'stopMedimate function is present');
async function exercise(approve, serverOk) {
  let requested = 0, shutdownScreen = null, confirms = 0, clearCount = 0;
  const button = {disabled:false};
  const status = {textContent:''};
  const context = {
    appStopping: false, macEnabled: true, macInstalled: true, macSyncTimer: null,
    dueInterval: 123,
    window: {confirm: () => {confirms++;return approve;}},
    t: key => key,
    $: id => ({'stop-medimate': button,'stop-medimate-status':status}[id]),
    clearTimeout: ()=>{}, clearInterval: () => {clearCount++;},
    fetch: async (url, config) => {
      requested++;
      assert.strictEqual(url, '/api/app/stop');
      assert.strictEqual(config.method, 'POST');
      assert.deepStrictEqual(JSON.parse(config.body),{confirm:true});
      return {ok:serverOk,json:async()=>({stopped:true,reminders_disabled:true})};
    },
    elt: (tag,cls,txt)=>({tag,cls,txt,children:[],append(...items){this.children.push(...items);}}),
    document: {body:{replaceChildren(screen){shutdownScreen=screen;}}}
  };
  vm.createContext(context);
  vm.runInContext(match[0] + '\nthis.stopMedimate = stopMedimate;',context);
  await context.stopMedimate();
  if (!approve) {
    assert.equal(confirms,1);
    assert.equal(requested,0);
    assert.equal(button.disabled,false);
    assert.equal(shutdownScreen,null);
  } else if (serverOk) {
    assert.equal(requested,1);
    assert.equal(clearCount,1);
    assert.ok(shutdownScreen);
    assert.equal(shutdownScreen.children[0].children[0].txt,'stopAppDoneTitle');
    assert.equal(context.macEnabled,false);
  } else {
    assert.equal(requested,1);
    assert.equal(button.disabled,false);
    assert.equal(status.textContent,'stopAppFailed');
    assert.equal(shutdownScreen,null);
  }
}
(async () => {
  await exercise(false,true);
  await exercise(true,false);
  await exercise(true,true);
  console.log('PASS: explicit Stop confirmation, backend request, success UI, error handling, and four translations');
})().catch(err=>{console.error(err);process.exitCode=1;});
