#!/usr/bin/env node
/**
 * Fails the build if the produced bundle still contains configuration placeholders
 * or dev-only code (the homework mock backend and the ?demo login).
 * Runs automatically after `npm run build` (npm "postbuild" hook).
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const BUNDLE_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '../dist')
const FORBIDDEN = [
  'BACKEND_URL_PLACEHOLDER', // set-env.mjs did not run
  'green-and-tasty-demo', // DEMO_ISSUER of the dev-only ?demo login
  'demo-invite-token', // dev-only group pre-order mock backend
]

function walk(dir) {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry)
    return statSync(full).isDirectory() ? walk(full) : [full]
  })
}

let failed = false

for (const file of walk(BUNDLE_DIR).filter((path) => /\.(js|css|html)$/.test(path))) {
  const contents = readFileSync(file, 'utf8')
  for (const token of FORBIDDEN) {
    if (contents.includes(token)) {
      console.error(`${token} found in ${file.replace(`${BUNDLE_DIR}/`, '')}`)
      failed = true
    }
  }
}

if (failed) {
  console.error('\nBundle is not deployable: placeholders or dev-only code made it into dist/.')
  process.exit(1)
}

console.log('Bundle check passed: no configuration placeholders or dev-only code left.')
