import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('same per-topic scores, different verified errors, different recommendations on mobile',async({browser,baseURL})=>{
 const recommendations:string[]=[];
 for(const scenario of [
  {index:0,step:'x = 12 + 5',message:'Subtract 5 from both sides',operation:'x + 5 - 5 = 12 - 5',practice:'x + 8 = 13',method:'balance'},
  {index:2,step:'2*x + 3 = 14',message:'only x was multiplied by 2',operation:'2 × x + 2 × 3 = 14',practice:'4 × (x + 2) = 28',method:'expand'}
 ]){
  const context=await browser.newContext({baseURL,viewport:{width:390,height:844}});const page=await context.newPage();
  await page.goto('/');await page.getByLabel('Язык / Language').selectOption('en');await page.getByRole('button',{name:'Find my starting point'}).click();
  for(let i=0;i<6;i++){
   await page.getByLabel('Your value for x',{exact:true}).fill('17');
   if(i===scenario.index)await page.getByLabel('One intermediate equation (optional)').fill(scenario.step);
   await page.getByRole('button',{name:'Check my answer',exact:true}).click();
   if(i===scenario.index){
    await expect(page.getByText(scenario.message,{exact:false})).toBeVisible();await expect(page.getByText(scenario.operation,{exact:true})).toBeVisible();
    const rehearsal=page.locator('details').filter({has:page.getByText(`Try a similar problem: ${scenario.practice}`,{exact:true})});
    await rehearsal.locator('summary').click();await rehearsal.getByLabel('Your value for x',{exact:true}).fill('5');
    await rehearsal.getByRole('button',{name:'Check my answer',exact:true}).click();await expect(rehearsal.getByText('This value satisfies the original equation.',{exact:true})).toBeVisible();
   }
   await page.getByRole('button',{name:i===5?'Understand my results':'Next problem',exact:true}).click();
  }
  await expect(page.locator('.evidence-list strong')).toHaveText(['0 / 2','0 / 2','0 / 2']);
  await page.getByRole('button',{name:'Choose a strategy',exact:true}).click();
  await expect(page.getByLabel('How would you like to try?')).toHaveValue(scenario.method);
  const evidence=page.getByTestId('plan-evidence');await expect(evidence.getByText(scenario.message,{exact:false})).toBeVisible();
  await expect(evidence.getByRole('heading',{name:'Your selection',exact:true})).toBeVisible();await expect(evidence.getByText('I’m not sure yet',{exact:true})).toBeVisible();
  recommendations.push(await page.getByRole('textbox',{name:'My goal',exact:true}).inputValue());
  await page.getByRole('textbox',{name:'My goal',exact:true}).fill('Write each operation clearly and check it.');await page.getByLabel('I have reviewed and approve this plan.').check();
  expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
  await page.screenshot({path:`../outputs/actionable-${scenario.method}-mobile.png`,fullPage:true});
  await page.getByRole('button',{name:'Save and try my plan'}).click();await expect(page.getByText(scenario.practice,{exact:true})).toBeVisible();
  await page.reload();await page.getByText('My plan',{exact:true}).click();await expect(page.getByText('Write each operation clearly and check it.',{exact:true})).toBeVisible();
  await context.close();
 }
 expect(recommendations[0]).not.toEqual(recommendations[1]);
});

test('answer alone has no specific explanation; adding a step replaces the attempt',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.goto('/');await page.getByRole('button',{name:'Найти отправную точку'}).click();
 await page.getByLabel('Твоё значение x',{exact:true}).fill('17');await page.getByRole('button',{name:'Проверить ответ',exact:true}).click();
 await expect(page.getByText('Неверный ответ сам по себе не объясняет, почему возникла ошибка.',{exact:true})).toBeVisible();
 await expect(page.getByText('В шаге x = 12 + 5',{exact:false})).toHaveCount(0);await expect(page.getByText('Попробовать похожее задание',{exact:false})).toHaveCount(0);
 await page.getByRole('button',{name:'Добавить один шаг',exact:true}).click();await expect(page.getByLabel('Твоё значение x',{exact:true})).toHaveValue('17');
 await page.getByLabel('Промежуточное уравнение (необязательно)').fill('x = 12 + 5');await page.getByRole('button',{name:'Проверить ответ',exact:true}).click();
 await expect(page.getByText('Чтобы убрать +5, вычти 5 из обеих частей.',{exact:false})).toBeVisible();
 expect(await page.evaluate(()=>JSON.parse(localStorage.getItem('teacherlens-public-v1')!).diagnostic.length)).toBe(1);
 await page.getByLabel('Язык / Language').selectOption('en');await expect(page.getByText('Subtract 5 from both sides',{exact:false})).toBeVisible();
 await page.screenshot({path:'../outputs/actionable-feedback-mobile.png',fullPage:true});
 await page.getByRole('button',{name:'Next problem',exact:true}).click();await expect(page.getByText('3 × x = 18',{exact:true})).toBeVisible();
});
