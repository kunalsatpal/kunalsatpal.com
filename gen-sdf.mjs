import { PartnerClient } from 'shaders/partner'
import fs from 'node:fs/promises'
const [inp, out] = process.argv.slice(2)
const c = new PartnerClient({ apiKey: 'none' })
const svg = await fs.readFile(inp, 'utf8')
const sdf = await c.generateSdf(svg)
await fs.writeFile(out, sdf)
console.log('wrote', out, sdf.byteLength)
