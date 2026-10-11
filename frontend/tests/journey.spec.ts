import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('diagnostic → feedback → conversation → editable plan → practice → retest → reflection',async({page})=>{
  const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('button',{name:'Find my starting point'})).toBeVisible();
  await page.screenshot({path:'../outputs/student-dashboard-desktop.png',fullPage:true});
  await page.getByRole('button',{name:'Find my starting point'}).click();
  await page.getByRole('button',{name:'Start diagnostic',exact:true}).click();
  for(let i=0;i<6;i++){
    await page.getByLabel('Your answer for x').fill('0');
    await page.getByRole('button',{name:'Record answer',exact:true}).click();
    await expect(page.getByText('Verified mathematical error',{exact:true})).toBeVisible();
    await page.getByRole('button',{name:i===5?'See the summary':'Next problem',exact:true}).click();
  }
  await expect(page.getByText('0 of 6 answers satisfy their equations.',{exact:false})).toBeVisible();
  await page.getByRole('button',{name:'Explore strategies together'}).click();
  await page.getByLabel('Which area felt uncertain?').selectOption('signs');
  await page.getByLabel('What did you notice?').fill('Synthetic learner: I want to check each sign and try a checklist.');
  await page.getByRole('button',{name:'Explore my options'}).click();
  await expect(page.getByText('Guided demo response · no live AI',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Try this strategy'}).first().click();
  await page.getByLabel('My goal').fill('Write each operation and check by substitution.');
  await page.getByLabel('I have reviewed and approve this editable plan.').check();
  await page.getByRole('button',{name:'Save my plan'}).click();
  await expect(page.getByRole('heading',{name:'Put the plan into practice'})).toBeVisible();
  for(let i=0;i<6;i++){
    await page.getByLabel('Your answer for x').fill('0');
    await page.getByRole('button',{name:'Check practice answer',exact:true}).click();
    await page.getByRole('button',{name:'Next unattempted exercise',exact:true}).click();
  }
  await page.getByRole('button',{name:'Go to follow-up',exact:true}).click();
  await page.getByRole('button',{name:'Start follow-up',exact:true}).click();
  const answers=['9','4','6','5','7','-3'];
  for(let i=0;i<6;i++){
    await page.getByLabel('Your answer for x').fill(answers[i]);
    await page.getByRole('button',{name:'Record answer',exact:true}).click();
    await page.getByRole('button',{name:i===5?'See the summary':'Next problem',exact:true}).click();
  }
  await page.getByRole('button',{name:'Compare & reflect',exact:true}).click();
  await expect(page.getByText('After: 2 / 2',{exact:true})).toHaveCount(3);
  await page.getByLabel('My reflection').fill('Synthetic reflection: I would like a slower sign checklist next.');
  await page.getByLabel('My next choice').selectOption('revise');
  await page.getByRole('button',{name:'Save reflection'}).click();
  await page.getByRole('button',{name:'Edit plan',exact:true}).click();
  await page.getByLabel('Minutes per session').fill('5');
  await page.getByLabel('I have reviewed and approve this editable plan.').check();
  await page.getByRole('button',{name:'Save my plan'}).click();
  await expect(page.getByText('Revision 2',{exact:true})).toBeVisible();
  await page.reload();
  await page.getByRole('navigation',{name:'Learning sections',exact:true}).getByRole('button',{name:'Progress & reflection'}).click();
  await expect(page.getByText('Synthetic reflection: I would like a slower sign checklist next.')).toBeVisible();
  await page.getByRole('button',{name:'Delete & restart demo'}).click();
  await page.getByRole('button',{name:'Confirm: delete this demo session'}).click();
  await expect(page.getByText('Not started',{exact:true})).toBeVisible();
  expect(errors).toEqual([]);
});

test('mobile navigation and layout stay usable',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'Find your way forward.'})).toBeVisible();
  await expect(page.getByRole('button',{name:'Find my starting point'})).toBeVisible();
  await page.screenshot({path:'../outputs/student-dashboard-mobile.png',fullPage:true});
  await page.getByRole('navigation',{name:'Mobile learning sections'}).getByRole('button',{name:'Studio',exact:true}).click();
  await expect(page.getByRole('heading',{name:'First, something real to work with'})).toBeVisible();
  await expect(page.getByRole('button',{name:'Take the diagnostic'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});

test('dashboard and diagnostic have no detected WCAG A/AA violations',async({page})=>{
  await page.goto('/');
  await expect(page.getByRole('button',{name:'Find my starting point'})).toBeVisible();
  expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
  await page.getByRole('button',{name:'Find my starting point'}).click();
  await page.getByRole('button',{name:'Start diagnostic',exact:true}).click();
  await expect(page.getByLabel('Your answer for x')).toBeVisible();
  expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
});

test('gateway enforces origin, hides session capability and preserves work on outage',async({page,request})=>{
  const blocked=await request.post('/api/session',{data:{}});
  expect(blocked.status()).toBe(403);
  await page.goto('/');
  await expect(page.getByRole('button',{name:'Find my starting point'})).toBeVisible();
  const cookie=(await page.context().cookies()).find(c=>c.name==='teacherlens_demo');
  expect(cookie?.httpOnly).toBeTruthy();expect(cookie?.sameSite).toBe('Strict');
  expect(await page.evaluate(()=>document.cookie)).not.toContain('teacherlens_demo');
  await page.route('**/api/assessment/start',route=>route.fulfill({status:503,json:{detail:'Synthetic test outage. Your saved work remains.'}}));
  await page.getByRole('button',{name:'Find my starting point'}).click();
  await page.getByRole('button',{name:'Start diagnostic',exact:true}).click();
  await expect(page.getByRole('alert').filter({hasText:'Synthetic test outage'})).toContainText('Synthetic test outage');
  await page.unroute('**/api/assessment/start');
  await page.getByRole('button',{name:'Start diagnostic',exact:true}).click();
  await expect(page.getByLabel('Your answer for x')).toBeVisible();
});

test('Studio checks the described transformation, remembers a correction and requires plan approval',async({page})=>{
  await page.goto('/');
  await expect(page.getByRole('button',{name:'Find my starting point'})).toBeVisible();
  // Synthetic recorded evidence via the same browser gateway, then exercise the UI.
  await page.evaluate(async()=>{
    const post=async(path:string,body:unknown)=>{
      const r=await fetch(`/api/${path}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      if(!r.ok)throw new Error(`Synthetic setup failed: ${r.status}`);
      return r.json();
    };
    const state=await post('assessment/start',{kind:'diagnostic'}),a=state.assessments[0];
    for(const id of a.problem_ids)await post(`assessment/${a.id}/answer`,{problem_id:id,answer:'0'});
  });
  await page.reload();
  await page.getByRole('navigation',{name:'Learning sections',exact:true}).getByRole('button',{name:'Strategy Studio'}).click();
  await page.getByLabel('What did you notice?').fill('Equation was x+5=12, so I moved +5 to the right and got x=17, but it was wrong.');
  await page.getByRole('button',{name:'Explore my options'}).click();
  await expect(page.getByText('The entered step x=17 does not preserve',{exact:false})).toBeVisible();
  await expect(page.getByText('To undo adding 5, subtract 5 on both sides.',{exact:false})).toBeVisible();
  const first=page.locator('.bubble.partner').last();
  await expect(first).not.toContainText('0/2');
  await expect(first).not.toContainText('x=7');
  await page.getByLabel('What did you notice?').fill('x+5-5=12-5');
  await page.getByRole('button',{name:'Explore my options'}).click();
  await expect(page.getByText('The entered step x+5-5=12-5 preserves',{exact:false})).toBeVisible();
  await expect(page.getByText('That entered change checks out.',{exact:false})).toBeVisible();
  expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
  await page.screenshot({path:'../outputs/studio-context.png',fullPage:true});
  await page.getByRole('button',{name:'Try this strategy'}).first().click();
  await expect(page.getByRole('button',{name:'Save my plan'})).toBeDisabled();
  await page.getByLabel('Observable success criteria').fill('Verify an equivalent step on two fresh equations.');
  await page.getByLabel('Current uncertainty').fill('I want to test whether writing both sides helps.');
  expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
  await page.getByLabel('I have reviewed and approve this editable plan.').check();
  await page.getByRole('button',{name:'Save my plan'}).click();
  await expect(page.getByText('Verify an equivalent step on two fresh equations.',{exact:false})).toBeVisible();
});
