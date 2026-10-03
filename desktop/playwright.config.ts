import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests',testMatch:'**/*.spec.ts',workers:1,timeout:60000,reporter:[['list'],['json',{outputFile:'../docs/reports/desktop-tests.json'}],['html',{outputFolder:'playwright-report',open:'never'}]],use:{trace:'retain-on-failure'}});
