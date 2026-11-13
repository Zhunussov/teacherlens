import {assess,bank,type Problem} from './math.ts';
import type {Locale} from './copy.ts';

// Deliberately narrow: matching a written transformation is not inferring a cause.
const compact=(text:string)=>text.replaceAll('−','-').replaceAll('×','*').replace(/\s/g,'').replace(/(\d)x/g,'$1*x');
const rules=[
 {id:'inverse-addition',problemId:'linear-1',original:'x + 5 = 12',wrong:'x = 12 + 5',operation:'x + 5 - 5 = 12 - 5',practiceId:'linear-3',freshId:'linear-5',method:'balance',
  en:{explanation:'In x = 12 + 5, +5 disappears on the left but is added on the right. Subtract 5 from both sides to undo +5.',goal:'Undo addition by subtracting the same amount from both sides.',steps:['Write the subtraction on both sides.','Simplify each side separately.','Substitute the result into the original equation.'],check:'On x + 4 = 13, write the same subtraction on both sides, then check by substitution.'},
  ru:{explanation:'В шаге x = 12 + 5 слагаемое +5 исчезло слева, но прибавилось справа. Чтобы убрать +5, вычти 5 из обеих частей.',goal:'Убирать слагаемое, вычитая одно и то же число из обеих частей.',steps:['Записать вычитание с обеих сторон.','Упростить каждую часть отдельно.','Подставить результат в исходное уравнение.'],check:'В x + 4 = 13 запиши одинаковое вычитание с обеих сторон и проверь ответ подстановкой.'}},
 {id:'partial-distribution',problemId:'distribution-1',original:'2*(x + 3) = 14',wrong:'2*x + 3 = 14',operation:'2*x + 2*3 = 14',practiceId:'distribution-3',freshId:'distribution-5',method:'expand',
  en:{explanation:'In 2x + 3 = 14, only x was multiplied by 2. The 3 inside the parentheses must also be multiplied by 2.',goal:'Multiply every term inside parentheses, including the constant.',steps:['Connect the multiplier to each term inside parentheses.','Write both products before simplifying.','Substitute the result into the original equation.'],check:'On 2(x + 4) = 20, write both products, then check the result by substitution.'},
  ru:{explanation:'В шаге 2x + 3 = 14 на 2 умножен только x. Число 3 внутри скобок тоже нужно умножить на 2.',goal:'Умножать каждый член в скобках, включая число.',steps:['Соединить множитель с каждым членом в скобках.','Записать оба произведения до упрощения.','Подставить результат в исходное уравнение.'],check:'В 2(x + 4) = 20 запиши оба произведения и проверь результат подстановкой.'}}
] as const;

export function stepFeedback(problem:Problem,step:string,locale:Locale){
 const rule=rules.find(r=>r.problemId===problem.id&&r.original===problem.equation&&compact(r.wrong)===compact(step));
 if(!rule)return null;
 // Recheck both the mismatch and the proposed correction with exact arithmetic.
 if(assess(problem,problem.answer,step).step!=='wrong'||assess(problem,problem.answer,rule.operation).step!=='equivalent')return null;
 return {...rule,...rule[locale],topic:problem.topic,practice:bank.find(p=>p.id===rule.practiceId)!};
}
