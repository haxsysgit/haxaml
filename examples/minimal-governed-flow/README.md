# Minimal Governed Flow Example

This folder is a tiny governed-flow walkthrough for local testing and onboarding.

## What It Includes

- A minimal command sequence you can run in a scratch repo.
- The current governed lifecycle order.
- A concrete `HAXAML_PROJECT_DIR` example for MCP-only experiments.

## Try It

Bootstrap a temporary FRAME scaffold first:

```bash
haxaml init examples/minimal-governed-flow
haxaml validate --dir examples/minimal-governed-flow
haxaml context-pack --dir examples/minimal-governed-flow --task "implement receipt printer support" --pack balanced
```

If you run MCP tools directly, set project path:

```bash
export HAXAML_PROJECT_DIR="$(pwd)/examples/minimal-governed-flow"
```

Then run governed flow in order:

1. `haxaml_about`
2. `haxaml_guidance`
3. `haxaml_prebuild`
4. `haxaml_context_pack`
5. `haxaml_context_fetch` as needed
6. `haxaml_session_verify`
7. `haxaml_session_record`
8. `haxaml_expect_sync`
