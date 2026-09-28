---
name: Book a restaurant table
description: Reserve a table in a restaurant for a given day, time and number of people
uses: [memory.recall, research.web, bookings.browse, bookings.confirm, calendar.write, memory.remember, tasks.manage]
---
1. Collect: restaurant (or cuisine + area), day, time, number of people. Ask one short question for anything missing.
2. Look up memory (memory_search "restaurant") for preferences and favourite places.
3. Find the restaurant's online booking page (web_search), open it in the browser, check availability.
4. If the exact slot is taken, offer the two nearest slots.
5. Call confirm_action with the full summary. Only after "approved" press the final booking button.
6. Add the reservation to the calendar (it will be confirmed too) and remember the place with memory_remember.
7. If a confirmation is expected later (SMS/email), create a task "Check the booking confirmation" due in 2 hours.
