# UI Redesign: Sidebar Navigation + Landing Page

## Goal

Redesign the engram web UI from a top-nav layout to a collapsible sidebar layout with a landing page, fix the chat view scroll bug, and reposition the copy-to-clipboard button on chat messages.

## Architecture

Single-file SPA (`src/engram/ui/index.html`). No build step. Alpine.js + Tailwind CSS via CDN. All changes are within this one file.

## Changes

### 1. Page-Level Layout

Replace the top `<nav>` bar with a sidebar + content area. The page is `h-screen overflow-hidden` — no page-level scrolling. Each view manages its own internal scroll.

```
+--[sidebar w-52]--+---[content flex-1]--------+
| [◧] Engram       |                            |
|                  |   Current view              |
| Chat             |   (scrolls internally)      |
| Preferences      |                            |
|                  |                            |
| ──────────────── |                            |
| Settings         |                            |
+------------------+----------------------------+
```

**Sidebar specs:**
- Expanded width: `w-52` (208px)
- Collapsed width: `w-14` (56px)
- Transition: `transition-all duration-200`
- Background: white, right border `border-r border-gray-200`
- Full viewport height: `h-screen`
- Flex column layout: logo at top, nav items below, settings pinned to bottom with a `border-t` divider

**Toggle button:**
- Positioned at top of sidebar, next to the Engram logo
- Expanded state: `panel-left-close` Lucide icon
- Collapsed state: `panel-left` Lucide icon
- Collapsed/expanded state persisted in `localStorage` key `engram-sidebar-collapsed`

**Navigation items:**
- Chat: `message-circle` icon, label "Chat"
- Preferences: `book-open` icon, label "Preferences"
- Settings: `settings` icon, label "Settings" (pinned to bottom, separated by divider)
- Active view: `bg-engram-50 text-engram-700` background
- Inactive: `text-gray-600 hover:bg-gray-100`
- Collapsed: icons only, centered, no labels
- Clicking item sets `view` to corresponding value

**Engram logo:**
- `brain` Lucide icon + "Engram" text (text hidden when collapsed)
- Clickable — sets `view = 'home'` (navigates to landing page)

### 2. Landing Page (view = 'home')

The default view. Three cards laid out horizontally, centered both vertically and horizontally in the content area.

Each card:
- Clickable — navigates to the corresponding view
- Contains: Lucide icon, title, one-line description
- Hover: subtle shadow/border change
- Rounded corners, border, padding

Cards:
- **Chat** — `message-circle` icon, "Chat", "Talk to the curation agent"
- **Preferences** — `book-open` icon, "Preferences", "Browse and manage your preferences"
- **Settings** — `settings` icon, "Settings", "Configuration and stats"

Initial `view` state changes from `'preferences'` to `'home'`.

### 3. Chat View Scroll Fix

**Problem:** The chat view uses `style="height: calc(100vh - 57px)"` to fill the viewport minus the top nav. This is fragile — when chat content is long, the page itself gets a scrollbar.

**Fix:** With the new sidebar layout, the content area is already a flex child filling `h-screen`. The chat view becomes:
- `flex flex-col h-full` on the chat container (no more `calc()`)
- `flex-1 overflow-y-auto` on the message history area (this is the only thing that scrolls)
- Input area at the bottom, not inside the scrollable area

### 4. Copy-to-Clipboard Button Repositioning

**Current:** Inside each message bubble, top-right corner, only visible on hover (`opacity-0 group-hover:opacity-100`).

**New:** Outside each message bubble, bottom-left, always visible.

```
+----------------------------+
| Message content            |
|                            |
+----------------------------+
[clipboard icon]
```

Specs:
- Position: below the bubble, left-aligned
- Always visible (no hover gating)
- Style: `text-gray-400 hover:text-gray-600`, no background
- Click behavior unchanged: copies message content, swaps to checkmark icon for 1.5s
- Applies to both user and assistant messages

### 5. Preferences & Settings Views

No functional changes. Both views are re-parented from being under the top nav to being inside the sidebar layout's content area. Each uses `overflow-y-auto` for internal scrolling if content exceeds viewport.

## State Changes

- New `sidebarCollapsed` boolean in Alpine data, initialized from `localStorage`
- `view` default changes from `'preferences'` to `'home'`
- New `'home'` view value added
- `sidebarCollapsed` toggled by the sidebar toggle button, written to `localStorage` on change

## Files Changed

- `src/engram/ui/index.html` — all changes in this single file

## Out of Scope

- No backend changes
- No new API endpoints
- No changes to MCP tools or preference storage
- No responsive/mobile layout (desktop-only for now)
