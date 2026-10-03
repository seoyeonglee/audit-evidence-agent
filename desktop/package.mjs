import { packager } from "@electron/packager";
import { cp, mkdir } from "node:fs/promises";
import { resolve, join } from "node:path";
const root = resolve(".."),
  runtime = resolve("artifacts/runtime");
await mkdir(runtime, { recursive: true });
for (const path of ["src", "data", "requirements.txt"])
  await cp(join(root, path), join(runtime, path), {
    recursive: true,
    filter: (p) => !p.includes("__pycache__"),
  });
await cp(join(root, "frontend/dist"), join(runtime, "frontend/dist"), {
  recursive: true,
});
const paths = await packager({
  dir: ".",
  name: "AuditEvidence",
  out: "artifacts",
  overwrite: true,
  extraResource: [runtime],
  ignore: /^\/(tests|test-results|playwright-report|artifacts|src)/,
});
console.log(
  "Developer artifact (requires Python dependencies):",
  paths.join("\n"),
);
