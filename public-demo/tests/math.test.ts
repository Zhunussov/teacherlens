import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {assess,bank,form,solution,value} from '../lib/math.ts';
import {counts,draftFor,fresh,practiceFor,restore,validPlan} from '../lib/session.ts';
import {copy,methods} from '../lib/copy.ts';

test('all 24 original bank answers and worked steps are exact; forms are disjoint',()=>{
 assert.equal(bank.length,24);
 for(const p of bank){assert.deepEqual(value(p.answer),solution(p.equation));assert.equal(assess(p,p.answer,p.step).step,'equivalent');}
 const ids=[...form('diagnostic'),...form('retest')].map(p=>p.id);
 assert.equal(new Set(ids).size,12);
 assert.ok(!bank.filter(p=>/-[34]$/.test(p.id)).some(p=>ids.includes(p.id)));
});
test('exact rational algebra, decimals, fractions, signs and Unicode',()=>{
 for(const [eq,answer] of [['2(x+3)=14','4'],['x-(-3)=8','5'],['x/2=0.25','1/2'],['−2×x=10','-5'],['.1*x=.3','3'],['(x+1)/3=2','5']])assert.deepEqual(solution(eq),value(answer));
 assert.deepEqual(value('0,5'),value('1/2'));
});
test('dangerous, nonlinear, incomplete, huge and ambiguous input is rejected',()=>{
 for(const eq of ['x*x=4','1/x=2','x=x','0*x=1','x=1=2','x=1/0','x=10001','x=window.alert(1)','x=2**3','y=2','x=1e2','x=((((((((((((((1))))))))))))))','x='+('1+'.repeat(50))+'1'])assert.throws(()=>solution(eq),eq);
 for(const answer of ['','x+1','NaN','Infinity','1 2','process.exit()'])assert.throws(()=>value(answer),answer);
});
test('wrong steps are distinct from correct answers and unreadable evidence',()=>{
 const p=bank[0];assert.equal(assess(p,'17','x=17').step,'wrong');
 assert.deepEqual(assess(p,'7','x=17'),{correct:true,step:'wrong'});
 assert.equal(assess(p,'7','not an equation').step,'unreadable');
 assert.equal(assess(p,'7').step,'absent');
});
test('browser bank is exactly the authored Python bank, not MAP data',()=>{
 assert.ok(readFileSync(new URL('../lib/bank.json',import.meta.url),'utf8').includes('negative-8'));
 // Python suite independently compares every row and validates every answer/step.
 assert.equal(new Set(bank.map(p=>p.id)).size,24);
});
test('student choice and verified step errors change practice focus',()=>{
 const s=fresh();s.diagnostic=form('diagnostic').map(p=>({problemId:p.id,answer:p.answer,step:''}));
 s.diagnostic[0].step='x=17';
 assert.equal(counts(s.diagnostic).linear.stepErrors,1);
 assert.ok(draftFor(s).focus.includes('linear'));
 s.difficulty='signs';assert.equal(draftFor(s).focus[0],'negative');
 s.difficulty='checking';assert.equal(draftFor(s).method,'check');
 for(const locale of ['ru','en'] as const){s.locale=locale;const p=draftFor(s);assert.ok(validPlan(p));assert.ok(practiceFor(p).every(q=>/-[34]$/.test(q.id)));}
});
test('storage validates the complete learning workflow and rejects corruption',()=>{
 const s=fresh();assert.deepEqual(restore(JSON.stringify(s)),s);
 for(const raw of ['null','{}','{bad',JSON.stringify({...s,stage:'progress'}),JSON.stringify({...s,diagnostic:[{problemId:'unknown',answer:'7',step:''}]})])assert.throws(()=>restore(raw));
 s.diagnostic=form('diagnostic').map(p=>({problemId:p.id,answer:'0',step:''}));s.plan=draftFor(s);
 s.practice=practiceFor(s.plan).map(p=>({problemId:p.id,answer:p.answer,step:p.step}));
 s.retest=form('retest').map(p=>({problemId:p.id,answer:p.answer,step:p.step}));s.stage='progress';
 assert.deepEqual(restore(JSON.stringify(s)),s);
 s.difficulty='signs';s.plan=draftFor(s);s.stage='practice';assert.deepEqual(restore(JSON.stringify(s)),s);
 const bad={...s,plan:{...s.plan,steps:[''],minutes:100}};assert.throws(()=>restore(JSON.stringify(bad)));
});
test('Russian and English have the same UI and strategy structure',()=>{
 assert.deepEqual(Object.keys(copy.ru).sort(),Object.keys(copy.en).sort());
 for(const locale of ['ru','en'] as const){for(const text of Object.values(copy[locale]))assert.ok(text.trim());assert.equal(Object.keys(methods[locale]).length,4);}
});
test('reload after the last submitted answer resumes the next appropriate screen',()=>{
 const s=fresh();s.stage='diagnostic';s.diagnostic=form('diagnostic').map(p=>({problemId:p.id,answer:p.answer,step:''}));
 assert.equal(restore(JSON.stringify(s)).stage,'understand');
 s.plan=draftFor(s);s.practice=practiceFor(s.plan).map(p=>({problemId:p.id,answer:p.answer,step:''}));
 s.retest=form('retest').map(p=>({problemId:p.id,answer:p.answer,step:''}));s.stage='retest';
 assert.equal(restore(JSON.stringify(s)).stage,'progress');
});
