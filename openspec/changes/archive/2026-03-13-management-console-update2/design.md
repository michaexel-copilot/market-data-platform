## Context

The instrument list can contain thousands of entries after a CMC migration. Operators need to locate a specific instrument quickly without scrolling.

## Goals / Non-Goals

**Goals:**
- Add a text filter input above the instrument list that narrows the displayed rows live as the user types

**Non-Goals:**
- Server-side search (the full list is already loaded in memory)
- Filtering by fields other than ticker and full_name
