# Diagram input schema

## Common fields

| Field | Type | Required | Rule |
|---|---|---:|---|
| `diagram_type` | string | yes | `architecture` or `flowchart` |
| `title` | string | yes | 1–80 characters |
| `subtitle` | string | no | 0–120 characters |
| `theme` | string | no | `chaoxing-blue`, `academic-blue`, `neutral` |

## Architecture

`layers` contains 1–12 objects. Each layer has `label`, optional `description`, and 1–30 `items`. A module may be a string or:

```json
{"name":"智能助教","description":"课程知识问答","status":"planned"}
```

`status`: `current`, `planned`, or `external`. Optional `columns` is 1–6.

Architecture layer keys are exactly `label` and `items`; module object keys are exactly `name`, optional `description`, and optional `status`. Do not use `name/modules`, `label/modules`, or module-level `label`.

## Flowchart

| Field | Type | Required | Rule |
|---|---|---:|---|
| `direction` | string | no | `top-down` or `left-right` |
| `nodes` | array | yes | 2–60 nodes |
| `edges` | array | yes | 1–120 edges |

Node:

```json
{"id":"review","label":"院系审核","description":"审核课程内容与规范","shape":"decision","status":"current"}
```

- `id`: 1–40 characters, `[A-Za-z0-9_-]`, unique.
- `label`: 1–60 characters.
- `description`: optional, 0–120 characters.
- `shape`: `start`, `process`, `decision`, `end`; default `process`.
- `status`: `current` or `planned`.

Edge:

```json
{"from":"review","to":"publish","label":"通过"}
```

- `from` and `to` must reference existing IDs.
- `label` is optional, 0–30 characters.
- An edge pointing to an earlier node is treated as a return loop and routed outside the main columns.

For stable layout, list flow nodes in the intended main-flow order. Branch nodes may follow their decision node. Do not encode presentation coordinates.

