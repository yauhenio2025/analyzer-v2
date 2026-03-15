import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(__dirname, '..')
const packageJsonPath = path.join(rootDir, 'package.json')
const artifactDir = path.join(rootDir, 'release-artifacts')

const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'))
const packageName = packageJson.name
const version = packageJson.version

if (packageName !== '@the-syllabus/analysis-renderers') {
  console.error(`Unexpected package identity: ${packageName}`)
  process.exit(1)
}

const tarballName = packageName.replace('@', '').replace('/', '-') + `-${version}.tgz`
const tarballPath = path.join(artifactDir, tarballName)

if (fs.existsSync(tarballPath)) {
  console.error(`Refusing to overwrite existing tarball for version ${version}: ${tarballPath}`)
  process.exit(1)
}

fs.mkdirSync(artifactDir, { recursive: true })

const buildResult = spawnSync('npm', ['run', 'build'], {
  cwd: rootDir,
  stdio: 'inherit',
  env: process.env,
})

if (buildResult.status !== 0) {
  process.exit(buildResult.status ?? 1)
}

const packResult = spawnSync('npm', ['pack', '--json', '--pack-destination', artifactDir], {
  cwd: rootDir,
  env: process.env,
  encoding: 'utf8',
})

if (packResult.status !== 0) {
  process.stderr.write(packResult.stderr || '')
  process.exit(packResult.status ?? 1)
}

const packOutput = JSON.parse(packResult.stdout)
const packed = Array.isArray(packOutput) ? packOutput[0] : packOutput

if (!packed?.filename) {
  console.error('npm pack did not return a filename')
  process.exit(1)
}

if (packed.filename !== tarballName) {
  console.error(`Unexpected tarball filename: expected ${tarballName}, got ${packed.filename}`)
  process.exit(1)
}

const tarballBuffer = fs.readFileSync(tarballPath)
const sha256 = crypto.createHash('sha256').update(tarballBuffer).digest('hex')

process.stdout.write(
  `${JSON.stringify(
    {
      package_name: packageName,
      version,
      tarball_path: tarballPath,
      tarball_name: tarballName,
      tarball_sha256: sha256,
    },
    null,
    2,
  )}\n`,
)
