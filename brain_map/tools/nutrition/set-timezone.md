---
type: Tool
title: set_timezone
description: Set the user's IANA timezone (e.g. 'America/Los_Angeles', 'Europe/Berlin',
  'Asia/Tokyo'). It decides which calendar day meals, water, weight and body measurements
  are grouped into when they are read — a meal logged at 11pm in LA counts on t
id: nutrition__set_timezone
server: nutrition
kind: mcp
short: set_timezone
capabilities: [weight.goals]
modules: [weight]
side_effect: read
requires_confirmation: false
status: online
params: [timezone]
tags: [tool, nutrition]
timestamp: '2026-10-04T21:08:27+02:00'
---

# set_timezone

Set the user's IANA timezone (e.g. 'America/Los_Angeles', 'Europe/Berlin', 'Asia/Tokyo'). It decides which calendar day meals, water, weight and body measurements are grouped into when they are read — a meal logged at 11pm in LA counts on that LA day, not the next UTC day — and how a logged_at with no UTC offset is turned into an exact moment when it is written. That second part is permanent: an entry keeps the moment it was resolved to, so correcting the timezone later regroups existing entries under the new zone's days but does not re-read their original local times (a meal entered as 21:00 while the account was on UTC shows as 00:00 the next day once Europe/Kyiv is set in summer). Until one is set, the account uses UTC.

Server: [nutrition](../../servers/nutrition.md)

## Capabilities
- [Weight and nutrition goals](../../capabilities/weight.goals.md) (`weight.goals`)

## Parameters
| name | type | required | description |
|---|---|---|---|
| `timezone` | string | yes | IANA timezone identifier (e.g. 'America/New_York'). Must be a valid tzdata name. |
