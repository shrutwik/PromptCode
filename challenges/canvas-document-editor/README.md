# Canvas editor

Build and repair the supplied React shape editor. Document version 1 stores ordered shapes (unique nonempty id; rect or ellipse; finite x,y; positive finite width,height; nonempty color) and selected id or null. Insertion selects the new shape. Pointer movement affects only the selected shape; divide screen deltas by positive zoom to obtain document deltas. A completed drag creates one undo record regardless of pointer move count; releasing outside the surface completes it. Color and deletion affect only selection; deletion clears selection. Undo/redo preserve exact document state; a new committed action clears redo. Save/load JSON preserves ids, coordinates, dimensions, colors, order and selection. Validate before replacing state; malformed documents and duplicate ids preserve the previous state. The React UI must render these operations and an invalid-load error. SVG is the supplied editable surface; adding a different rendering library is unnecessary.

## Verification

Run `npm test`. Start with the listed entry files and tests; starters intentionally contain a defect. A passing suite is evidence, not a substitute for explaining the invariant.

## Browser preview

Install the locked dependencies with `npm ci`, then run `npm run dev` and open the printed local address. The frozen `npm test` command remains the acceptance suite.

## Interview parts

Parts 1–3 organize the existing baseline contract; complete them in one ticket. The full suite remains the acceptance bar. Part 4 is discussion-only, has no extra coding requirement and does not affect the automated behavioral score.

Underlying invariant: The document owns identity and coordinates; pointer previews are distinct from committed history.

### Part 1 — Repair movement

Render and select shapes, convert screen movement through zoom and leave every unselected shape unchanged.

Evidence to show:

- Rendered selected-shape movement uses screen delta divided by zoom; unselected shapes stay fixed.

### Part 2 — Load and edit a document

Validate JSON before replacement; preserve styles, selection and dimensions through save/load, delete and completed-action history.

Evidence to show:

- Validated load preserves rejected state; save/load, deletion and one-entry completed-drag history agree with rendering.

### Part 3 — Pressure-test the model

Run the added fixture, then construct a second input exposing the same incorrect assumption. Explain the expected outcome before accepting a proposed AI repair.

Evidence to show:

- A new committed edit after undo must discard the abandoned redo branch.

### Part 4 — Changed requirement — optional discussion

Add multi-selection and group dragging. Define one group history action, selection persistence and deletion rules; show how a single selected-id model must change.

Evidence to show:

- Identify the changed invariant, affected code/data, and a minimal counterexample before proposing an implementation.

Keep supplied tests and runner files intact. Show observed verification and one AI suggestion you checked or rejected; use scratch files for additional experiments. Explanations require reviewer judgment; a passing behavioral run does not certify understanding.
