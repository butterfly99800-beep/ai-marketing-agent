const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path');
const {safe}=require('./network-policy.cjs');

// Capture evidence, not a simulated product UI. No form submission or login.
(async()=>{
 const [url,out]=process.argv.slice(2);if(!await safe(url))throw Error('PUBLIC_URL_REQUIRED');
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:process.env.VIDEO_BROWSER_PATH||(process.platform==='win32'?'C:/Program Files/Google/Chrome/Application/chrome.exe':chromium.executablePath())});
 try{
 const page=await browser.newPage({viewport:{width:1920,height:1080},deviceScaleFactor:2});
 await page.route('**/*',async route=>{if(await safe(route.request().url()))await route.continue();else await route.abort()});
 page.setDefaultTimeout(7000);
 await page.goto(url,{waitUntil:'domcontentloaded',timeout:45000});await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(1200);
 const final=page.url();if(!await safe(final))throw Error('UNSAFE_REDIRECT');
 const design_tokens=await page.evaluate(()=>{
  const body=getComputedStyle(document.body),h=document.querySelector('h1');const colors=[...document.querySelectorAll('a,button,h1,h2')].map(e=>({text:(e.textContent||'').trim().slice(0,40),color:getComputedStyle(e).color,background:getComputedStyle(e).backgroundColor}));const a=[...document.querySelectorAll('a,button')].find(e=>{const v=getComputedStyle(e).backgroundColor.match(/\d+/g);return v&&v.length>=3&&Math.max(...v.slice(0,3).map(Number))-Math.min(...v.slice(0,3).map(Number))>35});
  return {sampled_colors:colors.slice(0,24),font_family:body.fontFamily,background:body.backgroundColor,foreground:body.color,accent:a?getComputedStyle(a).backgroundColor:'',heading:h?{size:getComputedStyle(h).fontSize,weight:getComputedStyle(h).fontWeight}:null};
 });
 const links=await page.locator('a[href]').evaluateAll(nodes=>nodes.map(n=>({url:n.href,label:n.innerText.slice(0,100)})));
 const candidates=[...new Map(links.map(l=>[l.url,l])).values()].filter(l=>{try{const u=new URL(l.url),root=new URL(final);return u.origin===root.origin&&u.href!==root.href&&!(u.pathname===root.pathname&&u.search===root.search)&&!/跳转到|skip to/i.test(l.label)&&!/(login|logout|sign|delete|checkout|contact|register|download|支付|登录|删除)/i.test(u.href+' '+l.label)&&! /\.(pdf|zip|mp4|png|jpg)(?:$|[?#])/i.test(u.pathname)}catch{return false}}).sort((a,b)=>Number(/功能|产品|演示|流程|features|products|showcase|module/i.test(b.url+' '+b.label))-Number(/功能|产品|演示|流程|features|products|showcase|module/i.test(a.url+' '+a.label))).slice(0,3);
 const result=[];
 const save=async(locator,label,kind)=>{
  if(result.length>=12)return;
  const file=`site${result.length}.png`,box=await locator.boundingBox();if(!box||box.width<240||box.height<140)return;
  const text=(await locator.innerText()).slice(0,3500);
  if(kind==='section'&&((text.length<120&&!await locator.locator('h1,h2,h3').count())||!text.trim()||result.some(p=>p.kind==='section'&&p.text===text)))return;
  if(kind==='page')await page.screenshot({path:path.join(out,file),timeout:15000});else await locator.screenshot({path:path.join(out,file),timeout:15000});
  const hash=require('node:crypto').createHash('sha256').update(fs.readFileSync(path.join(out,file))).digest('hex');if(result.some(r=>r.hash===hash)){fs.unlinkSync(path.join(out,file));return;}
  const cssW=kind==='page'?1920:box.width;const pageH=kind==='page'?1080:box.height*1920/cssW;const regions=await locator.locator('tr,article,h1,h2,h3').evaluateAll(nodes=>nodes.filter(e=>{const b=e.getBoundingClientRect();return b.width>200&&b.height>25}).slice(0,35).map(e=>{const b=e.getBoundingClientRect();return {tag:e.tagName,text:(e.innerText||'').slice(0,140),x:b.x,y:b.y,w:b.width,h:b.height}}));for(const r of regions){r.x=(r.x-(kind==='page'?0:box.x))*1920/cssW;r.y=(r.y-(kind==='page'?0:box.y))*1920/cssW;r.w*=1920/cssW;r.h*=1920/cssW;}
  result.push({pageH,regions,state:{selected_tab:kind==='tab'?label:null},hash,url:page.url(),title:await page.title(),label,kind,text,file,bbox:box,scroll_y:await page.evaluate(()=>scrollY),pixel_ratio:2});
 };
 for(const [i,l] of [{url:final,label:'首页'},...candidates].entries()){
  if(i){try{await page.goto(l.url,{waitUntil:'domcontentloaded',timeout:18000});await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(700);}catch{continue;}}
  if(!await safe(page.url()))throw Error('UNSAFE_REDIRECT');
  await page.screenshot({path:path.join(out,`page${i}-full.png`),fullPage:true,timeout:20000});
  // Fixed/sticky chrome otherwise burns into an element screenshot at the wrong page coordinate.
  await page.evaluate(()=>document.querySelectorAll('header,nav,[role=banner]').forEach(e=>{if(['fixed','sticky'].includes(getComputedStyle(e).position))e.style.visibility='hidden'}));
  await save(page.locator('body'),l.label,'page');
  const tabs=page.getByRole('tab');const tabCount=Math.min(await tabs.count(),6);if(i===0&&tabCount){for(let t=0;t<tabCount&&result.length<8;t++){try{const tab=tabs.nth(t),label=(await tab.innerText()).trim();await tab.click();await page.waitForTimeout(650);const panel=page.getByRole('tabpanel').filter({visible:true}).first();if(await panel.count())await save(panel,label,'tab');}catch{}}}
  // A viewport remains readable in the film; a tall full-page image does not.
  const scrollTarget=await page.evaluate(()=>{const nodes=[document.scrollingElement,...document.querySelectorAll('main,[role=main],div')].filter(Boolean);let best=null,score=0;for(const e of nodes){const r=e.getBoundingClientRect(),css=getComputedStyle(e);if(r.width<600||r.height<300||e.scrollHeight<=e.clientHeight+100)continue;if(e!==document.scrollingElement&&!/(auto|scroll)/.test(css.overflowY))continue;const v=r.width*Math.min(r.height,1080);if(v>score){score=v;best=e}}if(!best)return null;best.setAttribute('data-film-scroll','true');return {max:best.scrollHeight-best.clientHeight,step:best.clientHeight*.78};});
  if(scrollTarget){for(let j=1;j<=(i===0&&tabCount?0:1)&&result.length<12;j++){const y=Math.min(scrollTarget.max,Math.round(j*scrollTarget.step));await page.locator('[data-film-scroll=true]').evaluate((e,y)=>e.scrollTo({top:y,behavior:'instant'}),y);await page.waitForTimeout(450);const before=result.length;await save(page.locator('body'),l.label+' · 第'+(j+1)+'屏','page');if(result.length>before)result[result.length-1].scroll_y=y;if(y===scrollTarget.max)break;}await page.locator('[data-film-scroll=true]').evaluate(e=>{e.scrollTo({top:0,behavior:'instant'});e.removeAttribute('data-film-scroll')});}
  if(result.length>=12)break;
  const sections=page.locator('main section, [role=main] section, #web-main section, main article');
  const n=i===0?0:Math.min(await sections.count(),1);
  for(let j=0;j<n&&result.length<12;j++){
   const loc=sections.nth(j);const label=(await loc.locator('h1,h2,h3').first().textContent().catch(()=>''))||await loc.getAttribute('aria-label')||`内容区块${j+1}`;
   await save(loc,label,'section');
  }
 }
 fs.writeFileSync(path.join(out,'site.json'),JSON.stringify({pages:result,design_tokens,limitations:'公开页面及正文区块的2x截图与文字证据；未登录、未提交表单、未验证完整操作流程。'},null,2));
 console.log('WEBSITE_CAPTURE_OK');
 }finally{await browser.close();}
})().catch(()=>{console.error('WEBSITE_CAPTURE_FAILED');process.exit(1)});

