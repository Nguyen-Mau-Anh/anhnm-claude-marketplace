#!/usr/bin/env node

/**
 * Claude Marketplace Plugin Version Manager
 * Bump versions, manage changelogs, and track plugin updates
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import readline from 'readline';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(__dirname, '..');

const COLORS = {
  reset: '\x1b[0m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
  bold: '\x1b[1m',
};

const log = {
  info: (msg) => console.log(`${COLORS.blue}ℹ${COLORS.reset} ${msg}`),
  success: (msg) => console.log(`${COLORS.green}✓${COLORS.reset} ${msg}`),
  warn: (msg) => console.log(`${COLORS.yellow}⚠${COLORS.reset} ${msg}`),
  error: (msg) => console.log(`${COLORS.red}✗${COLORS.reset} ${msg}`),
  header: (msg) => console.log(`\n${COLORS.cyan}${COLORS.bold}${msg}${COLORS.reset}`),
};

/**
 * Parse semantic version
 */
function parseVersion(version) {
  const match = version.match(/^(\d+)\.(\d+)\.(\d+)(-(.+))?$/);
  if (!match) return null;
  return {
    major: parseInt(match[1]),
    minor: parseInt(match[2]),
    patch: parseInt(match[3]),
    prerelease: match[5] || null,
  };
}

/**
 * Bump version based on type
 */
function bumpVersion(version, type) {
  const v = parseVersion(version);
  if (!v) return null;

  switch (type) {
    case 'major':
      return `${v.major + 1}.0.0`;
    case 'minor':
      return `${v.major}.${v.minor + 1}.0`;
    case 'patch':
      return `${v.major}.${v.minor}.${v.patch + 1}`;
    default:
      return null;
  }
}

/**
 * Get all plugins
 */
function getPlugins() {
  const pluginsDir = path.join(ROOT_DIR, 'plugins');
  if (!fs.existsSync(pluginsDir)) return [];

  return fs.readdirSync(pluginsDir, { withFileTypes: true })
    .filter(d => d.isDirectory())
    .map(d => {
      const pluginJsonPath = path.join(pluginsDir, d.name, '.claude-plugin', 'plugin.json');
      if (!fs.existsSync(pluginJsonPath)) return null;

      try {
        const pluginJson = JSON.parse(fs.readFileSync(pluginJsonPath, 'utf-8'));
        return {
          name: d.name,
          path: path.join(pluginsDir, d.name),
          jsonPath: pluginJsonPath,
          version: pluginJson.version || '0.0.0',
          data: pluginJson,
        };
      } catch {
        return null;
      }
    })
    .filter(Boolean);
}

/**
 * List all plugin versions
 */
function listVersions() {
  log.header('Plugin Versions');
  console.log('');

  const plugins = getPlugins();
  if (plugins.length === 0) {
    log.warn('No plugins found');
    return;
  }

  const maxNameLen = Math.max(...plugins.map(p => p.name.length));

  for (const plugin of plugins) {
    const padding = ' '.repeat(maxNameLen - plugin.name.length);
    console.log(`  ${COLORS.cyan}${plugin.name}${COLORS.reset}${padding}  v${plugin.version}`);
  }

  // Also show marketplace version
  const marketplacePath = path.join(ROOT_DIR, '.claude-plugin', 'marketplace.json');
  if (fs.existsSync(marketplacePath)) {
    const marketplace = JSON.parse(fs.readFileSync(marketplacePath, 'utf-8'));
    console.log('');
    console.log(`  ${COLORS.yellow}marketplace${COLORS.reset}${' '.repeat(maxNameLen - 11)}  v${marketplace.metadata?.version || '0.0.0'}`);
  }

  console.log('');
}

/**
 * Update changelog
 */
function updateChangelog(pluginPath, version, changes) {
  const changelogPath = path.join(pluginPath, 'CHANGELOG.md');
  const date = new Date().toISOString().split('T')[0];

  let changelog = '';
  if (fs.existsSync(changelogPath)) {
    changelog = fs.readFileSync(changelogPath, 'utf-8');
  } else {
    changelog = `# Changelog

All notable changes to this plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

`;
  }

  // Find insertion point (after header)
  const headerEnd = changelog.indexOf('\n## ');
  const insertPoint = headerEnd === -1 ? changelog.length : headerEnd;

  const newEntry = `
## [${version}] - ${date}

### Changed
- ${changes || 'Version bump'}
`;

  const updatedChangelog =
    changelog.slice(0, insertPoint) +
    newEntry +
    changelog.slice(insertPoint);

  fs.writeFileSync(changelogPath, updatedChangelog);
  return changelogPath;
}

/**
 * Bump plugin version
 */
async function bumpPluginVersion(pluginName, type, changes) {
  const plugins = getPlugins();
  const plugin = plugins.find(p => p.name === pluginName);

  if (!plugin) {
    log.error(`Plugin "${pluginName}" not found`);
    return false;
  }

  const newVersion = bumpVersion(plugin.version, type);
  if (!newVersion) {
    log.error(`Invalid version format: ${plugin.version}`);
    return false;
  }

  // Update plugin.json
  plugin.data.version = newVersion;
  fs.writeFileSync(plugin.jsonPath, JSON.stringify(plugin.data, null, 2) + '\n');
  log.success(`Updated ${plugin.name} version: ${plugin.version} → ${newVersion}`);

  // Update changelog
  const changelogPath = updateChangelog(plugin.path, newVersion, changes);
  log.success(`Updated changelog: ${path.relative(ROOT_DIR, changelogPath)}`);

  return true;
}

/**
 * Bump marketplace version
 */
function bumpMarketplaceVersion(type) {
  const marketplacePath = path.join(ROOT_DIR, '.claude-plugin', 'marketplace.json');
  if (!fs.existsSync(marketplacePath)) {
    log.error('marketplace.json not found');
    return false;
  }

  const marketplace = JSON.parse(fs.readFileSync(marketplacePath, 'utf-8'));
  const currentVersion = marketplace.metadata?.version || '1.0.0';
  const newVersion = bumpVersion(currentVersion, type);

  if (!newVersion) {
    log.error(`Invalid version format: ${currentVersion}`);
    return false;
  }

  marketplace.metadata = marketplace.metadata || {};
  marketplace.metadata.version = newVersion;
  fs.writeFileSync(marketplacePath, JSON.stringify(marketplace, null, 2) + '\n');

  log.success(`Updated marketplace version: ${currentVersion} → ${newVersion}`);
  return true;
}

/**
 * Interactive mode
 */
async function interactiveMode() {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  const question = (q) => new Promise(resolve => rl.question(q, resolve));

  log.header('Interactive Version Manager');
  console.log('');

  // List plugins
  const plugins = getPlugins();
  console.log('Available plugins:');
  plugins.forEach((p, i) => {
    console.log(`  ${COLORS.cyan}${i + 1}${COLORS.reset}. ${p.name} (v${p.version})`);
  });
  console.log(`  ${COLORS.yellow}m${COLORS.reset}. marketplace`);
  console.log('');

  const selection = await question('Select plugin to bump (number/m): ');

  let target;
  if (selection.toLowerCase() === 'm') {
    target = 'marketplace';
  } else {
    const index = parseInt(selection) - 1;
    if (isNaN(index) || index < 0 || index >= plugins.length) {
      log.error('Invalid selection');
      rl.close();
      return;
    }
    target = plugins[index].name;
  }

  console.log('');
  console.log('Bump type:');
  console.log(`  ${COLORS.cyan}1${COLORS.reset}. patch (bug fixes)`);
  console.log(`  ${COLORS.cyan}2${COLORS.reset}. minor (new features)`);
  console.log(`  ${COLORS.cyan}3${COLORS.reset}. major (breaking changes)`);
  console.log('');

  const typeSelection = await question('Select bump type (1/2/3): ');
  const types = ['patch', 'minor', 'major'];
  const type = types[parseInt(typeSelection) - 1];

  if (!type) {
    log.error('Invalid bump type');
    rl.close();
    return;
  }

  let changes = '';
  if (target !== 'marketplace') {
    console.log('');
    changes = await question('Describe changes (optional): ');
  }

  console.log('');

  if (target === 'marketplace') {
    bumpMarketplaceVersion(type);
  } else {
    await bumpPluginVersion(target, type, changes);
  }

  rl.close();
}

/**
 * Show help
 */
function showHelp() {
  console.log(`
${COLORS.cyan}${COLORS.bold}Claude Marketplace Version Manager${COLORS.reset}

${COLORS.bold}Usage:${COLORS.reset}
  node scripts/version.js [command] [options]

${COLORS.bold}Commands:${COLORS.reset}
  list                          List all plugin versions
  bump <plugin> <type>          Bump plugin version
  bump-marketplace <type>       Bump marketplace version
  interactive, -i               Interactive mode

${COLORS.bold}Bump Types:${COLORS.reset}
  patch     Bug fixes (1.0.0 → 1.0.1)
  minor     New features (1.0.0 → 1.1.0)
  major     Breaking changes (1.0.0 → 2.0.0)

${COLORS.bold}Options:${COLORS.reset}
  -m, --message <msg>   Changelog message for the version bump

${COLORS.bold}Examples:${COLORS.reset}
  node scripts/version.js list
  node scripts/version.js bump hello-world patch
  node scripts/version.js bump hello-world minor -m "Add new greeting formats"
  node scripts/version.js bump-marketplace minor
  node scripts/version.js -i
`);
}

/**
 * Main
 */
async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0 || args[0] === '--help' || args[0] === '-h') {
    showHelp();
    return;
  }

  const command = args[0];

  switch (command) {
    case 'list':
      listVersions();
      break;

    case 'bump':
      if (args.length < 3) {
        log.error('Usage: bump <plugin-name> <patch|minor|major> [-m message]');
        process.exit(1);
      }
      const msgIndex = args.indexOf('-m') !== -1 ? args.indexOf('-m') : args.indexOf('--message');
      const message = msgIndex !== -1 ? args[msgIndex + 1] : '';
      await bumpPluginVersion(args[1], args[2], message);
      break;

    case 'bump-marketplace':
      if (args.length < 2) {
        log.error('Usage: bump-marketplace <patch|minor|major>');
        process.exit(1);
      }
      bumpMarketplaceVersion(args[1]);
      break;

    case 'interactive':
    case '-i':
      await interactiveMode();
      break;

    default:
      log.error(`Unknown command: ${command}`);
      showHelp();
      process.exit(1);
  }
}

main();
