const base = import.meta.env.BASE_URL;

export async function fetchGlobals() {
  const res = await fetch(`${base}configs/globals.json`);
  return res.json();
}

export async function fetchLessons() {
  const res = await fetch(`${base}configs/index.json`);
  return res.json();
}

// Returns sections for a lesson: [{ id, wordCount }, ...]
// id format: "lessonKey/sectionKey"
export async function fetchSections(lesson) {
  const res  = await fetch(`${base}configs/${lesson.vocab_file}`);
  const data = await res.json();
  const sections = [];
  for (const [lk, lv] of Object.entries(data)) {
    for (const [sk, words] of Object.entries(lv)) {
      sections.push({ id: `${lk}/${sk}`, wordCount: words.length });
    }
  }
  return sections;
}

async function loadPairs(config, sectionId = null) {
  const res  = await fetch(`${base}configs/${config.vocab_file}`);
  const data = await res.json();
  const bk = config.base_language;
  const tk = config.target_language;
  const pairs = [];

  if (sectionId) {
    const [lk, sk] = sectionId.split('/');
    const words = data[lk]?.[sk] || [];
    for (const w of words) {
      if (w[bk] !== undefined && w[tk] !== undefined) {
        pairs.push({ base: w[bk], target: w[tk], grammar: w.grammar ?? '', icon: w.icon ?? null });
      }
    }
  } else {
    for (const lv of Object.values(data)) {
      for (const words of Object.values(lv)) {
        for (const w of words) {
          if (w[bk] !== undefined && w[tk] !== undefined) {
            pairs.push({ base: w[bk], target: w[tk], grammar: w.grammar ?? '', icon: w.icon ?? null });
          }
        }
      }
    }
  }
  return pairs;
}

function sample(arr, n) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a.slice(0, n);
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

export async function fetchSectionWords(config, sectionId = null) {
  return loadPairs(config, sectionId);
}

// sectionId: "lessonKey/sectionKey" for section play, null for all-words final round
export async function createRound(config, sectionId = null) {
  let pairs = await loadPairs(config, sectionId);
  while (pairs.length < 6) pairs = [...pairs, ...pairs];
  const chosen        = sample(pairs, 6);
  const targetIndices = sample([0, 1, 2, 3, 4, 5], 3).sort((a, b) => a - b);
  const targetWords   = targetIndices.map(i => chosen[i].target);
  const positions     = sample(GRID, 6);
  const displayCards  = chosen.map((pair, i) => ({
    id:      i,
    base:    pair.base,
    target:  pair.target,
    grammar: pair.grammar,
    icon:    pair.icon,
    left:    positions[i].left,
    top:     positions[i].top,
    rot:     (Math.random() - 0.5) * 8,
  }));
  return { displayCards, targetWords };
}
