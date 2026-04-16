# UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the engram web UI with a collapsible sidebar, landing page, fixed chat scrolling, and repositioned copy buttons.

**Architecture:** Replace the top nav with a sidebar + content layout. The page is `h-screen overflow-hidden` — no page-level scroll. Each view fills the content area and scrolls internally. All changes in one HTML file.

**Tech Stack:** Alpine.js, Tailwind CSS (CDN), Lucide icons — all existing, no new dependencies.

---

## File Structure

Only one file is modified:

- **Modify:** `src/engram/ui/index.html` — the entire SPA

The file is currently ~434 lines. After the redesign it will be longer (landing page + sidebar markup), but it remains a single file following the existing pattern.

---

### Task 1: Replace top nav with sidebar layout shell

Replace the `<nav>` bar and overall page structure with a sidebar + content area. This task gets the skeleton in place — sidebar renders, toggle works, navigation switches views. Views themselves stay as-is (just re-parented).

**Files:**
- Modify: `src/engram/ui/index.html:38-57` (nav bar) and `body` tag

- [ ] **Step 1: Replace the `<body>` tag and `<nav>` element**

Replace the current body tag and nav (lines 38-57):

```html
<body class="bg-gray-50 text-gray-900 min-h-screen" x-data="engram()" x-init="init()">

    <!-- Navigation -->
    <nav class="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <div class="flex items-center gap-2">
            <i data-lucide="brain" class="w-6 h-6 text-engram-600"></i>
            <span class="font-semibold text-lg">Engram</span>
        </div>
        <div class="flex gap-1">
            <button @click="view = 'preferences'" :class="view === 'preferences' ? 'bg-engram-50 text-engram-700' : 'text-gray-500 hover:text-gray-700'" class="px-4 py-2 rounded-lg text-sm font-medium transition-colors">
                Preferences
            </button>
            <button @click="view = 'chat'" :class="view === 'chat' ? 'bg-engram-50 text-engram-700' : 'text-gray-500 hover:text-gray-700'" class="px-4 py-2 rounded-lg text-sm font-medium transition-colors">
                Chat
            </button>
            <button @click="view = 'settings'" :class="view === 'settings' ? 'bg-engram-50 text-engram-700' : 'text-gray-500 hover:text-gray-700'" class="px-4 py-2 rounded-lg text-sm font-medium transition-colors">
                Settings
            </button>
        </div>
    </nav>
```

With this:

```html
<body class="bg-gray-50 text-gray-900 h-screen overflow-hidden" x-data="engram()" x-init="init()">

    <div class="flex h-screen">
        <!-- Sidebar -->
        <aside class="bg-white border-r border-gray-200 flex flex-col transition-all duration-200"
               :class="sidebarCollapsed ? 'w-14' : 'w-52'">
            <!-- Logo + Toggle -->
            <div class="flex items-center px-3 py-4 border-b border-gray-100"
                 :class="sidebarCollapsed ? 'justify-center' : 'justify-between'">
                <a @click.prevent="view = 'home'" href="#" class="flex items-center gap-2 text-engram-700 hover:text-engram-600 transition-colors">
                    <i data-lucide="brain" class="w-6 h-6 flex-shrink-0"></i>
                    <span x-show="!sidebarCollapsed" class="font-semibold text-lg">Engram</span>
                </a>
                <button @click="toggleSidebar()" class="p-1 text-gray-400 hover:text-gray-600 rounded transition-colors"
                        x-show="!sidebarCollapsed">
                    <i data-lucide="panel-left-close" class="w-4 h-4"></i>
                </button>
                <button @click="toggleSidebar()" class="p-1 text-gray-400 hover:text-gray-600 rounded transition-colors mt-2"
                        x-show="sidebarCollapsed" x-cloak>
                    <i data-lucide="panel-left" class="w-4 h-4"></i>
                </button>
            </div>

            <!-- Nav items -->
            <nav class="flex-1 px-2 py-3 space-y-1">
                <button @click="view = 'chat'"
                        :class="view === 'chat' ? 'bg-engram-50 text-engram-700' : 'text-gray-600 hover:bg-gray-100'"
                        class="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
                        :class="sidebarCollapsed ? 'justify-center' : ''">
                    <i data-lucide="message-circle" class="w-5 h-5 flex-shrink-0"></i>
                    <span x-show="!sidebarCollapsed">Chat</span>
                </button>
                <button @click="view = 'preferences'"
                        :class="view === 'preferences' ? 'bg-engram-50 text-engram-700' : 'text-gray-600 hover:bg-gray-100'"
                        class="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
                        :class="sidebarCollapsed ? 'justify-center' : ''">
                    <i data-lucide="book-open" class="w-5 h-5 flex-shrink-0"></i>
                    <span x-show="!sidebarCollapsed">Preferences</span>
                </button>
            </nav>

            <!-- Settings (pinned to bottom) -->
            <div class="px-2 py-3 border-t border-gray-200">
                <button @click="view = 'settings'"
                        :class="view === 'settings' ? 'bg-engram-50 text-engram-700' : 'text-gray-600 hover:bg-gray-100'"
                        class="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
                        :class="sidebarCollapsed ? 'justify-center' : ''">
                    <i data-lucide="settings" class="w-5 h-5 flex-shrink-0"></i>
                    <span x-show="!sidebarCollapsed">Settings</span>
                </button>
            </div>
        </aside>

        <!-- Content area -->
        <main class="flex-1 overflow-hidden">
```

- [ ] **Step 2: Close the content area and flex wrapper at the end of the body**

Before the `<script>` tag (currently around line 270), find the closing point after all view divs and add:

```html
        </main>
    </div>
```

So the structure becomes:
```
<body>
  <div class="flex h-screen">
    <aside>...</aside>
    <main class="flex-1 overflow-hidden">
      <!-- all view divs here -->
    </main>
  </div>
  <script>...</script>
</body>
```

- [ ] **Step 3: Add sidebar state to Alpine data**

In the `engram()` function (around line 274), add these properties after `copiedIdx: null,`:

```javascript
sidebarCollapsed: localStorage.getItem('engram-sidebar-collapsed') === 'true',
```

And change:
```javascript
view: 'preferences',
```
to:
```javascript
view: 'home',
```

- [ ] **Step 4: Add `toggleSidebar()` method**

After the `updateStats()` method in the Alpine component:

```javascript
toggleSidebar() {
    this.sidebarCollapsed = !this.sidebarCollapsed;
    localStorage.setItem('engram-sidebar-collapsed', this.sidebarCollapsed);
    this.$nextTick(() => lucide.createIcons());
},
```

- [ ] **Step 5: Verify in browser**

Run: Open `http://localhost:3000` in browser (server must be running: `engramd serve`).

Check:
- Sidebar visible on left with Engram logo, Chat, Preferences, Settings
- Settings is at the bottom separated by a line
- Toggle button collapses sidebar to icons only
- Collapsed state shows `panel-left` icon, expanded shows `panel-left-close`
- Clicking nav items switches views
- Clicking Engram logo/text does nothing visible yet (home view not built yet)
- Sidebar collapse state persists across page reload
- No page-level scrollbar on any view

- [ ] **Step 6: Commit**

```bash
git add src/engram/ui/index.html
git commit -m "feat(ui): replace top nav with collapsible sidebar layout"
```

---

### Task 2: Add landing page (home view)

Add the `home` view with three cards that navigate to Chat, Preferences, and Settings.

**Files:**
- Modify: `src/engram/ui/index.html`

- [ ] **Step 1: Add the home view HTML**

Add this immediately after `<main class="flex-1 overflow-hidden">` and before the Preferences View div:

```html
            <!-- Home View -->
            <div x-show="view === 'home'" x-cloak class="h-full flex items-center justify-center">
                <div class="flex gap-6">
                    <button @click="view = 'chat'" class="group bg-white border border-gray-200 rounded-xl p-8 w-56 text-left hover:border-engram-300 hover:shadow-md transition-all">
                        <i data-lucide="message-circle" class="w-8 h-8 text-engram-500 mb-4 group-hover:text-engram-600 transition-colors"></i>
                        <h3 class="font-semibold text-gray-900 mb-1">Chat</h3>
                        <p class="text-sm text-gray-500">Talk to the curation agent</p>
                    </button>
                    <button @click="view = 'preferences'" class="group bg-white border border-gray-200 rounded-xl p-8 w-56 text-left hover:border-engram-300 hover:shadow-md transition-all">
                        <i data-lucide="book-open" class="w-8 h-8 text-engram-500 mb-4 group-hover:text-engram-600 transition-colors"></i>
                        <h3 class="font-semibold text-gray-900 mb-1">Preferences</h3>
                        <p class="text-sm text-gray-500">Browse and manage your preferences</p>
                    </button>
                    <button @click="view = 'settings'" class="group bg-white border border-gray-200 rounded-xl p-8 w-56 text-left hover:border-engram-300 hover:shadow-md transition-all">
                        <i data-lucide="settings" class="w-8 h-8 text-engram-500 mb-4 group-hover:text-engram-600 transition-colors"></i>
                        <h3 class="font-semibold text-gray-900 mb-1">Settings</h3>
                        <p class="text-sm text-gray-500">Configuration and stats</p>
                    </button>
                </div>
            </div>
```

- [ ] **Step 2: Verify in browser**

Run: Reload `http://localhost:3000`.

Check:
- Landing page shows by default (three cards centered)
- Cards have icons, titles, descriptions
- Hovering a card shows subtle border/shadow change
- Clicking each card navigates to the correct view
- Clicking Engram logo in sidebar returns to landing page
- No sidebar item is highlighted when on home view

- [ ] **Step 3: Commit**

```bash
git add src/engram/ui/index.html
git commit -m "feat(ui): add landing page with navigation cards"
```

---

### Task 3: Fix chat view scroll and update container classes

Fix the chat view so only the message area scrolls, not the entire page. Remove the `calc()` hack and use flex layout.

**Files:**
- Modify: `src/engram/ui/index.html` (chat view div, around line 166)

- [ ] **Step 1: Replace the chat view container**

Find the current chat view opening div:

```html
    <div x-show="view === 'chat'" x-cloak class="max-w-3xl mx-auto p-6 flex flex-col" style="height: calc(100vh - 57px)">
```

Replace with:

```html
            <div x-show="view === 'chat'" x-cloak class="h-full flex flex-col">
                <div class="max-w-3xl w-full mx-auto flex flex-col flex-1 min-h-0 p-6">
```

This wraps the chat content in a full-height flex container, then an inner container with the max-width constraint. `min-h-0` is critical — it allows the flex child to shrink below its content height, enabling the message area to scroll.

- [ ] **Step 2: Close the extra wrapper div**

Find the closing of the chat view. The current structure ends with:

```html
        </div>
    </div>
```

(the input area div close, then the chat view div close)

Replace with:

```html
                </div>
            </div>
```

Adding one more closing `</div>` for the inner wrapper.

- [ ] **Step 3: Update the preferences view container**

Find:

```html
    <div x-show="view === 'preferences'" x-cloak class="max-w-6xl mx-auto p-6">
```

Replace with:

```html
            <div x-show="view === 'preferences'" x-cloak class="h-full overflow-y-auto p-6">
                <div class="max-w-6xl mx-auto">
```

And add a closing `</div>` before the preferences view's closing div (after the Add Modal closing `</div>`).

- [ ] **Step 4: Update the settings view container**

Find:

```html
    <div x-show="view === 'settings'" x-cloak class="max-w-2xl mx-auto p-6">
```

Replace with:

```html
            <div x-show="view === 'settings'" x-cloak class="h-full overflow-y-auto p-6">
                <div class="max-w-2xl mx-auto">
```

And add a closing `</div>` before the settings view's closing div (after the Stats section closing `</div>`).

- [ ] **Step 5: Verify in browser**

Run: Reload `http://localhost:3000`, navigate to Chat.

Check:
- Send several messages to fill the chat area
- Only the message history area scrolls, not the page
- The input area stays pinned to the bottom
- No scrollbar on the right edge of the entire page
- Preferences view scrolls internally if content overflows
- Settings view scrolls internally if content overflows

- [ ] **Step 6: Commit**

```bash
git add src/engram/ui/index.html
git commit -m "fix(ui): chat view scrolls internally, no page-level scrollbar"
```

---

### Task 4: Reposition copy-to-clipboard button

Move the copy button from inside the message bubble (top-right, hover-only) to outside the bubble (bottom-left, always visible).

**Files:**
- Modify: `src/engram/ui/index.html` (chat message template, around line 173-187)

- [ ] **Step 1: Replace the message template**

Find the current message template (the `x-for` loop over `chatHistory`):

```html
            <template x-for="(msg, i) in chatHistory" :key="i">
                <div :class="msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'">
                    <div class="relative group max-w-[80%]">
                        <template x-if="msg.role === 'user'">
                            <div class="bg-engram-600 text-white rounded-lg px-4 py-3 text-sm whitespace-pre-wrap" x-text="msg.content"></div>
                        </template>
                        <template x-if="msg.role === 'assistant'">
                            <div class="bg-white border border-gray-200 rounded-lg px-4 py-3 text-sm prose prose-sm prose-gray" x-html="marked.parse(msg.content)"></div>
                        </template>
                        <button @click="navigator.clipboard.writeText(msg.content); copiedIdx = i; setTimeout(() => copiedIdx = null, 1500)" class="absolute top-2 right-2 p-1 rounded bg-gray-100/80 text-gray-400 hover:text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity" :title="copiedIdx === i ? 'Copied!' : 'Copy'">
                            <template x-if="copiedIdx !== i"><i data-lucide="copy" class="w-3.5 h-3.5"></i></template>
                            <template x-if="copiedIdx === i"><i data-lucide="check" class="w-3.5 h-3.5 text-green-500"></i></template>
                        </button>
                    </div>
                </div>
            </template>
```

Replace with:

```html
            <template x-for="(msg, i) in chatHistory" :key="i">
                <div :class="msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'">
                    <div class="max-w-[80%]">
                        <template x-if="msg.role === 'user'">
                            <div class="bg-engram-600 text-white rounded-lg px-4 py-3 text-sm whitespace-pre-wrap" x-text="msg.content"></div>
                        </template>
                        <template x-if="msg.role === 'assistant'">
                            <div class="bg-white border border-gray-200 rounded-lg px-4 py-3 text-sm prose prose-sm prose-gray" x-html="marked.parse(msg.content)"></div>
                        </template>
                        <button @click="navigator.clipboard.writeText(msg.content); copiedIdx = i; setTimeout(() => copiedIdx = null, 1500)" class="mt-1 p-1 rounded text-gray-400 hover:text-gray-600 transition-colors" :title="copiedIdx === i ? 'Copied!' : 'Copy'">
                            <template x-if="copiedIdx !== i"><i data-lucide="copy" class="w-3.5 h-3.5"></i></template>
                            <template x-if="copiedIdx === i"><i data-lucide="check" class="w-3.5 h-3.5 text-green-500"></i></template>
                        </button>
                    </div>
                </div>
            </template>
```

Key changes:
- Removed `relative group` from wrapper (no longer needed for hover positioning)
- Removed `absolute top-2 right-2` positioning from button
- Removed `opacity-0 group-hover:opacity-100` (always visible now)
- Removed `bg-gray-100/80` background from button
- Added `mt-1` for spacing below the bubble
- Button is now a block element below the bubble, naturally left-aligned

- [ ] **Step 2: Verify in browser**

Run: Reload `http://localhost:3000`, navigate to Chat, send a message.

Check:
- Copy icon appears below each message bubble, left-aligned
- Icon is always visible (no hover required)
- Clicking copies the message text
- Icon swaps to checkmark for ~1.5 seconds after clicking
- Works on both user and assistant messages

- [ ] **Step 3: Commit**

```bash
git add src/engram/ui/index.html
git commit -m "feat(ui): reposition copy button below message bubbles, always visible"
```

---

## Self-Review

**Spec coverage check:**
1. Page-level layout (sidebar + content) — Task 1 ✓
2. Collapsible sidebar with toggle — Task 1 ✓
3. `panel-left` / `panel-left-close` icons — Task 1 ✓
4. localStorage persistence — Task 1 ✓
5. Settings pinned to bottom with divider — Task 1 ✓
6. Engram logo navigates to home — Task 1 ✓
7. Landing page with three cards — Task 2 ✓
8. Chat scroll fix (no page scrollbar) — Task 3 ✓
9. Copy button bottom-left, always visible — Task 4 ✓
10. Preferences/settings views re-parented with internal scroll — Task 3 ✓
11. `view` default changes to `'home'` — Task 1 ✓

**Placeholder scan:** No TBDs, TODOs, or vague steps. All code is complete.

**Type consistency:** `sidebarCollapsed` used consistently. `view = 'home'` consistent across Task 1 (state init) and Task 2 (home div). `toggleSidebar()` method name matches the `@click` handler.
