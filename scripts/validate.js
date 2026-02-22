#!/usr/bin/env node

/**
 * Claude Marketplace Plugin Validator
 * Validates marketplace.json and all plugin structures
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(__dirname, '..');

const COLORS = {
  reset: '\x1b[0m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
};

const log = {
  info: (msg) => console.log(`${COLORS.blue}ℹ${COLORS.reset} ${msg}`),
  success: (msg) => console.log(`${COLORS.green}✓${COLORS.reset} ${msg}`),
  warn: (msg) => console.log(`${COLORS.yellow}⚠${COLORS.reset} ${msg}`),
  error: (msg) => console.log(`${COLORS.red}✗${COLORS.reset} ${msg}`),
  header: (msg) => console.log(`\n${COLORS.cyan}${msg}${COLORS.reset}`),
};

let errors = [];
let warnings = [];

/**
 * Validate semantic version format
 */
function isValidSemver(version) {
  const semverRegex = /^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?(\+[a-zA-Z0-9.-]+)?$/;
  return semverRegex.test(version);
}

/**
 * Validate JSON file syntax
 */
function validateJson(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    JSON.parse(content);
    return { valid: true, data: JSON.parse(content) };
  } catch (e) {
    return { valid: false, error: e.message };
  }
}

/**
 * Validate marketplace.json
 */
function validateMarketplace() {
  log.header('Validating marketplace.json');

  const marketplacePath = path.join(ROOT_DIR, '.claude-plugin', 'marketplace.json');

  if (!fs.existsSync(marketplacePath)) {
    errors.push('marketplace.json not found at .claude-plugin/marketplace.json');
    log.error('marketplace.json not found');
    return null;
  }

  const result = validateJson(marketplacePath);
  if (!result.valid) {
    errors.push(`marketplace.json is invalid JSON: ${result.error}`);
    log.error(`Invalid JSON: ${result.error}`);
    return null;
  }

  const marketplace = result.data;

  // Required fields
  const requiredFields = ['name', 'owner', 'metadata', 'plugins'];
  for (const field of requiredFields) {
    if (!marketplace[field]) {
      errors.push(`marketplace.json missing required field: ${field}`);
      log.error(`Missing required field: ${field}`);
    }
  }

  // Validate owner
  if (marketplace.owner) {
    if (!marketplace.owner.name) {
      warnings.push('marketplace.json: owner.name is recommended');
      log.warn('owner.name is recommended');
    }
  }

  // Validate metadata
  if (marketplace.metadata) {
    if (!marketplace.metadata.description) {
      warnings.push('marketplace.json: metadata.description is recommended');
      log.warn('metadata.description is recommended');
    }
    if (!marketplace.metadata.version) {
      warnings.push('marketplace.json: metadata.version is recommended');
      log.warn('metadata.version is recommended');
    } else if (!isValidSemver(marketplace.metadata.version)) {
      errors.push(`marketplace.json: invalid version format "${marketplace.metadata.version}" (expected semver: x.y.z)`);
      log.error(`Invalid version format: ${marketplace.metadata.version}`);
    } else {
      log.success(`Version: ${marketplace.metadata.version}`);
    }
  }

  // Validate plugins array
  if (Array.isArray(marketplace.plugins)) {
    for (const plugin of marketplace.plugins) {
      if (!plugin.name) {
        errors.push('Plugin entry missing name');
        log.error('Plugin entry missing name');
      }
      if (!plugin.source) {
        errors.push(`Plugin "${plugin.name || 'unknown'}" missing source`);
        log.error(`Plugin "${plugin.name || 'unknown'}" missing source`);
      }
    }
    log.success(`Found ${marketplace.plugins.length} plugin(s) registered`);
  }

  log.success('marketplace.json structure is valid');
  return marketplace;
}

/**
 * Validate a single plugin
 */
function validatePlugin(pluginDir, pluginName) {
  log.header(`Validating plugin: ${pluginName}`);

  const pluginPath = path.join(ROOT_DIR, pluginDir);

  if (!fs.existsSync(pluginPath)) {
    errors.push(`Plugin directory not found: ${pluginDir}`);
    log.error(`Plugin directory not found: ${pluginDir}`);
    return false;
  }

  // Check plugin.json
  const pluginJsonPath = path.join(pluginPath, '.claude-plugin', 'plugin.json');
  if (!fs.existsSync(pluginJsonPath)) {
    errors.push(`${pluginName}: plugin.json not found`);
    log.error('plugin.json not found at .claude-plugin/plugin.json');
    return false;
  }

  const result = validateJson(pluginJsonPath);
  if (!result.valid) {
    errors.push(`${pluginName}: plugin.json is invalid JSON: ${result.error}`);
    log.error(`plugin.json is invalid JSON: ${result.error}`);
    return false;
  }

  const pluginJson = result.data;

  // Required plugin.json fields
  const requiredPluginFields = ['name', 'version', 'description'];
  for (const field of requiredPluginFields) {
    if (!pluginJson[field]) {
      errors.push(`${pluginName}: plugin.json missing required field: ${field}`);
      log.error(`Missing required field: ${field}`);
    }
  }

  // Validate version format
  if (pluginJson.version) {
    if (!isValidSemver(pluginJson.version)) {
      errors.push(`${pluginName}: invalid version format "${pluginJson.version}" (expected semver: x.y.z)`);
      log.error(`Invalid version format: ${pluginJson.version}`);
    } else {
      log.success(`Version: ${pluginJson.version}`);
    }
  }

  log.success('plugin.json is valid');

  // Check component directories
  const components = ['commands', 'skills', 'hooks', 'agents'];
  for (const component of components) {
    const componentPath = path.join(pluginPath, component);
    if (fs.existsSync(componentPath)) {
      const files = fs.readdirSync(componentPath);
      if (files.length > 0) {
        log.success(`${component}/: ${files.length} file(s)`);

        // Validate specific component files
        if (component === 'hooks') {
          validateHooks(componentPath, pluginName);
        } else if (component === 'skills') {
          validateSkills(componentPath, pluginName);
        }
      }
    }
  }

  // Check for README
  const readmePath = path.join(pluginPath, 'README.md');
  if (fs.existsSync(readmePath)) {
    log.success('README.md exists');
  } else {
    warnings.push(`${pluginName}: README.md is recommended`);
    log.warn('README.md is recommended');
  }

  // Check for MCP config
  const mcpPath = path.join(pluginPath, '.mcp.json');
  if (fs.existsSync(mcpPath)) {
    const mcpResult = validateJson(mcpPath);
    if (mcpResult.valid) {
      log.success('.mcp.json is valid');
    } else {
      errors.push(`${pluginName}: .mcp.json is invalid JSON`);
      log.error('.mcp.json is invalid JSON');
    }
  }

  return true;
}

/**
 * Validate hooks configuration
 */
function validateHooks(hooksDir, pluginName) {
  const hooksJsonPath = path.join(hooksDir, 'hooks.json');
  if (fs.existsSync(hooksJsonPath)) {
    const result = validateJson(hooksJsonPath);
    if (!result.valid) {
      errors.push(`${pluginName}: hooks/hooks.json is invalid JSON`);
      log.error('hooks.json is invalid JSON');
      return;
    }

    const hooks = result.data.hooks || [];
    const validEvents = ['SessionStart', 'PreToolUse', 'PostToolUse', 'Stop'];

    for (const hook of hooks) {
      if (!hook.name) {
        warnings.push(`${pluginName}: hook missing name`);
      }
      if (!hook.event) {
        errors.push(`${pluginName}: hook "${hook.name || 'unknown'}" missing event`);
      } else if (!validEvents.includes(hook.event)) {
        warnings.push(`${pluginName}: hook "${hook.name}" has unknown event: ${hook.event}`);
      }
      if (!hook.command) {
        errors.push(`${pluginName}: hook "${hook.name || 'unknown'}" missing command`);
      }
    }
  }
}

/**
 * Validate skills structure
 */
function validateSkills(skillsDir, pluginName) {
  const skillDirs = fs.readdirSync(skillsDir, { withFileTypes: true })
    .filter(d => d.isDirectory());

  for (const dir of skillDirs) {
    const skillMdPath = path.join(skillsDir, dir.name, 'SKILL.md');
    if (!fs.existsSync(skillMdPath)) {
      warnings.push(`${pluginName}: skill "${dir.name}" missing SKILL.md`);
      log.warn(`Skill "${dir.name}" missing SKILL.md`);
    }
  }
}

/**
 * Main validation function
 */
function main() {
  const args = process.argv.slice(2);
  const marketplaceOnly = args.includes('--marketplace-only');
  const pluginsOnly = args.includes('--plugins-only');
  const staged = args.includes('--staged');

  console.log(`\n${COLORS.cyan}═══════════════════════════════════════════${COLORS.reset}`);
  console.log(`${COLORS.cyan}   Claude Marketplace Plugin Validator${COLORS.reset}`);
  console.log(`${COLORS.cyan}═══════════════════════════════════════════${COLORS.reset}`);

  let marketplace = null;

  // Validate marketplace.json
  if (!pluginsOnly) {
    marketplace = validateMarketplace();
  }

  // Validate plugins
  if (!marketplaceOnly && marketplace?.plugins) {
    for (const plugin of marketplace.plugins) {
      validatePlugin(plugin.source, plugin.name);
    }
  } else if (!marketplaceOnly && !marketplace) {
    // Still try to validate plugins directory if marketplace.json is invalid
    const pluginsDir = path.join(ROOT_DIR, 'plugins');
    if (fs.existsSync(pluginsDir)) {
      const pluginDirs = fs.readdirSync(pluginsDir, { withFileTypes: true })
        .filter(d => d.isDirectory());

      for (const dir of pluginDirs) {
        validatePlugin(`plugins/${dir.name}`, dir.name);
      }
    }
  }

  // Summary
  console.log(`\n${COLORS.cyan}═══════════════════════════════════════════${COLORS.reset}`);
  console.log(`${COLORS.cyan}   Validation Summary${COLORS.reset}`);
  console.log(`${COLORS.cyan}═══════════════════════════════════════════${COLORS.reset}\n`);

  if (warnings.length > 0) {
    log.warn(`${warnings.length} warning(s)`);
    warnings.forEach(w => console.log(`   - ${w}`));
  }

  if (errors.length > 0) {
    log.error(`${errors.length} error(s)`);
    errors.forEach(e => console.log(`   - ${e}`));
    console.log('');
    process.exit(1);
  }

  log.success('All validations passed!\n');
  process.exit(0);
}

main();
