---
name: npm-scripts
description: Run npm/node project tasks — install, build, test, dev server
triggers: [npm, node, package.json, install dependencies, build project, dev server, test project, yarn, pnpm, typescript, react, next, vite]
requires: {bins: [node]}
emoji: 📦
source: builtin
---
# NPM Scripts Skill

Use npm (or yarn/pnpm) via run_command for Node.js project tasks.

## Install dependencies
```
npm install
npm ci           # clean install from lockfile
yarn install
pnpm install
```

## Common scripts
```
npm run dev      # development server
npm run build    # production build
npm run test     # run tests
npm run lint     # linting
npm start        # start server
```

## Package management
```
npm install <package>
npm install -D <package>     # dev dependency
npm uninstall <package>
npm outdated                 # check for updates
npm update
```

## Info
```
npm list                     # installed packages (local)
npm list -g                  # global packages
npm run                      # list available scripts
node --version
npm --version
```

## Tips
- Always run from the project directory (use cwd param in run_command)
- Use --prefix <path> to run npm in a specific folder without cd
- For long builds, increase timeout to 120+ seconds
- Check package.json scripts section first to know available commands
