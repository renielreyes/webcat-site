# results/ — the results contract

Every executor run writes exactly one result file here as its **final step**. This folder is the
append-only history of the AI Brain loop (and a future AI-services case study), so it is kept
publishable-clean: no secrets, no client names until approved.

## File naming

One JSON file per run:

```
results/<task-id>.<run-id>.json
```

Example: `results/wiring.r1.json`

## Fields

Each result file is a single JSON object with these fields:

| Field | Meaning |
|---|---|
| `task` | The task id (matches the task the run acted on). |
| `runId` | The run id for this execution. |
| `status` | One of `"success"`, `"failed"`, or `"blocked"`. |
| `summary` | Plain-English summary, **max 5 lines**. |
| `branch` | The branch the work was committed to. |
| `pr` | The pull request URL, or `null` if none was opened. |
| `filesChanged` | List of files created or edited by the run. |
| `model` | The model that executed the run. |
| `started` | When the run started (ISO 8601). |
| `finished` | When the run finished (ISO 8601). |
| `notes` | Anything a human should know — blockers, risks, follow-ups. |

## The append-only rule

- **Never edit or delete a previous result file.** History is immutable.
- Each run adds its own new file. If a run reruns, it uses a new `<run-id>`.
- The result file is written as the **last** step of a run.
