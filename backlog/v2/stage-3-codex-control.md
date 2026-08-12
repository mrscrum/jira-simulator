# V2 Stage 3 — Private Codex Control and First Alpha

> **DETAILED REFERENCE DRAFT — NOT ACTIVE.** See [`README.md`](README.md) for milestone status.
Status: NOT STARTED

## Tasks
- [ ] V2-S3-T01 — Implement the non-provisioning team preview service
- [ ] V2-S3-T02 — Implement idempotent provisioning operation
- [ ] V2-S3-T03 — Add private scoped API and dashboard authentication
- [ ] V2-S3-T04 — Establish minimum trusted TLS and isolate legacy public helpers
- [ ] V2-S3-T05 — Scaffold the private Codex skill, plugin, and thin MCP server
- [ ] V2-S3-T06 — Implement basic MCP read tools
- [ ] V2-S3-T07 — Implement MCP preview and confirmed creation
- [ ] V2-S3-T08 — Implement MCP start, pause, and resume controls
- [ ] V2-S3-T09 — Implement MCP Jira sync controls
- [ ] V2-S3-T10 — Implement versioned team-settings control
- [ ] V2-S3-T11 — Implement work-item controls
- [ ] V2-S3-T12 — Implement member-availability control
- [ ] V2-S3-T13 — Prove prompt-to-running-team Codex alpha

## UAT Results
(pending Gate G3 evidence and Pavel's review)

## Notes
- Gate G3 is the first usable alpha: basic statistical Scrum plus Codex control.
- Codex handles conversation; the service OpenAI key is not a plugin chat backend.
- T01/T02 build unmounted application services. T03 establishes bearer/session authentication;
  authenticated read and preview/create routes are mounted only in T06/T07.
