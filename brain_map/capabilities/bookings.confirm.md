---
type: Capability
title: Ask the user before an irreversible step
description: Spoken yes/no before submitting a booking, payment or form.
id: bookings.confirm
module: bookings
tools: [confirm_action]
tool_patterns: [confirm_action]
available: 1
confirm: false
always: true
examples: []
used_by: ['skill:bookings.restaurant-table', 'module:calendar']
tags: [capability, bookings]
timestamp: '2026-09-25T14:22:57+02:00'
---

# Ask the user before an irreversible step

Spoken yes/no before submitting a booking, payment or form.

Module: [bookings](../modules/bookings.md)

## Tools
- [confirm_action](../tools/alfred/confirm-action.md) - alfred, guard

## Used by
- skill:bookings.restaurant-table
- module:calendar
