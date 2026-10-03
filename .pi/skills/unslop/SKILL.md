---
name: unslop
description: Remove AI writing patterns from htmlnet docs and video notes. Use whenever drafting or revising prose in this repository, or when the user asks to unslop text.
---

# Unslop htmlnet writing

Read `../../../reference/cursor-plugins/pstack/skills/unslop/SKILL.md`, resolved
relative to this directory, and follow its scan, rewrite, and self-audit steps.
If the source is missing, run `bash ../../../scripts/install-pstack.sh` from
this directory. Read `../../../docs/agents/pstack.md` for the pinned revision.

For documentation, also read upstream `skills/technical-writing/SKILL.md`.
The audience is a relatively technical YouTube viewer. Explain intuition
before optional circuit details. Use complete sentences in the docs.

Keep mathematically literal terms such as vector, matrix, and primitive gate
when needed. Do not remove equations or identifiers as supposed jargon.
Do remove unsupported claims, invented precision, filler, and generic AI prose.
Do not turn a technical guide into a script impersonating the author.

The distinctions in `../../../docs/COMPUTATION_MODEL.md` must survive editing.
HTML supplies form state. CSS computes inference. The optional script handles
pointer geometry. Rust trains models and generates the artifact before runtime.
