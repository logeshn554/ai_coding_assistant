const fs = require('fs');
const path = require('path');

let ts;
try {
  ts = require('typescript');
} catch (e1) {
  try {
    const frontTs = path.join(__dirname, '../../frontend/node_modules/typescript');
    ts = require(frontTs);
  } catch (e2) {
    try {
      const frontTs2 = path.join(process.cwd(), 'frontend/node_modules/typescript');
      ts = require(frontTs2);
    } catch (e3) {
      ts = null;
    }
  }
}

/**
 * Load tsconfig/jsconfig paths and baseUrl
 */
function loadTsConfig(workspaceRoot) {
  const configs = ['tsconfig.app.json', 'tsconfig.json', 'jsconfig.json', 'frontend/tsconfig.app.json', 'frontend/tsconfig.json'];
  let baseUrl = '';
  let paths = {};
  let configDir = workspaceRoot;

  for (const cfgName of configs) {
    const fullPath = path.join(workspaceRoot, cfgName);
    if (fs.existsSync(fullPath)) {
      try {
        let content = fs.readFileSync(fullPath, 'utf8');
        // Remove trailing commas and comments simple cleanup
        content = content.replace(/\/\*[\s\S]*?\*\/|([^\\:]|^)\/\/.*$/gm, '$1');
        const json = JSON.parse(content);
        const opts = json.compilerOptions || {};
        if (opts.paths) {
          paths = { ...paths, ...opts.paths };
        }
        if (opts.baseUrl && !baseUrl) {
          baseUrl = opts.baseUrl;
          configDir = path.dirname(fullPath);
        }
      } catch (err) {
        // ignore parse error for draft/partial tsconfigs
      }
    }
  }

  return { baseUrl, paths, configDir };
}

/**
 * Resolve a path alias using compilerOptions.paths
 */
function resolveAlias(specifier, workspaceRoot, tsConfig) {
  const { paths, baseUrl, configDir } = tsConfig;
  if (!paths || Object.keys(paths).length === 0) return null;

  for (const pattern of Object.keys(paths)) {
    const targets = paths[pattern];
    if (!targets || targets.length === 0) continue;

    if (pattern.endsWith('*')) {
      const prefix = pattern.slice(0, -1);
      if (specifier.startsWith(prefix)) {
        const remainder = specifier.slice(prefix.length);
        const targetPattern = targets[0];
        const targetPrefix = targetPattern.endsWith('*') ? targetPattern.slice(0, -1) : targetPattern;
        
        const baseDir = baseUrl ? path.resolve(configDir, baseUrl) : workspaceRoot;
        const resolvedPath = path.resolve(baseDir, targetPrefix + remainder);
        const relPath = path.relative(workspaceRoot, resolvedPath).replace(/\\/g, '/');
        return relPath;
      }
    } else if (specifier === pattern) {
      const baseDir = baseUrl ? path.resolve(configDir, baseUrl) : workspaceRoot;
      const resolvedPath = path.resolve(baseDir, targets[0]);
      const relPath = path.relative(workspaceRoot, resolvedPath).replace(/\\/g, '/');
      return relPath;
    }
  }

  return null;
}

function extractImportsFromFile(filePath, workspaceRoot, tsConfig) {
  const imports = [];
  if (!fs.existsSync(filePath)) return imports;

  let code;
  try {
    code = fs.readFileSync(filePath, 'utf8');
  } catch (e) {
    return imports;
  }

  if (!ts) {
    // Regex fallback if TS module unavailable
    const regex = /(?:import|from)\s+['"]([^'"]+)['"]/g;
    let match;
    while ((match = regex.exec(code)) !== null) {
      imports.push(match[1]);
    }
    return imports;
  }

  try {
    const sourceFile = ts.createSourceFile(
      filePath,
      code,
      ts.ScriptTarget.Latest,
      true
    );

    function visit(node) {
      // 1. ES6 import statement: import ... from '...'
      if (ts.isImportDeclaration(node) && node.moduleSpecifier && ts.isStringLiteral(node.moduleSpecifier)) {
        imports.push(node.moduleSpecifier.text);
      }
      // 2. Export statement: export ... from '...'
      else if (ts.isExportDeclaration(node) && node.moduleSpecifier && ts.isStringLiteral(node.moduleSpecifier)) {
        imports.push(node.moduleSpecifier.text);
      }
      // 3. Dynamic import() or require()
      else if (ts.isCallExpression(node)) {
        const expr = node.expression;
        const isDynamicImport = expr.kind === ts.SyntaxKind.ImportKeyword;
        const isRequire = ts.isIdentifier(expr) && expr.text === 'require';

        if ((isDynamicImport || isRequire) && node.arguments.length > 0) {
          const arg = node.arguments[0];
          if (ts.isStringLiteral(arg)) {
            imports.push(arg.text);
          }
        }
      }

      ts.forEachChild(node, visit);
    }

    visit(sourceFile);
  } catch (err) {
    // fallback if AST parsing fails
  }

  return imports;
}

function main() {
  let inputData = '';
  process.stdin.setEncoding('utf8');

  process.stdin.on('data', chunk => {
    inputData += chunk;
  });

  process.stdin.on('end', () => {
    if (!inputData.trim()) {
      console.log(JSON.stringify({ error: 'No input provided' }));
      return;
    }

    try {
      const payload = JSON.parse(inputData);
      const workspaceRoot = payload.workspace_root || process.cwd();
      const files = payload.files || [];

      const tsConfig = loadTsConfig(workspaceRoot);
      const result = {};

      for (const relFile of files) {
        const absFile = path.resolve(workspaceRoot, relFile);
        const rawImports = extractImportsFromFile(absFile, workspaceRoot, tsConfig);
        
        const resolvedImports = rawImports.map(imp => {
          // Check path alias resolution
          const aliasResolved = resolveAlias(imp, workspaceRoot, tsConfig);
          if (aliasResolved) {
            return aliasResolved;
          }
          return imp;
        });

        result[relFile] = resolvedImports;
      }

      console.log(JSON.stringify(result));
    } catch (e) {
      console.log(JSON.stringify({ error: e.message }));
    }
  });
}

main();
