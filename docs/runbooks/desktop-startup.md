# Desktop startup and developer packaging

From the repository root:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
npm --prefix desktop ci
npm --prefix desktop run dev
```

Use `AUDIT_PYTHON` to select an absolute interpreter path if Electron cannot find the prepared Python environment. `AUDIT_USER_DATA` is a trusted developer/testing override; never accept it from renderer input. Default data lives under Electron userData.

To produce a developer artifact, build the frontend first, then run `npm --prefix desktop run package`. The Linux bundle is under `desktop/artifacts/AuditEvidence-linux-x64`. Its backend Python dependencies remain a prerequisite. Other platform builds have not been runtime-tested.

A visible startup error usually means a missing interpreter/dependency or unavailable private data directory. Correct the trusted environment and choose Retry connection. The sidecar starts on demand; repeated API calls reuse the same startup promise. If it exits, the next request starts a new owned process and reopens local storage.

Run desktop tests on Linux with `xvfb-run -a npm --prefix desktop run test:e2e`. Dialog automation selects a fixture path in main; the real file reader, API, SQL service and graph still run. Root-only environments require the test's --no-sandbox launch flag. Secure BrowserWindow settings remain enabled, but root captures do not verify the OS sandbox.
