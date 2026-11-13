'use client';
import {useState} from 'react';
import {assess,show,type Problem,type Verdict} from '../lib/math';
import {copy,type Locale} from '../lib/copy';

// Optional rehearsal stays outside diagnostic/retest records and score counts.
export function StepPractice({problem,locale}:{problem:Problem;locale:Locale}){
 const [answer,setAnswer]=useState(''),[step,setStep]=useState(''),[result,setResult]=useState<Verdict|null>(null),[invalid,setInvalid]=useState(false);
 const c=copy[locale];
 return <details><summary>{c.similar}: {show(problem.equation)}</summary><form onSubmit={e=>{e.preventDefault();try{setResult(assess(problem,answer,step));setInvalid(false);}catch{setResult(null);setInvalid(true);}}}>
  <p>{c.rehearsal}</p><label>{c.answer}<input required maxLength={80} value={answer} onChange={e=>{setAnswer(e.target.value);setResult(null);}}/></label>
  <label>{c.step}<input maxLength={165} value={step} onChange={e=>{setStep(e.target.value);setResult(null);}}/></label>
  <button type="submit" className="text-button">{c.check}</button>
  {invalid&&<p role="alert">{c.invalid}</p>}{result&&<div role="status"><p>{result.correct?c.correct:c.incorrect}</p><p>{result.step==='equivalent'?c.stepGood:result.step==='wrong'?c.stepWrong:result.step==='unreadable'?c.stepUnreadable:c.stepAbsent}</p></div>}
 </form></details>;
}
