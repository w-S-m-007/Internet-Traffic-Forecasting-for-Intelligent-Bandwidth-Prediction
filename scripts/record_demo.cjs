// Optional browser QA/recording helper. npm install playwright; npx playwright install ffmpeg.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '..');
const output = path.join(root, 'deliverables', 'demo');
fs.mkdirSync(output, {recursive: true});
let browser;
(async () => {
  browser = await chromium.launch({channel:'msedge', headless:true});
  const context = await browser.newContext({viewport:{width:1440,height:1050},
    recordVideo:{dir:path.join(root,'tmp','demo_capture'),size:{width:1440,height:1050}}});
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const select = async (name, value) => {
    await page.getByRole('combobox', {name,exact:true}).click();
    await page.getByRole('option', {name:value,exact:true}).click();
    await page.waitForTimeout(1600);
  };
  const view = async value => {
    await page.getByTestId('stSidebar').getByText(value,{exact:true}).click();
    await page.waitForTimeout(1600);
  };
  await page.goto('http://127.0.0.1:8501/',{waitUntil:'domcontentloaded'});
  await page.getByText('21.148 Mbps',{exact:true}).waitFor({timeout:60000});
  await page.waitForTimeout(4000);
  await select('Model','Transformer');
  await page.getByText('20.746 Mbps',{exact:true}).waitFor();
  await page.waitForTimeout(3500);
  await select('Horizon','30 minutes');
  await select('Model','GRU');
  await page.getByText('21.495 Mbps',{exact:true}).waitFor();
  await page.waitForTimeout(3500);
  await select('Horizon','60 minutes');
  await page.getByText('24.506 Mbps',{exact:true}).waitFor();
  await page.waitForTimeout(3500);
  await view('Forecasts');
  const replay = page.getByTestId('stSlider').filter({hasText:'Replay position'}).getByRole('slider');
  await replay.focus();
  for (let i=0;i<12;i++) await replay.press('ArrowRight');
  await page.waitForTimeout(3500);
  await view('Comparison');
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button',{name:'Download comparison CSV',exact:true}).click();
  const download = await downloadPromise;
  await download.saveAs(path.join(root,'tmp','demo_comparison.csv'));
  await page.waitForTimeout(3000);
  await select('Horizon','10 minutes');
  await view('Allocation');
  await select('Allocation model','GRU');
  await page.getByText(/1% validation shortfall target unmet/).waitFor();
  await page.waitForTimeout(3500);
  const margin = page.getByTestId('stSlider').filter({hasText:'Safety margin'}).getByRole('slider');
  await margin.focus(); await margin.press('Home');
  await page.waitForTimeout(3500);
  await margin.focus(); await margin.press('End');
  await page.waitForTimeout(3500);
  await select('Allocation model','Transformer');
  await page.waitForTimeout(3500);
  await page.screenshot({path:path.join(output,'allocation.png'),fullPage:true,animations:'disabled'});
  await select('Allocation model','LSTM');
  await select('Evaluation split','Validation');
  await page.waitForTimeout(3500);
  await select('Evaluation split','Test');
  await view('Overview');
  await page.waitForTimeout(3500);
  await page.screenshot({path:path.join(output,'overview.png'),fullPage:true,animations:'disabled'});
  if(errors.length) throw new Error(errors.join('; '));
  const video = page.video();
  await context.close();
  await video.saveAs(path.join(output,'dashboard_demo.webm'));
  await browser.close();
  fs.writeFileSync(path.join(output,'demo_verification.json'),JSON.stringify({
    checked_at_utc:new Date().toISOString(),browser_errors:errors,download_verified:fs.statSync(path.join(root,'tmp','demo_comparison.csv')).size>0,
    covered:['10/30/60-minute forecasts','model selection','historical replay','comparison CSV download','GRU/Transformer/LSTM allocation','5% and20% equal margins','validation/test selection'],
    audio:'Silent screen recording; speaking guide in docs/presentation/demo_script.md'
  },null,2));
  console.log('Demo recording and browser checks complete: '+output);
})().catch(async error=>{console.error(error);if(browser)await browser.close();process.exit(1);});
