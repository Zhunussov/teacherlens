import {defineConfig, devices} from '@playwright/test';
import {existsSync} from 'node:fs';
import {resolve} from 'node:path';
const local = resolve('..', '.venv', process.platform==='win32'?'Scripts/python.exe':'bin/python');
const python = process.env.TEACHERLENS_PYTHON ?? (existsSync(local)?local:'python');
export default defineConfig({
  testDir:'./tests', timeout:90000, fullyParallel:false, workers:1, retries:0,
  reporter:'list', use:{baseURL:'http://127.0.0.1:3000',trace:'retain-on-failure'},
  projects:[{name:'chromium',use:{...devices['Desktop Chrome']}}],
  webServer:{command:`"${python}" ../scripts/dev_mvp.py --production-build --test-db`,url:'http://127.0.0.1:3000',timeout:90000,reuseExistingServer:false},
});
