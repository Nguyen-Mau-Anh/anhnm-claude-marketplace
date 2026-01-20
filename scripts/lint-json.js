#!/usr/bin/env node

/**
 * JSON Linter for Claude Marketplace
 * Validates JSON files for syntax errors
 */

import fs from 'fs';
import path from 'path';

const COLORS = {
  reset: '\x1b[0m',
  red: '\x1b[31m',
  green: '\x1b[32m',
};

const args = process.argv.slice(2);
let hasErrors = false;

function lintJsonFile(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    JSON.parse(content);
    console.log(`${COLORS.green}✓${COLORS.reset} ${filePath}`);
    return true;
  } catch (e) {
    console.log(`${COLORS.red}✗${COLORS.reset} ${filePath}`);
    console.log(`  ${e.message}`);
    return false;
  }
}

if (args.length === 0) {
  console.log('Usage: lint-json.js <file1.json> [file2.json] ...');
  process.exit(1);
}

console.log('\nLinting JSON files...\n');

for (const file of args) {
  if (fs.existsSync(file) && file.endsWith('.json')) {
    if (!lintJsonFile(file)) {
      hasErrors = true;
    }
  }
}

console.log('');

if (hasErrors) {
  process.exit(1);
}
