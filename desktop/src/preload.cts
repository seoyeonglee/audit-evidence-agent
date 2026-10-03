import { contextBridge, ipcRenderer } from "electron";
contextBridge.exposeInMainWorld(
  "auditDesktop",
  Object.freeze({
    runtimeStatus: () => ipcRenderer.invoke("audit:status"),
    apiRequest: (input: unknown) => ipcRenderer.invoke("audit:api", input),
    selectEvidence: () => ipcRenderer.invoke("audit:select"),
    saveReport: (runId: string) => ipcRenderer.invoke("audit:save", runId),
  }),
);
