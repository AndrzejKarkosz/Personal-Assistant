---
type: Tool
title: manage-accounts
description: 'Manage Google account authentication. Actions: ''list'' (show accounts),
  ''add'' (authenticate new account), ''remove'' (remove account).'
id: google-calendar__manage-accounts
server: google-calendar
kind: mcp
short: manage-accounts
capabilities: []
modules: []
side_effect: destructive
requires_confirmation: true
status: online
params: [action, account_id]
tags: [tool, google-calendar]
timestamp: '2026-09-30T13:14:24+02:00'
---

# manage-accounts

Manage Google account authentication. Actions: 'list' (show accounts), 'add' (authenticate new account), 'remove' (remove account).

Server: [google-calendar](../../servers/google-calendar.md)

## Capabilities
- not assigned to any capability yet - add a pattern to a module's capabilities

## Parameters
| name | type | required | description |
|---|---|---|---|
| `action` | string | yes | Action to perform: 'list' shows all accounts, 'add' authenticates a new account, 'remove' removes an account |
| `account_id` | string |  | Account nickname (e.g., 'work', 'personal') - a friendly name to identify this Google account. Required for 'add' and 'remove'. Optional for 'list' (shows all i |
