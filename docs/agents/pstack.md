# pstack in this repository

The Pi wrappers are `.pi/skills/pstack/SKILL.md` and
`.pi/skills/unslop/SKILL.md`. They load Cursor's upstream skill sources without
installing the Cursor plugin runtime or changing global Pi configuration.

## Source and installation

Upstream is [cursor/plugins](https://github.com/cursor/plugins/tree/main/pstack),
licensed under MIT. The pinned revision is
`9bd4a8289f1c3fe870d518051772762a78b66ea0`, the same revision found in the local
`ds-agent` setup during this revision.

```bash
bash scripts/install-pstack.sh
```

The installer checks out only `pstack/` under the ignored
`reference/cursor-plugins/` directory. It does not run upstream hooks or install
packages. It refuses an unexpected remote or modified source checkout.
The upstream license remains at `reference/cursor-plugins/pstack/LICENSE`.

Start a new trusted Pi project session to discover the wrappers, then use:

```text
/skill:pstack explain the digit-score circuit
/skill:pstack unslop docs/HOW_IT_WORKS.md
/skill:unslop docs/VIDEO_WALKTHROUGH.md
```

A Pi session can also read either local `SKILL.md` directly. Do not invoke the
system `/usr/bin/pstack` command. That is a debugger tool, not this skill stack.

## Local rules

All roles use the current model. No Cursor model slugs or global
`~/.cursor/rules/pstack-models.mdc` file are configured.
The wrappers do not provide subagent, browser-control, or MCP tools.
An agent must use the tools actually present and report unavailable steps.

The upstream setup skill configures Cursor models, so it is not run in this
Pi project. Existing caveman and Matt Pocock instructions still apply.
An upstream playbook does not grant permission to commit, publish, retrain,
or overwrite user work.

Use `unslop` for this repo's prose. Keep mathematical notation and real source
names. The main explanation should work for a technical YouTube audience
without requiring a detailed account of every gate.
