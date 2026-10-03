# ADR 008 — Main owns local files and loopback transport

Accepted for the developer desktop app.

The packaged React renderer has no Node integration. Electron enables context isolation, sandbox configuration and web security. Main checks the sending window and exact main-frame URL. The preload exposes four named bounded functions: runtime status, allowlisted API request, selected evidence import and authorized report save.

The renderer cannot choose a local path or backend URL. Main opens native dialogs, validates a regular non-symlink UTF-8 txt/csv/json file through its opened descriptor, and returns only basename, media type and bounded content. Report export accepts a run ID, obtains the authorized completed report, then writes to a main-owned save-dialog destination.

Main starts an owned Python process on loopback with a random transport secret. The secret never enters renderer DTOs; API membership bearer authorization is independently required. Startup failures surface as recoverable UI errors; application shutdown terminates its sidecar.

Developer packaging includes the backend source, synthetic data and built web assets as a resource. Python and its requirements must already be installed. There is no signed installer, bundled interpreter or VM. Linux Electron execution is verified; Windows/macOS are untested. Root-run captures use --no-sandbox, so they prove real Electron/IPC behavior, not operating-system sandbox enforcement.
