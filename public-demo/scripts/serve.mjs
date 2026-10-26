// A deliberately small static preview server. No application backend or persistence.
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {resolve,sep,extname} from 'node:path';
const root=resolve('out');
const deploymentConfig=JSON.parse(await readFile(resolve('vercel.json'),'utf8'));
const headers=Object.fromEntries(deploymentConfig.headers[0].headers.map(h=>[h.key,h.value]));
const types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.svg':'image/svg+xml','.txt':'text/plain; charset=utf-8','.json':'application/json'};
const server=createServer(async(req,res)=>{try{
 const url=new URL(req.url,'http://localhost');const path=resolve(root,'.'+decodeURIComponent(url.pathname==='/'?'/index.html':url.pathname));
 if(!path.startsWith(root+sep)){res.writeHead(403).end();return;}
 const body=await readFile(path);res.writeHead(200,{...headers,'Content-Type':types[extname(path)]??'application/octet-stream'});res.end(body);
}catch{res.writeHead(404,{'Content-Type':'text/plain'}).end('Not found');}});
server.listen(Number(process.env.PORT??3001),'127.0.0.1',()=>console.log('TeacherLens public static preview: http://127.0.0.1:'+Number(process.env.PORT??3001)));
