import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { createServer } from "node:net";
import { join } from "node:path";
import { mkdir } from "node:fs/promises";
export interface TrustedSidecarConfig {
  python: string;
  repositoryRoot: string;
  userData: string;
  startupTimeout: number;
}
export interface SidecarHandle {
  baseURL: string;
  secret: string;
  stop(): Promise<void>;
  isAlive(): boolean;
}
async function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : 0;
      server.close(() => resolve(port));
    });
  });
}
export async function startSidecar(
  config: TrustedSidecarConfig,
): Promise<SidecarHandle> {
  await mkdir(config.userData, { recursive: true });
  const secret = randomBytes(32).toString("hex");
  const port = await freePort();
  const baseURL = `http://127.0.0.1:${port}`;
  const database = join(config.userData, "evidence.db").replaceAll("\\", "/");
  const child = spawn(
    config.python,
    ["-m", "src.enterprise.desktop_api", "--port", String(port)],
    {
      cwd: config.repositoryRoot,
      env: {
        ...process.env,
        DEMO_MODE: "1",
        DATABASE_URL: `sqlite:///${database}`,
        GRAPH_CHECKPOINT_DIR: join(config.userData, "checkpoints"),
        AUDIT_DESKTOP_SECRET: secret,
        PYTHONUNBUFFERED: "1",
      },
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
    },
  );
  let exited = false;
  child.on("error", () => {
    exited = true;
  });
  child.on("exit", () => {
    exited = true;
  });
  // Drain output without retaining potentially sensitive document text.
  child.stdout?.on("data", () => {});
  child.stderr?.on("data", () => {});
  const handle: SidecarHandle = {
    baseURL,
    secret,
    isAlive: () => !exited,
    async stop() {
      if (exited) return;
      child.kill("SIGTERM");
      await new Promise<void>((resolve) => {
        const timer = setTimeout(() => {
          if (!exited) child.kill("SIGKILL");
          resolve();
        }, 2500);
        child.once("exit", () => {
          clearTimeout(timer);
          resolve();
        });
      });
    },
  };
  const deadline = Date.now() + config.startupTimeout;
  while (Date.now() < deadline) {
    if (exited) {
      await handle.stop();
      throw new Error(
        "Local Python API could not start. Check the configured Python environment.",
      );
    }
    try {
      const r = await fetch(baseURL + "/desktop/health", {
        headers: { "X-Desktop-Secret": secret },
        signal: AbortSignal.timeout(600),
      });
      if (r.ok) return handle;
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  await handle.stop();
  throw new Error(
    "Local API startup timed out. Retry after checking Python dependencies.",
  );
}
