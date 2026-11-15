const base = import.meta.env.BASE_URL;

export async function fetchGlobals() {
  const res = await fetch(`${base}configs/globals.json`);
  return res.json();
}

export async function fetchLessons() {
  const res = await fetch(`${base}configs/index.json`);
  return res.json();
}

// Vocab files are static — cache parsed JSON so sets within a round don't re-fetch.
const vocabCache = new Map();
async function loadVocab(file) {
  if (!vocabCache.has(file)) {
    const p = fetch(`${base}configs/${file}`).then(r => r.json());
    vocabCache.set(file, p);
    p.catch(() => vocabCache.delete(file));
  }
  return vocabCache.get(file);
}

// Returns sections for a lesson: [{ id, wordCount }, ...]
// id format: "lessonKey/sectionKey"
export async function fetchSections(lesson) {
  const data = await loadVocab(lesson.vocab_file);
  const sections = [];
  for (const [lk, lv] of Object.entries(data)) {
    for (const [sk, words] of Object.entries(lv)) {
      sections.push({ id: `${lk}/${sk}`, wordCount: words.length });
    }
  }
  return sections;
}

function toPair(w, bk, tk) {
  return {
    key:       w.german ?? w[bk],
    base:      w[bk],
    target:    w[tk],
    grammar:   w.grammar ?? '',
    icon:      w.icon ?? null,
    hardIcon:  !!w.hard_icon,
    conflicts: Array.isArray(w.conflicts) ? w.conflicts : [],
  };
}

async function loadPairs(config, sectionId = null) {
  const data = await loadVocab(config.vocab_file);
  const bk = config.base_language;
  const tk = config.target_language;
  const pairs = [];
  const add = words => {
    for (const w of words) {
      if (w[bk] !== undefined && w[tk] !== undefined) pairs.push(toPair(w, bk, tk));
    }
  };

  if (sectionId) {
    const [lk, sk] = sectionId.split('/');
    add(data[lk]?.[sk] || []);
  } else {
    for (const lv of Object.values(data)) {
      for (const words of Object.values(lv)) add(words);
    }
  }
  return pairs;
}

function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function sample(arr, n) {
  return shuffle(arr).slice(0, n);
}

// left/top are card *centers* (CSS uses translateX(-50%))
const GRID = [
  { left: '20%', top: '15%' },
  { left: '50%', top: '10%' },
  { left: '80%', top: '18%' },
  { left: '22%', top: '55%' },
  { left: '55%', top: '50%' },
  { left: '82%', top: '58%' },
];

const CARDS_PER_SET   = 6;
const TARGETS_PER_SET = 3;

export async function fetchSectionWords(config, sectionId = null) {
  return loadPairs(config, sectionId);
}

// Builds a deck for one game round.
// conflicts[i] = Set of pair indices that must not share a view with pair i.
// Sources: explicit `conflicts` (German words, same lesson file; symmetric) and
// identical base or target text.
export async function createDeck(config, sectionId = null) {
  const pairs = await loadPairs(config, sectionId);
  const n = pairs.length;
  const conflicts = pairs.map(() => new Set());
  const link = (a, b) => { if (a !== b) { conflicts[a].add(b); conflicts[b].add(a); } };

  const byKey = new Map();
  pairs.forEach((p, i) => {
    const k = p.key.toLowerCase();
    if (!byKey.has(k)) byKey.set(k, []);
    byKey.get(k).push(i);
  });
  pairs.forEach((p, i) => {
    for (const c of p.conflicts) {
      for (const j of byKey.get(String(c).toLowerCase()) ?? []) link(i, j);
    }
  });
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      if (pairs[i].base === pairs[j].base || pairs[i].target === pairs[j].target) link(i, j);
    }
  }

  return { pairs, conflicts, queue: shuffle([...Array(n).keys()]), current: [] };
}

function clashes(deck, idx, chosen) {
  return chosen.some(c => c === idx || deck.conflicts[idx].has(c));
}

// Picks the next set: targets come from the shuffled deck (every word is asked
// before any repeats), distractors are random non-conflicting words.
export function createRound(deck) {
  const n = deck.pairs.length;
  const targets = [];
  const nTargets = Math.min(TARGETS_PER_SET, n);

  // 1. Targets from the front of the queue, skipping clashes (they stay queued).
  for (let pass = 0; pass < 2 && targets.length < nTargets; pass++) {
    if (pass === 1) {
      // Queue exhausted or blocked: refill, putting words from the last set at the back.
      const fresh = shuffle([...Array(n).keys()].filter(i => !deck.queue.includes(i)));
      const recent = new Set(deck.current);
      deck.queue = [...deck.queue, ...fresh.filter(i => !recent.has(i)), ...fresh.filter(i => recent.has(i))];
    }
    for (let qi = 0; qi < deck.queue.length && targets.length < nTargets; ) {
      const idx = deck.queue[qi];
      if (clashes(deck, idx, targets)) { qi++; continue; }
      targets.push(idx);
      deck.queue.splice(qi, 1);
    }
  }
  // Last resort (all remaining words conflict): ignore conflicts, keep uniqueness.
  for (const idx of shuffle([...Array(n).keys()])) {
    if (targets.length >= nTargets) break;
    if (!targets.includes(idx)) targets.push(idx);
  }

  // 2. Distractors: prefer non-conflicting, then any unused, then repeats (tiny sections).
  const chosen = [...targets];
  const want = CARDS_PER_SET;
  const others = shuffle([...Array(n).keys()].filter(i => !chosen.includes(i)));
  for (const idx of others) {
    if (chosen.length >= want) break;
    if (!clashes(deck, idx, chosen)) chosen.push(idx);
  }
  for (const idx of others) {
    if (chosen.length >= want) break;
    if (!chosen.includes(idx)) chosen.push(idx);
  }
  while (chosen.length < want && n > 0) {
    // Fewer than 6 words in total — fill with non-target repeats where possible.
    const pool = [...Array(n).keys()].filter(i => !targets.includes(i));
    const src = pool.length ? pool : [...Array(n).keys()];
    chosen.push(src[Math.floor(Math.random() * src.length)]);
  }
  deck.current = chosen;

  // 3. Build cards; targets are mixed among positions.
  const order     = shuffle(chosen.map((idx, k) => ({ idx, isTarget: k < targets.length })));
  const positions = sample(GRID, CARDS_PER_SET);
  const displayCards = order.map(({ idx }, i) => {
    const pair = deck.pairs[idx];
    return {
      id:       i,
      base:     pair.base,
      target:   pair.target,
      grammar:  pair.grammar,
      icon:     pair.icon,
      hardIcon: pair.hardIcon,
      left:     positions[i].left,
      top:      positions[i].top,
      rot:      (Math.random() - 0.5) * 8,
    };
  });
  const targetWords = order.flatMap((o, i) => o.isTarget ? [displayCards[i].target] : []);
  return { displayCards, targetWords };
}
