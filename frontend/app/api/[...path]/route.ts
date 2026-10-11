import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
const cookieName = 'teacherlens_demo';
const routes: Record<string, RegExp> = {
  GET: /^state$/,
  POST: /^(session|assessment\/start|assessment\/[a-f0-9]{24}\/answer|conversation|practice\/answer|reflection)$/,
  PUT: /^plan$/,
  DELETE: /^session$/,
};

async function handle(request: NextRequest, context: {params: Promise<{path: string[]}>}) {
  const path = (await context.params).path.join('/');
  if (!routes[request.method]?.test(path)) return NextResponse.json({detail:'Endpoint not available.'}, {status:404});
  const expectedOrigin=process.env.TEACHERLENS_FRONTEND_ORIGIN ?? 'http://127.0.0.1:3000';
  if (request.method !== 'GET' && request.headers.get('origin') !== expectedOrigin)
    return NextResponse.json({detail:'Use the same-origin TeacherLens interface.'}, {status:403});
  const secret = process.env.TEACHERLENS_GATEWAY_KEY;
  const base = process.env.TEACHERLENS_BACKEND_URL ?? 'http://127.0.0.1:8000';
  if (!secret || secret.length < 32) return NextResponse.json({detail:'Local server configuration missing. Use the development launcher.'}, {status:503});
  let body: string | undefined;
  if (['POST','PUT'].includes(request.method)) {
    if (request.headers.get('content-type')?.split(';')[0] !== 'application/json') return NextResponse.json({detail:'Send JSON.'}, {status:415});
    const reader = request.body?.getReader(); const chunks: Uint8Array[] = []; let length=0;
    if (reader) { while (true) { const item=await reader.read(); if(item.done)break; length+=item.value.length;
      if(length>4096){await reader.cancel(); return NextResponse.json({detail:'Request is too large.'},{status:413});} chunks.push(item.value); } }
    body = Buffer.concat(chunks).toString('utf8');
  }
  try {
    const upstream = await fetch(`${base}/${path}`, {method:request.method, cache:'no-store', signal:AbortSignal.timeout(20000),
      headers:{'Content-Type':'application/json','X-TeacherLens-Gateway':secret,
        Authorization:`Bearer ${request.cookies.get(cookieName)?.value ?? ''}`}, body});
    const result = await upstream.json();
    if (path === 'session' && request.method === 'POST' && upstream.ok) {
      const response = NextResponse.json({created:true}, {headers:{'Cache-Control':'no-store'}});
      response.cookies.set(cookieName, result.token, {httpOnly:true, sameSite:'strict', secure:new URL(expectedOrigin).protocol==='https:', path:'/', maxAge:7*24*3600});
      return response;
    }
    const response = NextResponse.json(result, {status:upstream.status, headers:{'Cache-Control':'no-store'}});
    if (path==='session' && request.method==='DELETE' && upstream.ok) response.cookies.delete(cookieName);
    return response;
  } catch {
    return NextResponse.json({detail:'The local learning server is unavailable. Your saved work has not been replaced. Try again after restarting it.'},{status:503});
  }
}
export {handle as GET, handle as POST, handle as PUT, handle as DELETE};
