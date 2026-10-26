import {assess,bank,form,topics,type Topic} from './math.ts';
import {copy,methods,topicNames,type Locale,type Method} from './copy.ts';
export type Stage='welcome'|'diagnostic'|'understand'|'strategy'|'practice'|'retest'|'progress';
export type Attempt={problemId:string;answer:string;step:string};
export type Difficulty='unsure'|'operations'|'brackets'|'signs'|'checking';
export type Plan={method:Method;focus:Topic[];goal:string;steps:string[];minutes:number;days:number;criteria:string;revision:number};
export type Session={version:1;locale:Locale;stage:Stage;diagnostic:Attempt[];practice:Attempt[];retest:Attempt[];difficulty:Difficulty;plan:Plan|null;reflection:string};
export const storageKey='teacherlens-public-v1';
export const fresh=():Session=>({version:1,locale:'ru',stage:'welcome',diagnostic:[],practice:[],retest:[],difficulty:'unsure',plan:null,reflection:''});
export function counts(attempts:Attempt[]){return Object.fromEntries(topics.map(topic=>{const rows=attempts.filter(a=>bank.find(p=>p.id===a.problemId)?.topic===topic);const results=rows.map(a=>assess(bank.find(p=>p.id===a.problemId)!,a.answer,a.step));return [topic,{correct:results.filter(v=>v.correct).length,total:rows.length,stepErrors:results.filter(v=>v.step==='wrong').length}];})) as Record<Topic,{correct:number;total:number;stepErrors:number}>;}
export function focusFor(s:Session):Topic[]{
 const stats=counts(s.diagnostic),ranked=[...topics].sort((a,b)=>(stats[b].total-stats[b].correct+stats[b].stepErrors)-(stats[a].total-stats[a].correct+stats[a].stepErrors));
 const selected:Topic|undefined=s.difficulty==='operations'?'linear':s.difficulty==='brackets'?'distribution':s.difficulty==='signs'?'negative':undefined;
 const weak=ranked.filter(t=>stats[t].correct<stats[t].total||stats[t].stepErrors);
 return [...new Set([...(selected?[selected]:[]),...weak])].slice(0,2).length?[...new Set([...(selected?[selected]:[]),...weak])].slice(0,2):[ranked[0]];
}
export function draftFor(s:Session,method?:Method):Plan{
 const focus=focusFor(s),key=method??(s.difficulty==='checking'?'check':focus[0]==='distribution'?'expand':focus[0]==='negative'?'signed':'balance');
 return {method:key,focus,goal:copy[s.locale].planGoal+focus.map(t=>topicNames[s.locale][t]).join(', '),steps:methods[s.locale][key].steps,minutes:10,days:3,criteria:copy[s.locale].planCriteria,revision:(s.plan?.revision??0)+1};
}
export function practiceFor(plan:Plan){return plan.focus.flatMap(t=>[3,4].map(n=>bank.find(p=>p.id===`${t}-${n}`)!));}
export function validPlan(p:Plan){return ['balance','expand','signed','check'].includes(p.method)&&Array.isArray(p.focus)&&p.focus.length>=1&&p.focus.length<=2&&new Set(p.focus).size===p.focus.length&&p.focus.every(t=>topics.includes(t))&&[p.goal,p.criteria].every(s=>typeof s==='string'&&s.trim().length>=5&&s.length<=200)&&Array.isArray(p.steps)&&p.steps.length>=1&&p.steps.length<=5&&p.steps.every(s=>typeof s==='string'&&s.trim().length>0&&s.length<=200)&&Number.isInteger(p.minutes)&&p.minutes>=5&&p.minutes<=20&&Number.isInteger(p.days)&&p.days>=1&&p.days<=5&&Number.isInteger(p.revision)&&p.revision>=1;}
export function restore(raw:string):Session{
 if(raw.length>100000)throw Error('storage');const s=JSON.parse(raw) as Session;
 if(s.version!==1||!['ru','en'].includes(s.locale)||!['welcome','diagnostic','understand','strategy','practice','retest','progress'].includes(s.stage)||!['unsure','operations','brackets','signs','checking'].includes(s.difficulty)||typeof s.reflection!=='string'||s.reflection.length>400)throw Error('storage');
 for(const kind of ['diagnostic','practice','retest'] as const){
  const records=s[kind];if(!Array.isArray(records)||records.length>(kind==='practice'?60:6))throw Error('storage');
  const allowed=kind==='practice'?bank.filter(p=>/-[34]$/.test(p.id)):form(kind);
  records.forEach((a,i)=>{
   if(!a||typeof a.answer!=='string'||a.answer.length>80||typeof a.step!=='string'||a.step.length>165)throw Error('storage');
   const p=allowed.find(p=>p.id===a.problemId);if(!p||(kind!=='practice'&&p.id!==allowed[i].id))throw Error('storage');assess(p,a.answer,a.step);
  });
 }
 if(s.plan!==null&&!validPlan(s.plan))throw Error('storage');
 if(['understand','strategy','practice','retest','progress'].includes(s.stage)&&s.diagnostic.length!==6)throw Error('storage');
 if((s.practice.length||s.retest.length||['practice','retest','progress'].includes(s.stage))&&!s.plan)throw Error('storage');
 if(s.stage==='retest'&&(!s.plan||!practiceFor(s.plan).every(p=>s.practice.some(a=>a.problemId===p.id))))throw Error('storage');
 if(s.stage==='progress'&&s.retest.length!==6)throw Error('storage');
 if(s.stage==='diagnostic'&&s.diagnostic.length===6)s.stage='understand';
 if(s.stage==='retest'&&s.retest.length===6)s.stage='progress';
 return s;
}
