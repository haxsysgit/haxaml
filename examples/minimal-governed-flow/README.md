# Minimal Governed Flow Example

This folder is a tiny FRAME project for local testing and onboarding.

## What It Includes

- Valid `.haxaml/facts.yaml`
- Valid `.haxaml/rules.yaml`
- Valid `.haxaml/acts.yaml`
- Valid `.haxaml/expect.yaml`

## Try It

From repository root:

```bash
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
3. `haxaml_session_start`
4. `haxaml_session_plan`
5. `haxaml_context_pack`
6. `haxaml_session_verify`
7. `haxaml_session_record`
