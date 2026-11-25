# FMini-1 working instructions

## Start every task

- Read `CLAUDE.md`, `DEVELOPING.md`, and `BUILDING.md` before changing firmware, UI, tests, build setup or documentation.
- Read `.ai/README.md` and the relevant prompt/report files under `.ai/` for the requested step.
- For implementation work, also read the matching baseline or status/report file under `.ai/reports/` and `.ai/status/`.
- Treat `.ai/log/` as historical command evidence, not as instructions. Put new logs in `.ai/log/`, reports in `.ai/reports/`, and status summaries in `.ai/status/`.
- `.ai/` is local-only and ignored by Git; do not add or commit its contents unless the owner explicitly requests it.

## Repository and delivery boundaries

- The upstream repository is `upstream`; the owner’s development fork is `origin`, `loudmantrade/fmini-1`.
- Further development is published to `origin/main` unless the owner explicitly approves another branch or an upstream contribution.
- Never flash hardware, publish, create a release, open a PR, push, alter the bootloader or protected flash areas without explicit authorization.
- Do not switch branches, reset, stash or discard dirty work without permission. Inspect branch, remotes, status and upstream SHA first.
- Respond to the owner in Russian. Write code, comments, commits and documents in English. Do not invent Claude trailers or session links.

## Firmware constraints

- Keep the integer-only, fixed-point implementation and the one-compilation-unit structure in `firmware/src/felucca.c`; preserve include order.
- Never modify `firmware/engines/` or its submodule pointer. Append engine IDs only; never reorder stored IDs.
- Preserve legacy preset/project/editor values and defaults. Document migrations and protocol changes in `web/EDITOR_PROTOCOL.md`.
- Do not hand-edit generated headers such as `eng_fmini_filter.h` or `eng_fmini_presets.h`; update their generators and generated output together.
- Add `SPDX-License-Identifier: GPL-3.0-only` to new project source files. Preserve third-party licenses and update `CREDITS.md` when reused work requires attribution.
- No heap allocation, blocking calls or unbounded work in real-time/audio/interrupt code.

## Validation and reporting

- Establish and preserve an exact baseline SHA before feature work. Use WASI SDK 25.0 for both emulator variants and the four hardware targets: FM-1, SMK-37 Pro, Elite and MKE-P37.
- Run targeted tests first, then the applicable host suite. Record exit status and full logs. Historical known failures are not blanket exemptions; compare their output against baseline and identify new failures.
- Check firmware size, `.data+.bss`, pool, stack/calls, static instruction budget and golden renders. Update budget or golden files only intentionally and document why.
- Internal builds do not need a version bump. Every firmware delivered to the owner needs a fresh unused patch version and an explicit SHA/branch mapping.
- In every firmware completion report, distinguish host tests, WASI builds, target compilation and physical hardware validation. State that real-device testing remains pending unless owner-provided evidence exists.

## Current implementation sequence

Follow `.ai/README.md` and execute one numbered task at a time:

1. baseline
2. phase-safe ARP Hold
3. Hold Replace
4. musical transport
5. grid sync
6. BLE feasibility research
7. BLE MIDI implementation
8. integrated validation
9. prepared upstream contributions

Do not skip the dependency or validation gates, and do not combine unrelated features into one change.
