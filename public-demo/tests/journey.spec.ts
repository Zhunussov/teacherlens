import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('complete English journey with no API, wrong answer, personalized editable strategy, fresh retest and reset',async({page})=>{
 const errors:string[]=[],requests:string[]=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));
 await page.goto('/');await page.getByLabel('Язык / Language').selectOption('en');
 await expect(page.getByRole('heading',{name:'Don’t just solve it. Find your way to learn.'})).toBeVisible();
 await page.getByRole('button',{name:'Find my starting point'}).click();
 await page.getByLabel('Your value for x',{exact:true}).fill('garbage');await page.getByRole('button',{name:'Check my answer'}).click();
 await expect(page.locator('main [role="alert"]')).toContainText('We could not read');
 for(let i=0;i<6;i++){
  await page.getByLabel('Your value for x',{exact:true}).fill('0');
  if(i===0)await page.getByLabel('One intermediate equation (optional)').fill('x=17');
  await page.getByRole('button',{name:'Check my answer'}).click();
  await expect(page.getByText('This value does not satisfy the original equation.',{exact:true})).toBeVisible();
  if(i===0)await expect(page.getByText('Your entered step changes the solution:',{exact:false})).toBeVisible();
  if(i===5)await page.reload();else await page.getByRole('button',{name:'Next problem',exact:true}).click();
 }
 await expect(page.getByRole('heading',{name:'What do your answers show?'})).toBeVisible();
 await page.getByLabel('Keeping track of signs',{exact:true}).check();
 await page.getByRole('button',{name:'Choose a strategy'}).click();
 await expect(page.locator('main p').filter({hasText:'Practice focus:'})).toContainText('Negative number operations');
 await page.getByLabel('How would you like to try?').selectOption('check');
 await page.getByRole('textbox',{name:'My goal',exact:true}).fill('Check my signs by substituting each result.');
 await expect(page.getByRole('button',{name:'Save and try my plan'})).toBeDisabled();
 await page.getByLabel('I have reviewed and approve this plan.').check();
 expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
 await page.getByRole('button',{name:'Save and try my plan'}).click();
 for(let i=0;i<4;i++){
  await page.getByLabel('Your value for x',{exact:true}).fill('0');await page.getByRole('button',{name:'Check my answer'}).click();
  await page.getByRole('button',{name:'Continue practice',exact:true}).click();
 }
 await page.getByRole('button',{name:'Try a fresh check',exact:true}).click();
 for(const [i,answer] of ['9','4','6','5','7','-3'].entries()){
  await page.getByLabel('Your value for x',{exact:true}).fill(answer);await page.getByRole('button',{name:'Check my answer'}).click();
  await expect(page.getByText('This value satisfies the original equation.',{exact:true})).toBeVisible();
  if(i===5)await page.reload();else await page.getByRole('button',{name:'Next problem',exact:true}).click();
 }
 await expect(page.getByRole('heading',{name:'What changed?'})).toBeVisible();
 await expect(page.locator('meter[value="2"]')).toHaveCount(3);
 await page.getByLabel('What helped, and what would you change?').fill('Fictional reflection: substitution helped me notice signs.');
 await page.getByRole('button',{name:'Save reflection',exact:true}).click();await expect(page.getByText('Reflection saved on this device.')).toBeVisible();
 await page.reload();await expect(page.getByRole('heading',{name:'What changed?'})).toBeVisible();
 await expect(page.getByLabel('What helped, and what would you change?')).toHaveValue('Fictional reflection: substitution helped me notice signs.');
 expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
 await page.screenshot({path:'../outputs/public-progress-en.png',fullPage:true});
 await page.getByRole('button',{name:'Revise my strategy'}).click();await page.getByLabel('Minutes per session',{exact:true}).fill('5');
 await page.getByLabel('I have reviewed and approve this plan.').check();await page.getByRole('button',{name:'Save and try my plan'}).click();
 await page.reload();await expect(page.getByRole('heading',{name:'Your practice attempts are recorded.'})).toBeVisible();
 await page.getByRole('button',{name:'Reset progress',exact:true}).click();await page.getByRole('button',{name:'Yes, start again'}).click();
 await expect(page.getByRole('heading',{name:'Don’t just solve it. Find your way to learn.'})).toBeVisible();
 await page.reload();await expect(page.getByRole('button',{name:'Find my starting point'})).toBeVisible();
 expect(errors).toEqual([]);expect(requests.filter(url=>/\/api\/|:8000|huggingface|ollama/.test(url))).toEqual([]);
});

test('Russian journey, mobile layout, locale switching and saved diagnostic',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.goto('/');
 await expect(page.getByRole('heading',{name:'Не просто решить. Понять, как учиться.'})).toBeVisible();
 expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
 await page.screenshot({path:'../outputs/public-welcome-ru-mobile.png',fullPage:true});
 await page.getByRole('button',{name:'Найти отправную точку'}).click();
 await page.getByLabel('Твоё значение x',{exact:true}).fill('7');await page.getByRole('button',{name:'Проверить ответ',exact:true}).click();
 await expect(page.getByText('Это значение подходит к исходному уравнению.',{exact:true})).toBeVisible();
 await page.reload();await expect(page.getByLabel('Твоё значение x',{exact:true})).toBeVisible();
 for(let i=1;i<6;i++){
  await page.getByLabel('Твоё значение x',{exact:true}).fill('0');await page.getByRole('button',{name:'Проверить ответ',exact:true}).click();
  await page.getByRole('button',{name:i===5?'Разобраться в результате':'Следующее задание',exact:true}).click();
 }
 await page.getByLabel('Раскрыть скобки',{exact:true}).check();await page.getByRole('button',{name:'Выбрать стратегию',exact:true}).click();
 await expect(page.getByLabel('Как попробовать?')).toHaveValue('expand');await expect(page.getByLabel('Мои действия · по одному на строке')).toHaveValue(/Соединить множитель/);
 await page.getByLabel('Язык / Language').selectOption('en');await expect(page.getByLabel('How would you like to try?')).toHaveValue('expand');
 await expect(page.getByLabel('My actions · one per line')).toHaveValue(/Connect the multiplier/);
 await page.getByLabel('Language / Язык').selectOption('ru');await expect(page.getByLabel('Мои действия · по одному на строке')).toHaveValue(/Соединить множитель/);
 await page.getByLabel('Я просмотрел(а) и одобряю этот план.').check();await page.getByRole('button',{name:'Сохранить и попробовать',exact:true}).click();
 await expect(page.getByText('Раскрытие скобок · Задание 1 из 4',{exact:true})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
 expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
});

test('corrupt and blocked browser storage are transparent and never block use',async({page})=>{
 await page.addInitScript(()=>localStorage.setItem('teacherlens-public-v1','{"version":900}'));
 await page.goto('/');await expect(page.getByText('Сохранённые данные не удалось проверить. Начат новый сеанс.')).toBeVisible();
 await page.getByRole('button',{name:'Найти отправную точку'}).click();await expect(page.getByLabel('Твоё значение x',{exact:true})).toBeVisible();
 await page.addInitScript(()=>{Storage.prototype.setItem=()=>{throw new DOMException('disabled','QuotaExceededError');};});
 await page.reload();await expect(page.getByText('Браузер не разрешил сохранение.',{exact:false})).toBeVisible();
});
