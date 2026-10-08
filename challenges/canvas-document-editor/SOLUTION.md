# SOLUTION — canvas-document-editor

## Reference approach and limits

The stored document is the source of truth; rendering is a projection. Convert pointer deltas once, preserve identity, and coalesce previews into one committed history entry. Load validation must finish before replacement. Full snapshots make history simple but cost O(actions × document size); rendering and shape updates scan O(n). State probes do not certify usable dragging: the rendered suite and reviewer interaction are separate evidence.

Reviewed implementations are in backend/tests/ranked_reference_fixtures.py and remain interviewer/test-only.

## Initial incident

`src/designStore.ts` contains the faulty change `(x-drag.x),dy=(y-drag.y)`. Repair the contract rather than changing expectations.

The candidate also implements validated load before state replacement.

## Independent evidence

Eight server-owned observation probes cover this family; expected values never enter the candidate command. Two plausible wrong repairs are checked separately. Rendered frontend behavior retains explicit reviewer requirements even when the visible suite passes.

## Rubric (100)

Correct behavior and preservation: 35; model and explanation: 25; independent verification: 20; AI-output review and trade-offs: 20. This guide does not replace the platform rubric.

## Parts and reviewer evidence

The document owns identity and coordinates; pointer previews are distinct from committed history.

- Part 1 (Repair movement): zoom-drag, only-selection, duplicate-reject.
- Part 2 (Load and edit a document): round-trip, invalid-preserves, delete-selection, style-isolated, drag-history.
- Part 3 (Pressure-test the model): branch-clears-redo.

Part 3 checks this contract property: A new committed edit after undo must discard the abandoned redo branch. A behavioral pass observes these cases; it does not certify the candidate’s explanation. Existing declared manual review gaps remain.

Plausible wrong assumption to challenge: Redo history remains valid after undo followed by a new committed edit. Ask for a concrete counterexample; the selected automated wrong-repair fixtures remain the declared regression evidence.

Optional changed requirement: Add multi-selection and group dragging. Define one group history action, selection persistence and deletion rules; show how a single selected-id model must change. This is discussion-only and must not silently become a baseline coding requirement.

## Defend-Your-Code (4)
1. Q: Why divide movement by zoom? A: Pointer deltas are screen units; document coordinates must be independent of display scale.
2. Q: What is one undo action? A: A completed drag, not each preview event; retain the pre-drag snapshot until release.
3. Q: What happens when a saved shape is invalid? A: Validation fails before replacing the current document, selection or history.
4. Q: Why are state probes insufficient? A: Rendering, hit targets and release outside the surface need interaction evidence; a correct store can still have a broken editor.
