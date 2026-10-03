---
name: pstack
description: Use the pinned Cursor pstack engineering playbooks for htmlnet through Pi. Invoke for investigation, code revision, or an implementation audit.
disable-model-invocation: true
---

# pstack for htmlnet

Resolve the repository root as `../../..` relative to this skill directory.
Upstream sources live at `../../../reference/cursor-plugins/pstack`.
If missing, run `bash ../../../scripts/install-pstack.sh` from this directory.
The installer downloads source files, not a Cursor plugin runtime.

For a named skill, such as `pstack unslop`, read its upstream
`skills/<name>/SKILL.md`. Otherwise read `skills/poteto-mode/SKILL.md` and the
matching playbook. Resolve upstream relative links against each upstream file.
Read `../../../docs/agents/pstack.md` for provenance and local configuration.

## Pi compatibility

- Upstream `/name` means read the corresponding upstream skill. It is not a
  registered Pi command unless a local wrapper exists.
- Use tools actually available in this session. Cursor Task, AskQuestion,
  plugin subagents, and control-ui are not supplied by these source files.
- All roles inherit the current model. Do not invent provider IDs, claim
  parallel reviews ran, or write Cursor's global model configuration.
- Upstream workflows do not authorize commits, pushes, publishing, model
  retraining, destructive cleanup, or additional tool installation.
- Keep the global caveman and Matt Pocock workflows. Read this repo's
  `docs/COMPUTATION_MODEL.md` and `docs/DECISIONS.md` before circuit changes.
- Preserve user changes. Edit generator sources and rebuild instead of
  patching generated `dist/index.html` alone. Do not change weights to make
  an inference test pass.
- Apply upstream `unslop` and `technical-writing` to documentation. Keep
  literal mathematical terms, equations, and source identifiers intact.
- Verify with `make test`. Report missing tools and skipped checks explicitly.
