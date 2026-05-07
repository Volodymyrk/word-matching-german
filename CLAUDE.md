# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
npm install        # install dependencies
npm run dev        # dev server at http://localhost:5173
npm run build      # production build → dist/
npm run preview    # preview the production build locally
```

Python scripts (in `scripts/`) must be run with `uv`:
```bash
uv run scripts/generate_index.py
```

There are no tests or linter config in this project.

## Architecture

Pure frontend Svelte 5 app (Vite). No backend — deployed as static files from `dist/`.

### Screens & routing

`App.svelte` holds all state and routes between six screens via `screen: 'courses' | 'lessons' | 'saga' | 'preview' | 'game' | 'complete'`:

| Screen | Component | Purpose |
|---|---|---|
| `courses` | `ScreenCourses.svelte` | Course selection with progress cards |
| `lessons` | `ScreenLessons.svelte` | Lesson list for a selected course |
| `saga` | `ScreenSaga.svelte` | Node-map of sections for a selected lesson |
| `preview` | `ScreenPreview.svelte` | Full vocab list before starting a round |
| `game` | (inline in App.svelte) | Card-matching gameplay |
| `complete` | `ScreenComplete.svelte` | Score + stars after a round |

### Key files

**`src/App.svelte`** — all game state. Uses Svelte 5 runes (`$state`, `$derived`, `$derived.by`). Key state:

```js
// Navigation
let lessons         = $state([]);     // all lessons from index.json
let sectionsMap     = $state({});     // lessonId → sections[] (preloaded on mount)
let sections        = $state([]);     // sections for currently selected lesson
let selectedCourse  = $state(null);
let selectedLesson  = $state(null);
let selectedSection = $state(null);   // { id, wordCount } or { id: 'final', isFinal: true }
let selectedDir     = $state(0);      // 0 or 1
let progress        = $state({});     // from localStorage
let globals         = $state({});     // from globals.json (scoring, timing config)

// Game board
let displayCards    = $state([]);     // 6 card objects with position, text, icon, rotation
let targetWords     = $state([]);     // 3 target words to match against
let matchedIds      = $state(new Set());
let clickedIds      = $state(new Set());
let wrongCardId     = $state(-1);
let score           = $state(0);
let remainingSeconds = $state(0);
let mistakesInSet   = $state(0);
let wrongInRound    = $state(0);
let correctClicks   = $state(0);
let wrongWords      = $state([]);     // [{ clicked, correct }] for review on complete screen
let previewTargetWord = $state(null);

// Game progression
let setsCompleted   = $state(0);
let comboActive     = $state(false);
let comboPrimed     = $state(false);
let comboRestartKey = $state(0);
let comboDurationMs = $state(0);
```

Key derived state: `courses` (grouped from lessons), `courseLessons`, `livesLeft`, `boardLang`, `targetLang`, `currentDirLabel`, `bottomLabel`, `gameConfig`, `sectionLabel`.

Navigation functions: `selectCourse()` → lessons, `selectLesson()` → saga, `startGame(section, dir)` → preview, `startGameFromPreview()` → game, `quitToSaga()` → saga, `handleContinue()` → saga, `handleRetry()` → game, `endRound()` → complete.

`loadRound()` passes `sectionId = selectedSection?.isFinal ? null : selectedSection?.id` to `createRound` (null = all words = final round).

Timer via `setInterval`, combo bar via `{#key comboRestartKey}` to replay CSS `drain` animation, wrong/perfect-set flashes via `setTimeout`. Lives system: `globals.lives` wrong answers allowed before game over.

**`src/lib/vocab.js`** — pure JS data layer:
- `fetchLessons()` → loads `index.json` and `globals.json`, returns `{ lessons, globals }`
- `fetchSections(lesson)` → returns `[{ id: "lessonKey/sectionKey", wordCount }]`
- `createRound(config, sectionId=null)` → picks random pairs for 9 sets of 6 cards; null means all words

**`src/lib/history.js`** — localStorage under key `word_matching_history`:
- `markPlay(lessonId, sectionId, dir, score)` — records play; `sectionId` is `'final'` for final round
- `lessonProgress(lesson, sections, progress)` → `{ doneSectionPlays, totalSectionPlays, finalDone }`
- `getProgress()` / `setProgress()`

**`src/lib/theme.js`** — shared constants and helpers:
- `sectionLocked(lesson, idx, sections, progress)` — section 0 always open; N+1 needs N to have ≥1 dir done
- `finalLocked(lesson, sections, progress)` — locked until every section has ≥1 dir done
- `dirLabel(lesson, dir)` → `"DE → EN"` style badge text
- `roman(n)` → Roman numeral string
- Color tokens under `T` (cream, peach, sage, sand, terracotta, etc.)

**`src/lib/ScreenCourses.svelte`** — root course selection:
- Shows all courses as cards with lesson count, total stars, and course-level progress %
- Derives completion stats across all lessons in each course

**`src/lib/ScreenLessons.svelte`** — lesson list within a course:
- Back button to courses screen
- Progress bar per lesson via `lessonProgress(lesson, sectionsMap[lesson.id] || [], progress)`
- Star count and completion badge per lesson

**`src/lib/ScreenSaga.svelte`** — section node map:
- Nodes alternate left/right (`i % 2 !== 0` → `.right`), connected by curved SVG paths
- Each section node: colored by state (locked=sand, untouched=cream, current=terracotta, done=sage), Roman numeral, two direction dots
- Final node: circular (`magna` class), star icon when unlocked
- Tapping an unlocked node opens a fixed bottom panel (`dir-panel`) to pick direction
- `currentId` derived: first incomplete unlocked section (or final), shown with "HIER WEITER" callout

**`src/lib/ScreenPreview.svelte`** — vocab preview before gameplay:
- Shows full word list for the selected section with German word, article (derived from `grammar` m/f/n), and English translation
- Icon per word, speech synthesis audio playback
- Start button transitions to game

**`src/lib/ScreenComplete.svelte`** — round-end screen:
- Props: `{ lesson, sectionLabel, dir, score, isNewBest, onContinue, onRetry }`
- Animated star earn-in (0–3), score breakdown (base + time bonus), accuracy stats
- Wrong-word review panel: shows clicked vs. correct pairs
- Confetti on new high score (canvas-confetti from CDN, loaded lazily)

### Progress data shape (localStorage)

```js
{
  [lessonId]: {
    [sectionId]: {          // e.g. "lesson_4/Grundwörter" or "final"
      "0": { done: bool, best: number },
      "1": { done: bool, best: number }
    }
  }
}
```

Direction index: `dir=0` → `languages[0]` on board, `languages[1]` as prompts; `dir=1` flipped.

## Config & vocab data format

All data lives under `public/configs/` and is served as static files.

**`globals.json`** — game-wide scoring and timing config:
```json
{
  "round_seconds": 60,
  "combo_seconds": 2,
  "combo_new_set_bonus_seconds": 2,
  "score_correct": 1,
  "score_combo": 2,
  "score_wrong": -1,
  "timer_bonus_per_correct": 1,
  "star_thresholds": [15, 30, 50],
  "lives": 3,
  "wrong_flash_ms": 2000,
  "sets_per_round": 9
}
```

**`index.json`** — flat array of all lessons (currently 18: 3 German Basics + 15 Goethe A1). Each lesson:
```json
{
  "id": "de1",
  "name": "Deutsch Lektion 1",
  "emoji": "👋",
  "vocab_file": "courses/German_1/german_1.json",
  "languages": ["german", "english"],
  "course_id": "german_1",
  "course_name": "German Basics",
  "course_emoji": "🇩🇪"
}
```
`languages[dir]` = language shown on the board for that direction; `languages[1-dir]` = prompt language.

**`courses/<CourseName>/course.json`** — course metadata:
```json
{ "name": "Goethe A1", "id_prefix": "goethe_a1", "emoji": "📖", "languages": ["german", "english"] }
```

**Vocab file** (e.g. `courses/German_1/german_1.json`): nested `lessonKey → sectionKey → [items]`. Each item has one key per language plus optional `"grammar"`:
```json
{ "german": "Apfel", "english": "apple", "grammar": "m" }
```
`grammar` holds noun gender (`m`/`f`/`n`) or a label like `"Adj."` for adjectives; empty string for phrases/particles. German articles are derived from the gender: `m` → "der", `f` → "die", `n` → "das".

Section IDs are `"lessonKey/sectionKey"` (e.g. `"lesson_4/Grundwörter"`). Final round uses `sectionId = null` in `createRound`.

**Courses & lessons:**
- `courses/German_1/` — de1 (Deutsch Lektion 1), de2 (Supermarkt), de3 (Supermarkt II)
- `courses/Goethe_A1/` — goethe_a1_1 through goethe_a1_15 (Persönliche Angaben → Sprache und Medien)

## Design system

Neo-brutal style: thick `#1B1410` borders, offset box-shadows (`3px 3px 0 #1B1410`), cream/peach/sage palette. All tokens in `theme.js` under `T`.

Fonts (Google Fonts): DM Serif Display (headings, italic), Bricolage Grotesque (body/buttons), Geist Mono (labels/badges).

## Scoring rules

- Correct guess: +1 pt (or +2 within combo window after previous correct)
- Wrong guess: −1 pt, combo resets; uses one life (`globals.lives = 3` total per round)
- Each correct guess adds 1 bonus second to timer
- Star thresholds: 1★ ≥15 pts, 2★ ≥30 pts, 3★ ≥50 pts (from `globals.star_thresholds`)
- New high score triggers confetti
