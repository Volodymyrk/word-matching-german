// v2 paper theme tokens — calm, content-first
export const T = {
  bg:           '#FBFAF7',
  panel:        '#FFFFFF',
  surface:      '#F4F2EC',
  ink:          '#1F1D1A',
  inkSoft:      '#7A7269',
  inkMuted:     '#B0A89E',
  border:       '#E8E3D9',
  borderStrong: '#D4CDC0',
  primary:      '#2F8F6E',
  primaryInk:   '#FFFFFF',
  primarySoft:  '#E0F0E8',
  accent:       '#D49A4A',
  correct:      '#2F8F6E',
  correctSoft:  '#E0F0E8',
  wrong:        '#C75A4A',
  locked:       '#E8E3D9',
  lockedInk:    '#B0A89E',
  // card tints — pale pastel washes behind white inner panel
  tintA: '#F5EFE3',
  tintB: '#EAF1ED',
  tintC: '#EDEAF5',
  tintD: '#F1ECE6',
  tintE: '#E8EFF2',
  tintF: '#F5E9E4',
  // backward-compat aliases used by game board
  cardBoard:    '#F5EFE3',
  cardBoardInk: '#1F1D1A',
  cardTarget:   '#EAF1ED',
  cardTargetInk:'#2F8F6E',
};

const LANG_CODES = { german: 'DE', latin: 'LA', english: 'EN', french: 'FR', spanish: 'ES' };
export const langCode = l => LANG_CODES[l] || l.slice(0, 2).toUpperCase();

const NUMERALS = ['I','II','III','IV','V','VI','VII','VIII','IX','X'];
export const roman = n => NUMERALS[n] ?? String(n + 1);

export function dirLabel(lesson, dir) {
  const board  = lesson.languages[dir];
  const prompt = lesson.languages[1 - dir];
  return `${langCode(prompt)} → ${langCode(board)}`;
}

// Is a specific level (sectionIdx, dir) locked?
export function levelLocked(lesson, sectionIdx, dir, sections, progress, starThresholds = [1, 10, 20]) {
  if (import.meta.env.DEV) return false;
  if (sectionIdx === 0 && dir === 1) return false;
  const lp = progress[lesson.id] || {};
  const twoStar = starThresholds[1];
  if (dir === 0) {
    const sp = lp[sections[sectionIdx].id] || {};
    return (sp['1']?.best ?? -1) < twoStar;
  } else {
    const pp = lp[sections[sectionIdx - 1].id] || {};
    return (pp['0']?.best ?? -1) < twoStar;
  }
}

// Final level locking — mirrors the progressive pattern of regular levels.
// dir=1: unlocks when the last section's dir=0 reaches ≥ 2 stars.
// dir=0: unlocks when final dir=1 reaches ≥ 2 stars.
export function finalLevelLocked(lesson, dir, sections, progress, starThresholds = [1, 10, 20]) {
  if (import.meta.env.DEV) return false;
  const lp = progress[lesson.id] || {};
  const twoStar = starThresholds[1];
  if (dir === 1) {
    const last = sections[sections.length - 1];
    if (!last) return false;
    return (lp[last.id]?.['0']?.best ?? -1) < twoStar;
  }
  return (lp['final']?.['1']?.best ?? -1) < twoStar;
}
