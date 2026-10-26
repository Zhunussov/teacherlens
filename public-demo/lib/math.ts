import source from './bank.json' with {type:'json'};
export type Topic='linear'|'distribution'|'negative';
export type Problem={id:string;topic:Topic;equation:string;answer:string;step:string};
export const bank=source as Problem[];
export const topics:Topic[]=['linear','distribution','negative'];
type Q={n:bigint;d:bigint};
type Linear={a:Q;b:Q};
const abs=(v:bigint)=>v<0n?-v:v;
function q(n:bigint,d=1n):Q{
 if(!d)throw Error('division');
 if(d<0n){n=-n;d=-d;}
 let a=abs(n),b=d;while(b){[a,b]=[b,a%b];}
 n/=a||1n;d/=a||1n;
 if(n.toString().length>100||d.toString().length>100)throw Error('complex');
 return {n,d};
}
const add=(x:Q,y:Q)=>q(x.n*y.d+y.n*x.d,x.d*y.d);
const neg=(x:Q)=>q(-x.n,x.d);
const mul=(x:Q,y:Q)=>q(x.n*y.n,x.d*y.d);
const div=(x:Q,y:Q)=>q(x.n*y.d,x.d*y.n);
const zero=()=>q(0n);
const equal=(x:Q,y:Q)=>x.n===y.n&&x.d===y.d;
const scalar=(b:Q):Linear=>({a:zero(),b});
function parse(input:string):Linear{
 let s=input.trim().replaceAll('−','-').replaceAll('×','*').replaceAll('÷','/').replaceAll(',','.');
 if(!s||s.length>80||!/^[0-9x.\s+*/()\-]+$/.test(s))throw Error('notation');
 s=s.replace(/(\d|\))\s*(?=x|\()/g,'$1*');
 const tokens=s.match(/(?:\d+(?:\.\d*)?|\.\d+)|x|[+*/()\-]/g)||[];
 if(tokens.join('')!==s.replace(/\s/g,'')||tokens.length>50)throw Error('notation');
 let i=0,depth=0;
 function factor():Linear{
  if(++depth>12)throw Error('complex');
  const token=tokens[i++];let value:Linear;
  if(token==='+'||token==='-'){value=factor();if(token==='-')value={a:neg(value.a),b:neg(value.b)};}
  else if(token==='('){value=sum();if(tokens[i++]!==')')throw Error('notation');}
  else if(token==='x')value={a:q(1n),b:zero()};
  else if(token&&/^(?:\d+(?:\.\d*)?|\.\d+)$/.test(token)){
   const [whole,frac='']=token.split('.');const number=q(BigInt((whole||'0')+frac),10n**BigInt(frac.length));
   if(abs(number.n)>10000n*number.d)throw Error('number');value=scalar(number);
  }else throw Error('notation');
  depth--;return value;
 }
 function product():Linear{
  let x=factor();
  while(tokens[i]==='*'||tokens[i]==='/'){
   const op=tokens[i++],y=factor();
   if(op==='/'){if(y.a.n||!y.b.n)throw Error('division');x={a:div(x.a,y.b),b:div(x.b,y.b)};}
   else {if(x.a.n&&y.a.n)throw Error('nonlinear');x={a:add(mul(x.a,y.b),mul(y.a,x.b)),b:mul(x.b,y.b)};}
  }return x;
 }
 function sum():Linear{
  let x=product();while(tokens[i]==='+'||tokens[i]==='-'){
   const op=tokens[i++],y=product();x={a:add(x.a,op==='+'?y.a:neg(y.a)),b:add(x.b,op==='+'?y.b:neg(y.b))};
  }return x;
 }
 const value=sum();if(i!==tokens.length)throw Error('notation');return value;
}
export function solution(text:string):Q{
 if(text.length>165||text.split('=').length!==2)throw Error('equation');
 const [l,r]=text.split('=').map(parse),a=add(l.a,neg(r.a));
 if(!a.n)throw Error('unique');return div(add(r.b,neg(l.b)),a);
}
export function value(text:string):Q{
 if(/^x\s*=/.test(text.trim()))return solution(text);
 const v=parse(text);if(v.a.n)throw Error('number');return v.b;
}
export type Verdict={correct:boolean;step:'absent'|'equivalent'|'wrong'|'unreadable'};
export function assess(problem:Problem,answer:string,step=''):Verdict{
 const correct=equal(value(answer),solution(problem.equation));
 let checked:Verdict['step']='absent';
 if(step.trim()){try{checked=equal(solution(step),solution(problem.equation))?'equivalent':'wrong';}catch{checked='unreadable';}}
 return {correct,step:checked};
}
export function form(kind:'diagnostic'|'retest'){return topics.flatMap(t=>(kind==='diagnostic'?[1,2]:[5,6]).map(n=>bank.find(p=>p.id===`${t}-${n}`)!));}
export function show(text:string){return text.replaceAll('*',' × ');}
