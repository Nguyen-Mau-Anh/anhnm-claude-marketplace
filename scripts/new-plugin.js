#!/usr/bin/env node

/**
 * Claude Marketplace Plugin Scaffolding Tool
 * Quickly create new plugins with proper structure
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

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
});

const question = (q) => new Promise(resolve => rl.question(q, resolve));

/**
 * Create plugin.json
 */
function createPluginJson(pluginPath, config) {
  const pluginJson = {
    name: config.name,
    version: '1.0.0',
    description: config.description,
    author: {
      name: config.author || 'anhnm',
    },
    license: 'MIT',
    keywords: config.keywords || [],
  };

  const jsonPath = path.join(pluginPath, '.claude-plugin', 'plugin.json');
  fs.writeFileSync(jsonPath, JSON.stringify(pluginJson, null, 2) + '\n');
  return jsonPath;
}

/**
 * Create CHANGELOG.md
 */
function createChangelog(pluginPath, config) {
  const date = new Date().toISOString().split('T')[0];
  const content = `# Changelog

All notable changes to this plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - ${date}

### Added
- Initial release
- ${config.description}
`;

  const changelogPath = path.join(pluginPath, 'CHANGELOG.md');
  fs.writeFileSync(changelogPath, content);
  return changelogPath;
}

/**
 * Create README.md
 */
function createReadme(pluginPath, config) {
  let componentsSection = '## Components\n\n';

  if (config.hasCommands) {
    componentsSection += `### Commands
- \`/${config.name}\` - Description of command

`;
  }

  if (config.hasSkills) {
    componentsSection += `### Skills
- \`${config.name}-skill\` - Description of skill

`;
  }

  if (config.hasHooks) {
    componentsSection += `### Hooks
- \`${config.name}-hook\` - Description of hook

`;
  }

  if (config.hasAgents) {
    componentsSection += `### Agents
- \`${config.name}-agent\` - Description of agent

`;
  }

  const content = `# ${config.name}

${config.description}

## Installation

\`\`\`bash
/plugin marketplace add anhnm/anhnm-claude-marketplace
/plugin install ${config.name}
\`\`\`

${componentsSection}
## Usage

Describe how to use this plugin.

## License

MIT
`;

  const readmePath = path.join(pluginPath, 'README.md');
  fs.writeFileSync(readmePath, content);
  return readmePath;
}

/**
 * Create example command
 */
function createExampleCommand(pluginPath, config) {
  const content = `# /${config.name}

${config.description}

## Usage

\`\`\`
/${config.name} [args]
\`\`\`

## Description

Detailed description of what this command does.

## Instructions

When the user invokes this command:

1. First step...
2. Second step...
3. Return the result...

## Examples

- \`/${config.name}\` - Basic usage
- \`/${config.name} --option\` - With option
`;

  const cmdPath = path.join(pluginPath, 'commands', `${config.name}.md`);
  fs.writeFileSync(cmdPath, content);
  return cmdPath;
}

/**
 * Create example skill
 */
function createExampleSkill(pluginPath, config) {
  const skillDir = path.join(pluginPath, 'skills', `${config.name}-skill`);
  fs.mkdirSync(skillDir, { recursive: true });

  const content = `# ${config.name} Skill

${config.description}

## When to Use

Use this skill when:
- Condition 1
- Condition 2
- Condition 3

## Instructions

When this skill is active:

1. **Step One** - Description of first step
2. **Step Two** - Description of second step
3. **Step Three** - Description of third step

## Example Behaviors

### Scenario 1
How to behave in this scenario.

### Scenario 2
How to behave in this scenario.

## Integration

Notes on how this skill integrates with other components.
`;

  const skillPath = path.join(skillDir, 'SKILL.md');
  fs.writeFileSync(skillPath, content);
  return skillPath;
}

/**
 * Create example hooks
 */
function createExampleHooks(pluginPath, config) {
  const content = {
    hooks: [
      {
        name: `${config.name}-hook`,
        event: 'SessionStart',
        description: `Hook for ${config.name} plugin`,
        command: `echo '${config.name} plugin loaded'`,
      },
    ],
  };

  const hooksPath = path.join(pluginPath, 'hooks', 'hooks.json');
  fs.writeFileSync(hooksPath, JSON.stringify(content, null, 2) + '\n');
  return hooksPath;
}

/**
 * Create example agent
 */
function createExampleAgent(pluginPath, config) {
  const content = `# ${config.name} Agent

${config.description}

## Purpose

Detailed explanation of what this agent specializes in.

## Capabilities

- Capability 1
- Capability 2
- Capability 3

## When to Invoke

This agent should be invoked when:
- Condition 1
- Condition 2

## Behavior

1. Assess the situation
2. Take appropriate action
3. Report results

## Example Interaction

User: "Example user request"

Agent: "Example response demonstrating the agent's behavior and capabilities."
`;

  const agentPath = path.join(pluginPath, 'agents', `${config.name}-agent.md`);
  fs.writeFileSync(agentPath, content);
  return agentPath;
}

/**
 * Update marketplace.json
 */
function updateMarketplace(config) {
  const marketplacePath = path.join(ROOT_DIR, '.claude-plugin', 'marketplace.json');
  const marketplace = JSON.parse(fs.readFileSync(marketplacePath, 'utf-8'));

  // Check if plugin already exists
  const exists = marketplace.plugins.some(p => p.name === config.name);
  if (exists) {
    log.warn(`Plugin "${config.name}" already registered in marketplace.json`);
    return false;
  }

  marketplace.plugins.push({
    name: config.name,
    source: `./plugins/${config.name}`,
    description: config.description,
  });

  fs.writeFileSync(marketplacePath, JSON.stringify(marketplace, null, 2) + '\n');
  return true;
}

/**
 * Interactive mode
 */
async function interactive() {
  log.header('Create New Plugin');
  console.log('');

  // Get plugin name
  const name = await question('Plugin name (kebab-case): ');
  if (!name || !/^[a-z][a-z0-9-]*$/.test(name)) {
    log.error('Invalid plugin name. Use kebab-case (e.g., my-plugin)');
    rl.close();
    process.exit(1);
  }

  // Check if exists
  const pluginPath = path.join(ROOT_DIR, 'plugins', name);
  if (fs.existsSync(pluginPath)) {
    log.error(`Plugin "${name}" already exists`);
    rl.close();
    process.exit(1);
  }

  // Get description
  const description = await question('Description: ') || `${name} plugin`;

  // Get author
  const author = await question('Author (default: anhnm): ') || 'anhnm';

  // Get keywords
  const keywordsInput = await question('Keywords (comma-separated): ');
  const keywords = keywordsInput ? keywordsInput.split(',').map(k => k.trim()) : [];

  // Component selection
  console.log('\nSelect components to include:');
  const hasCommands = (await question('Include commands? (Y/n): ')).toLowerCase() !== 'n';
  const hasSkills = (await question('Include skills? (Y/n): ')).toLowerCase() !== 'n';
  const hasHooks = (await question('Include hooks? (Y/n): ')).toLowerCase() !== 'n';
  const hasAgents = (await question('Include agents? (Y/n): ')).toLowerCase() !== 'n';

  const config = {
    name,
    description,
    author,
    keywords,
    hasCommands,
    hasSkills,
    hasHooks,
    hasAgents,
  };

  console.log('');
  log.header('Creating Plugin');

  // Create directories
  const dirs = ['.claude-plugin'];
  if (hasCommands) dirs.push('commands');
  if (hasSkills) dirs.push('skills');
  if (hasHooks) dirs.push('hooks');
  if (hasAgents) dirs.push('agents');

  for (const dir of dirs) {
    fs.mkdirSync(path.join(pluginPath, dir), { recursive: true });
  }
  log.success(`Created plugin directory: plugins/${name}/`);

  // Create files
  createPluginJson(pluginPath, config);
  log.success('Created .claude-plugin/plugin.json');

  createChangelog(pluginPath, config);
  log.success('Created CHANGELOG.md');

  createReadme(pluginPath, config);
  log.success('Created README.md');

  if (hasCommands) {
    createExampleCommand(pluginPath, config);
    log.success(`Created commands/${name}.md`);
  }

  if (hasSkills) {
    createExampleSkill(pluginPath, config);
    log.success(`Created skills/${name}-skill/SKILL.md`);
  }

  if (hasHooks) {
    createExampleHooks(pluginPath, config);
    log.success('Created hooks/hooks.json');
  }

  if (hasAgents) {
    createExampleAgent(pluginPath, config);
    log.success(`Created agents/${name}-agent.md`);
  }

  // Update marketplace
  if (updateMarketplace(config)) {
    log.success('Registered in marketplace.json');
  }

  console.log('');
  log.header('Plugin Created Successfully!');
  console.log(`
Next steps:
  1. Edit the generated files in plugins/${name}/
  2. Run ${COLORS.cyan}npm run validate${COLORS.reset} to check your plugin
  3. Commit your changes with ${COLORS.cyan}git commit -m "feat(${name}): add ${name} plugin"${COLORS.reset}
`);

  rl.close();
}

/**
 * Quick create (non-interactive)
 */
function quickCreate(name, description) {
  if (!name || !/^[a-z][a-z0-9-]*$/.test(name)) {
    log.error('Invalid plugin name. Use kebab-case (e.g., my-plugin)');
    process.exit(1);
  }

  const pluginPath = path.join(ROOT_DIR, 'plugins', name);
  if (fs.existsSync(pluginPath)) {
    log.error(`Plugin "${name}" already exists`);
    process.exit(1);
  }

  const config = {
    name,
    description: description || `${name} plugin`,
    author: 'anhnm',
    keywords: [],
    hasCommands: true,
    hasSkills: true,
    hasHooks: true,
    hasAgents: true,
  };

  // Create all directories
  const dirs = ['.claude-plugin', 'commands', 'skills', 'hooks', 'agents'];
  for (const dir of dirs) {
    fs.mkdirSync(path.join(pluginPath, dir), { recursive: true });
  }

  // Create all files
  createPluginJson(pluginPath, config);
  createChangelog(pluginPath, config);
  createReadme(pluginPath, config);
  createExampleCommand(pluginPath, config);
  createExampleSkill(pluginPath, config);
  createExampleHooks(pluginPath, config);
  createExampleAgent(pluginPath, config);
  updateMarketplace(config);

  log.success(`Created plugin: ${name}`);
  log.info(`Edit files in plugins/${name}/ and run npm run validate`);
}

/**
 * Show help
 */
function showHelp() {
  console.log(`
${COLORS.cyan}${COLORS.bold}Claude Marketplace Plugin Scaffolding${COLORS.reset}

${COLORS.bold}Usage:${COLORS.reset}
  node scripts/new-plugin.js [options]
  node scripts/new-plugin.js <name> [description]

${COLORS.bold}Options:${COLORS.reset}
  -i, --interactive    Interactive mode (default if no args)
  -h, --help           Show this help

${COLORS.bold}Examples:${COLORS.reset}
  node scripts/new-plugin.js                           # Interactive mode
  node scripts/new-plugin.js -i                        # Interactive mode
  node scripts/new-plugin.js my-plugin                 # Quick create
  node scripts/new-plugin.js my-plugin "My plugin"    # Quick create with description
`);
}

/**
 * Main
 */
async function main() {
  const args = process.argv.slice(2);

  if (args.includes('-h') || args.includes('--help')) {
    showHelp();
    process.exit(0);
  }

  if (args.length === 0 || args.includes('-i') || args.includes('--interactive')) {
    await interactive();
  } else {
    quickCreate(args[0], args[1]);
    rl.close();
  }
}

main();
