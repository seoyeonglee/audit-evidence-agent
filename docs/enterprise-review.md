# Independent enterprise branch review

A fresh independent reviewer inspected base e2580b8 through e3a62f6, the approved spec/plan and the task rulings. It independently ran enterprise (28 pass, 2 PostgreSQL skips) and desktop unit (4 pass) tests and reproduced key failure cases. No Critical findings or deferred Minors were reported.

Five Important findings were addressed in one native fix pass:

| Finding | Correction | Regression evidence |
|---|---|---|
| Existing session fails after sidecar token rotation | Retry obtains the chosen persona again, reloads reads and preserves the run; HTTP status survives trusted transport | Real Electron kills its owned Python process through a fixture-owned interpreter wrapper, sees failure, retries and completes the same run |
| Native file errors expose absolute paths | File read, selected report write and dialog errors become bounded path-free messages | Missing selected file and unwritable export assertions in unit and actual Electron flows |
| Unicode/JSON escape expansion rejects valid evidence | Code-point count matches backend; byte cap remains independent; transport envelope accommodates escaped valid text | Supplementary Unicode filename/content and 110,000 newlines accepted; raw-byte and oversize cases remain denied |
| Quoted CSV loses source syntax/physical lines | CSV values retain exact original record spans and physical starting lines | Quoted scalar, comma, escaped quote and multiline CSV all pass strict graph grounding |
| Completed report disappears after navigating away | Selecting a request loads its latest persisted run and restores its report pointer | Browser completes A, creates B, reopens/exports A and reloads A |

Tests were observed failing before fixes and passing afterward. Corpus/parser validation was rerun because CSV provenance changed. A second reviewer was not substituted for regression evidence.

Review boundaries retained: Windows/macOS runtime, signing, bundled Python and OS sandbox enforcement remain unverified; graph reasoning remains offline heuristic; checkpoint execution remains one host. Actual PostgreSQL and remote CI results are a separate gate. These boundaries are stated in the verification manifest and startup/recovery runbooks.
