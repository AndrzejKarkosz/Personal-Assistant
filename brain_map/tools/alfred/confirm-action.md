---
type: Tool
title: confirm_action
description: Ask the user for a spoken yes/no before an irreversible step that has
  no dedicated tool (e.g. pressing the final 'Book' button in a browser). Returns
  approved or declined.
id: confirm_action
server: alfred
kind: builtin
short: confirm_action
capabilities: [bookings.confirm]
modules: [bookings]
side_effect: guard
requires_confirmation: false
status: online
params: [summary]
tags: [tool, alfred]
timestamp: '2026-09-25T14:22:57+02:00'
---

# confirm_action

Ask the user for a spoken yes/no before an irreversible step that has no dedicated tool (e.g. pressing the final 'Book' button in a browser). Returns approved or declined.

Server: [alfred](../../servers/alfred.md)

## Capabilities
- [Ask the user before an irreversible step](../../capabilities/bookings.confirm.md) (`bookings.confirm`)

## Parameters
| name | type | required | description |

|---|---|---|---|
| `summary` | string | yes | One sentence: exactly what will happen |
