// Re-render the exact finalized PPTX for review and its static PDF companion.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const modules=process.env.ARTIFACT_NODE_MODULES || path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {PresentationFile,FileBlob}=await import(pathToFileURL(path.join(modules,'@oai/artifact-tool/dist/artifact_tool.mjs')));
const deck=await PresentationFile.importPptx(await FileBlob.load(path.join(root,'deliverables/presentation/project_presentation.pptx')));
const out=path.join(root,'docs/presentation/.build/final');
await fs.mkdir(out,{recursive:true});
for (const [i,slide] of deck.slides.items.entries()) {
 const png=await deck.export({slide,format:'png',scale:1});
 await fs.writeFile(path.join(out,`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await png.arrayBuffer()));
}
console.log(`Rendered ${deck.slides.items.length} finalized slides`);
