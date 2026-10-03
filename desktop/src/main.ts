import {
  app,
  BrowserWindow,
  ipcMain,
  dialog,
  protocol,
  net,
  session,
} from "electron";
import { dirname, join, resolve, sep } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { validateSender, validateApiRequest } from "./security.js";
import { readSelectedEvidence, writeSelectedReport } from "./files.js";
import { proxyApi, ApiProxyError } from "./proxy.js";
import { startSidecar, type SidecarHandle } from "./sidecar.js";
const here = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = app.isPackaged
  ? join(process.resourcesPath, "runtime")
  : resolve(here, "../..");
const origin = "app://audit/index.html";
if (process.env.AUDIT_USER_DATA)
  app.setPath("userData", resolve(process.env.AUDIT_USER_DATA));
protocol.registerSchemesAsPrivileged([
  {
    scheme: "app",
    privileges: { standard: true, secure: true, supportFetchAPI: true },
  },
]);
let sidecar: SidecarHandle | undefined;
let boot: Promise<SidecarHandle> | undefined;
let token: string | undefined;
let quitting = false;
async function readySidecar() {
  if (sidecar?.isAlive()) return sidecar;
  if (!boot) {
    boot = startSidecar({
      python:
        process.env.AUDIT_PYTHON ??
        (process.platform === "win32" ? "python" : "python3"),
      repositoryRoot,
      userData: app.getPath("userData"),
      startupTimeout: 15000,
    })
      .then((h) => {
        sidecar = h;
        return h;
      })
      .finally(() => {
        boot = undefined;
      });
  }
  return boot;
}
app.whenReady().then(async () => {
  const assets = resolve(repositoryRoot, "frontend/dist");
  protocol.handle("app", async (request) => {
    const url = new URL(request.url);
    let relative: string;
    try {
      relative = decodeURIComponent(url.pathname);
    } catch {
      return new Response("Invalid path", { status: 400 });
    }
    const target = resolve(assets, "." + relative);
    if (url.host !== "audit" || !target.startsWith(assets + sep))
      return new Response("Not found", { status: 404 });
    const response = await net.fetch(pathToFileURL(target).toString());
    const headers = new Headers(response.headers);
    headers.set(
      "Content-Security-Policy",
      "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'",
    );
    return new Response(response.body, { status: response.status, headers });
  });
  session.defaultSession.setPermissionRequestHandler(
    (_wc, _permission, callback) => callback(false),
  );
  const window = new BrowserWindow({
    width: 1512,
    height: 1120,
    backgroundColor: "#090d13",
    title: "Audit Evidence · Enterprise Agent",
    webPreferences: {
      preload: join(here, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  });
  window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  window.webContents.on("will-navigate", (event, url) => {
    if (url !== origin) event.preventDefault();
  });
  const guard = (event: Electron.IpcMainInvokeEvent) => {
    if (event.sender !== window.webContents)
      throw new Error("Unknown IPC window");
    validateSender(event, origin);
  };
  ipcMain.handle("audit:status", (event) => {
    guard(event);
    return {
      status: sidecar?.isAlive() ? "ready" : boot ? "starting" : "not_started",
      profile: "local-synthetic-offline",
    };
  });
  ipcMain.handle("audit:api", async (event, input) => {
    guard(event);
    const r = validateApiRequest(input);
    const h = await readySidecar();
    try {
      const data = await proxyApi(r, h.baseURL, h.secret);
      if (r.bearerToken) token = r.bearerToken;
      return data;
    } catch (error) {
      if (error instanceof ApiProxyError)
        return {
          $auditError: { status: error.status, message: error.message },
        };
      throw error;
    }
  });
  ipcMain.handle("audit:select", async (event) => {
    guard(event);
    let result;
    try {
      result = await dialog.showOpenDialog(window, {
        properties: ["openFile"],
        filters: [
          { name: "Evidence text", extensions: ["txt", "csv", "json"] },
        ],
      });
    } catch {
      throw new Error("Evidence selection could not finish. Try again.");
    }
    return result.canceled
      ? { cancelled: true }
      : readSelectedEvidence(result.filePaths[0]);
  });
  ipcMain.handle("audit:save", async (event, runId: unknown) => {
    guard(event);
    if (typeof runId !== "string" || !/^[a-zA-Z0-9_-]{1,80}$/.test(runId))
      throw new Error("Invalid run");
    const h = await readySidecar();
    const data = await proxyApi(
      {
        method: "GET",
        path: `/api/v2/agent-runs/${runId}/report`,
        bearerToken: token,
      },
      h.baseURL,
      h.secret,
    );
    let selected;
    try {
      selected = await dialog.showSaveDialog(window, {
        defaultPath: `audit-${runId}.json`,
        filters: [{ name: "JSON report", extensions: ["json"] }],
      });
    } catch {
      throw new Error("Report destination could not be selected. Try again.");
    }
    if (selected.canceled || !selected.filePath) return { saved: false };
    await writeSelectedReport(selected.filePath, JSON.stringify(data, null, 2));
    return { saved: true };
  });
  await window.loadURL(origin);
});
app.on("window-all-closed", () => app.quit());
app.on("before-quit", (event) => {
  if (quitting) return;
  event.preventDefault();
  quitting = true;
  (async () => {
    if (boot) {
      try {
        await boot;
      } catch {}
    }
    await sidecar?.stop();
    app.quit();
  })();
});
