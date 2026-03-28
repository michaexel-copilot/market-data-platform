## Context

The management console (`console.py`) contains a "Best SMA Exit V1" section that was implemented but never formally specced. It includes:
- Two action-bar controls: `INP_BEST_SMA_POS_USD` (number input) and `BTN_COMPUTE_BEST_SMA_V2` (button)
- A `best-sma-v2-section` div rendered inside `PANE_FUNDAMENTALS`
- A parallel API fetch to `/v1/strategies/best-sma-exit-v1`
- A click event handler and a `_refreshBestSmaV2Section` helper function

The management-console spec already defines the action bar with exactly two elements and `PANE_FUNDAMENTALS` with exactly two additional sections — neither includes Best SMA. This code is dead UI that should be removed to align the implementation with the spec.

## Goals / Non-Goals

**Goals:**
- Remove all Best SMA Exit V1 UI from the management console
- Make the implementation match the existing management-console spec exactly
- Update the management-console spec to explicitly prohibit these elements, ensuring they cannot re-appear unintentionally

**Non-Goals:**
- Removing the underlying strategy Python files (`best_sma_exit_v1.py`, `best_sma.py`) — they are server-side modules unrelated to this UI cleanup
- Modifying the API endpoint that served the Best SMA data
- Any schema or data changes

## Decisions

**Decision: Remove all Best SMA code in one pass, not incrementally**
Rather than simply commenting out or feature-flagging, delete the dead code entirely. There is no reason to preserve it — the spec does not include it and it was never shipped as a documented feature.

**Decision: Update the management-console spec with explicit prohibitions**
The current spec does not mention Best SMA, which means it was never required. To avoid ambiguity and prevent re-introduction, update the spec to explicitly state these elements SHALL NOT be present. This converts an implicit omission into an active constraint.

## Risks / Trade-offs

[Risk: The parallel fetch in `loadFundamentals` currently awaits 4 promises including `bestSmaRes`] → Mitigation: Reduce the destructuring to 3 promises (`fundRes`, `availRes`, `matrixRes`) after removing the Best SMA call. Ensure no other code consumes `bestSmaRes`.

[Risk: JS variable declarations for `inpBestSmaPosUsd` and `btnBestSmaV2` are used in `setControlsEnabled`] → Mitigation: Remove both declarations and all references in `setControlsEnabled` together in a single pass.
