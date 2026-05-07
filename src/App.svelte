<script>
  import { onMount, onDestroy, tick } from 'svelte';
  import { fetchGlobals, fetchLessons, fetchSections, fetchSectionWords, createRound } from './lib/vocab.js';
  import { logScore, getBestScore, getProgress, markPlay } from './lib/history.js';
  import { dirLabel, roman } from './lib/theme.js';
  import ScreenCourses  from './lib/ScreenCourses.svelte';
  import ScreenLessons  from './lib/ScreenLessons.svelte';
  import ScreenSaga     from './lib/ScreenSaga.svelte';
  import ScreenPreview  from './lib/ScreenPreview.svelte';
  import ScreenComplete from './lib/ScreenComplete.svelte';

  // ── Routing ────────────────────────────────────────────────────────────────
  let screen          = $state('courses'); // 'courses' | 'lessons' | 'saga' | 'preview' | 'game' | 'complete'
  let lessons         = $state([]);
  let sectionsMap     = $state({});        // lessonId → sections[]
  let sections        = $state([]);        // sections for selected lesson
  let selectedCourse  = $state(null);
  let selectedLesson  = $state(null);
  let selectedSection = $state(null);      // { id, wordCount } or { id: 'final', isFinal: true }
  let selectedDir     = $state(0);
  let progress        = $state({});
  let previewWords    = $state([]);
  let lastScore        = $state(0);
  let lastBaseScore    = $state(0);
  let lastTimeBonus    = $state(0);
  let lastStreakBonus   = $state(0);
  let lastElapsedSecs  = $state(0);
  let lastNextLabel    = $state('');
  let isNewBest       = $state(false);
  let globals         = $state(null);

  // ── Game state ─────────────────────────────────────────────────────────────
  const CARD_TINTS = ['#F5EFE3','#EAF1ED','#EDEAF5','#F1ECE6','#E8EFF2','#F5E9E4'];
  let displayCards     = $state([]);
  let targetWords      = $state([]);
  let matchedIds       = $state(new Set());
  let clickedIds       = $state(new Set());
  let score            = $state(0);
  let remainingSeconds = $state(0);
  let wrongCardId      = $state(-1);
  let mistakesInSet    = $state(0);
  let wrongInRound     = $state(0);
  let correctClicks    = $state(0);
  let wrongWords          = $state([]);  // { clicked, correct }[]
  let previewTargetWord   = $state(null);
  let setsCompleted    = $state(0);
  let comboClicks      = $state(0);
  let roundCompleted   = $state(false);
  let comboActive      = $state(false);
  let comboPrimed      = $state(false);
  let comboRestartKey  = $state(0);
  let comboDurationMs  = $state(1000);

  // ── Derived ────────────────────────────────────────────────────────────────
  const courses = $derived.by(() => {
    const map = new Map();
    for (const l of lessons) {
      if (!map.has(l.course_id)) {
        map.set(l.course_id, { id: l.course_id, name: l.course_name, emoji: l.course_emoji, lessons: [] });
      }
      map.get(l.course_id).lessons.push(l);
    }
    return [...map.values()];
  });

  const courseLessons = $derived(
    selectedCourse ? lessons.filter(l => l.course_id === selectedCourse.id) : []
  );

  const livesLeft   = $derived(Math.max(0, (globals?.lives ?? 3) - wrongInRound));
  const livesRange  = $derived(Array.from({ length: globals?.lives ?? 3 }, (_, i) => i));
  const setsPerRound = $derived(globals?.sets_per_round ?? 6);
  const setProgress  = $derived(setsCompleted);

  const boardLang       = $derived(selectedLesson?.languages?.[selectedDir] ?? '');
  const targetLang      = $derived(selectedLesson?.languages?.[1 - selectedDir] ?? '');

  const currentDirLabel = $derived.by(() => {
    if (!selectedLesson || selectedDir == null) return '';
    return dirLabel(selectedLesson, selectedDir);
  });

  const bottomLabel = $derived.by(() => {
    if (!selectedLesson) return 'Übersetze';
    const targetLang = selectedLesson.languages[1 - selectedDir];
    if (targetLang === 'latin')   return 'Übersetze ins Lateinische';
    if (targetLang === 'german')  return 'Übersetze ins Deutsche';
    if (targetLang === 'english') return 'Translate to English';
    return `→ ${targetLang}`;
  });

  const gameConfig = $derived.by(() => {
    if (!selectedLesson) return null;
    return {
      vocab_file:      selectedLesson.vocab_file,
      base_language:   selectedLesson.languages[selectedDir],
      target_language: selectedLesson.languages[1 - selectedDir],
    };
  });

  const sectionLabel = $derived.by(() => {
    if (!selectedSection) return '';
    if (selectedSection.isFinal) return 'Finalrunde';
    return selectedSection.id.split('/').pop();
  });

  let timerInterval        = null;
  let wrongTimeout         = null;
  let comboPrimedTimeout   = null;
  let targetPreviewTimeout = null;

  onMount(async () => {
    [globals, lessons] = await Promise.all([fetchGlobals(), fetchLessons()]);
    progress = getProgress();
    const pairs = await Promise.all(lessons.map(async l => [l.id, await fetchSections(l)]));
    sectionsMap = Object.fromEntries(pairs);
  });

  onDestroy(() => {
    clearInterval(timerInterval);
    clearTimeout(wrongTimeout);
    clearTimeout(comboPrimedTimeout);
    clearTimeout(targetPreviewTimeout);
  });

  // ── Navigation ─────────────────────────────────────────────────────────────
  function selectCourse(course) {
    selectedCourse = course;
    screen = 'lessons';
  }

  function selectLesson(lesson) {
    selectedLesson = lesson;
    sections = sectionsMap[lesson.id] || [];
    screen = 'saga';
  }

  async function startGame(section, dir) {
    selectedSection = section;
    selectedDir     = dir;
    const sectionId = section.isFinal ? null : section.id;
    const config = {
      vocab_file:      selectedLesson.vocab_file,
      base_language:   selectedLesson.languages[dir],
      target_language: selectedLesson.languages[1 - dir],
    };
    previewWords = await fetchSectionWords(config, sectionId);
    screen = 'preview';
  }

  function startGameFromPreview() {
    screen = 'game';
    loadRound();
  }

  function quitToSaga() {
    clearInterval(timerInterval);
    clearTimeout(wrongTimeout);
    clearTimeout(targetPreviewTimeout);
    displayCards      = [];
    targetWords       = [];
    previewTargetWord = null;
    screen = 'saga';
  }

  function handleContinue() {
    const configName = `${selectedLesson.id}-${selectedSection.id}-${selectedDir}`;
    logScore(lastScore, configName);
    markPlay(selectedLesson.id, selectedSection.id, selectedDir, lastScore);
    progress = getProgress();
    screen = 'saga';
  }

  function handleRetry() {
    screen = 'game';
    loadRound();
  }

  function computeNextLabel() {
    if (selectedSection?.isFinal) {
      return selectedDir === 1 ? `Finalrunde · ${dirLabel(selectedLesson, 0)}` : '';
    }
    const idx = sections.findIndex(s => s.id === selectedSection?.id);
    if (idx === -1) return '';
    if (selectedDir === 1) {
      return `${roman(idx)} · ${dirLabel(selectedLesson, 0)}`;
    } else if (idx + 1 < sections.length) {
      return `${roman(idx + 1)} · ${dirLabel(selectedLesson, 1)}`;
    }
    return `Finalrunde · ${dirLabel(selectedLesson, 1)}`;
  }

  function endRound() {
    clearInterval(timerInterval);
    const roundSecs   = globals?.round_seconds ?? 60;
    const elapsed     = roundSecs - remainingSeconds;
    const threshold   = globals?.time_bonus_threshold ?? Infinity;
    const scoreCorr   = globals?.score_correct ?? 1;
    const scoreCombo  = globals?.score_combo ?? 2;
    const tBonus      = roundCompleted && elapsed < threshold ? Math.floor(remainingSeconds / 5) : 0;
    const sBonus      = comboClicks * (scoreCombo - scoreCorr);

    lastElapsedSecs  = elapsed;
    lastBaseScore    = score;
    lastTimeBonus    = tBonus;
    lastStreakBonus   = sBonus;
    lastScore        = score + tBonus;
    lastNextLabel    = computeNextLabel();
    const configName = `${selectedLesson.id}-${selectedSection.id}-${selectedDir}`;
    const best       = getBestScore(configName);
    isNewBest        = lastScore > best && lastScore > 0;
    displayCards     = [];
    targetWords      = [];
    screen           = 'complete';
  }

  // ── Game logic ─────────────────────────────────────────────────────────────
  function startTimer() {
    clearInterval(timerInterval);
    timerInterval = setInterval(() => {
      if (remainingSeconds <= 0) return;
      remainingSeconds--;
      if (remainingSeconds === 0) endRound();
    }, 1000);
  }

  async function loadRound() {
    clearInterval(timerInterval);
    clearTimeout(wrongTimeout);
    const config    = gameConfig;
    const sectionId = selectedSection?.isFinal ? null : selectedSection?.id;
    const data      = await createRound(config, sectionId);
    displayCards      = data.displayCards;
    targetWords       = data.targetWords;
    matchedIds        = new Set();
    clickedIds        = new Set();
    score             = 0;
    setsCompleted     = 0;
    remainingSeconds  = globals?.round_seconds ?? 60;
    wrongCardId       = -1;
    mistakesInSet     = 0;
    wrongInRound      = 0;
    correctClicks     = 0;
    wrongWords        = [];
    previewTargetWord = null;
    clearTimeout(targetPreviewTimeout);
    comboClicks       = 0;
    roundCompleted    = false;
    comboActive       = false;
    comboPrimed       = false;
    comboRestartKey   = 0;
    comboDurationMs   = Math.round((globals?.combo_seconds ?? 2) * 1000);
    clearTimeout(comboPrimedTimeout);
    startTimer();
  }

  async function loadNextRound() {
    setsCompleted++;
    if (setsCompleted >= setsPerRound) { roundCompleted = true; endRound(); return; }
    await tick();
    const sectionId = selectedSection?.isFinal ? null : selectedSection?.id;
    const data      = await createRound(gameConfig, sectionId);
    displayCards    = data.displayCards;
    targetWords     = data.targetWords;
    matchedIds      = new Set();
    mistakesInSet   = 0;
    comboPrimed     = false;
    clearTimeout(comboPrimedTimeout);
    if (comboActive) {
      comboDurationMs = Math.round((globals?.combo_seconds ?? 2) * 1000 + (globals?.combo_new_set_bonus_seconds ?? 5) * 1000);
      comboRestartKey++;
    }
  }

  function clickCard(card) {
    wrongCardId = -1;
    clearTimeout(wrongTimeout);
    if (card.icon) clickedIds = new Set([...clickedIds, card.icon]);

    if (!targetWords.includes(card.target)) {
      score += globals?.score_wrong ?? -1;
      mistakesInSet++;
      wrongInRound++;
      wrongCardId  = card.id;
      comboActive  = false;
      comboPrimed  = false;
      comboRestartKey = 0;
      clearTimeout(comboPrimedTimeout);
      wrongTimeout = setTimeout(() => { wrongCardId = -1; }, globals?.wrong_flash_ms ?? 500);
      if (!wrongWords.some(w => w.clicked === card.base)) {
        wrongWords = [...wrongWords, { clicked: card.base, correct: card.target }];
      }
      return;
    }

    correctClicks++;
    if (boardLang === 'german' || targetLang === 'german') speakWord(card);

    const inCombo     = comboPrimed || comboActive;
    const comboDurMs  = Math.round((globals?.combo_seconds ?? 2) * 1000);
    score += inCombo ? (globals?.score_combo ?? 2) : (globals?.score_correct ?? 1);
    if (inCombo) comboClicks++;
    clearTimeout(comboPrimedTimeout);
    if (inCombo) {
      comboActive     = true;
      comboPrimed     = true;
      comboDurationMs = comboDurMs;
      comboRestartKey++;
    } else {
      comboPrimed = true;
      comboPrimedTimeout = setTimeout(() => { comboPrimed = false; }, comboDurMs);
    }
    remainingSeconds += globals?.timer_bonus_per_correct ?? 1;

    matchedIds = new Set([...matchedIds, card.id]);
    if (matchedIds.size >= targetWords.length) loadNextRound();
  }

  function comboExpired() { comboActive = false; comboPrimed = false; }

  function speakWord(card) {
    if (card.icon) {
      const stem = card.icon.replace(/\.[^.]+$/, '');
      const audio = new Audio(`${import.meta.env.BASE_URL}audio/${stem}.mp3`);
      audio.play().catch(() => {});
      return;
    }
    if (!window.speechSynthesis) return;
    const word    = boardLang === 'german' ? card.base : card.target;
    const grammar = card.grammar ?? '';
    const article = grammar === 'm' ? 'der' : grammar === 'f' ? 'die' : grammar === 'n' ? 'das' : '';
    const utt = new SpeechSynthesisUtterance(article ? `${article} ${word}` : word);
    utt.lang = 'de-DE';
    utt.rate = 0.9;
    speechSynthesis.cancel();
    speechSynthesis.speak(utt);
  }

  function clickTargetWord(word) {
    clearTimeout(targetPreviewTimeout);
    previewTargetWord = word;
    comboActive     = false;
    comboPrimed     = false;
    comboRestartKey = 0;
    clearTimeout(comboPrimedTimeout);
    targetPreviewTimeout = setTimeout(() => { previewTargetWord = null; }, globals?.wrong_flash_ms ?? 2000);
  }
</script>

{#if screen === 'courses'}
  <ScreenCourses {courses} {sectionsMap} {progress} onSelect={selectCourse} />

{:else if screen === 'lessons'}
  <ScreenLessons
    lessons={courseLessons}
    course={selectedCourse}
    {sectionsMap}
    {progress}
    onSelect={selectLesson}
    onBack={() => screen = 'courses'}
  />

{:else if screen === 'saga'}
  <ScreenSaga
    lesson={selectedLesson}
    {sections}
    {progress}
    starThresholds={globals?.star_thresholds ?? [1, 10, 20]}
    onBack={() => screen = 'lessons'}
    onStart={startGame}
  />

{:else if screen === 'preview'}
  <ScreenPreview
    lesson={selectedLesson}
    {sectionLabel}
    dir={selectedDir}
    words={previewWords}
    onBack={() => screen = 'saga'}
    onStart={startGameFromPreview}
  />

{:else if screen === 'game'}
  <div class="page">

    <!-- HUD row 1: quit + thin progress + count + life dots -->
    <div class="hud">
      <button class="quit-btn" aria-label="Zurück zur Saga" onclick={quitToSaga}>
        <svg width="13" height="13" viewBox="0 0 13 13">
          <path d="M2 2l9 9M11 2L2 11" stroke="#7A7269" stroke-width="1.8" stroke-linecap="round"/>
        </svg>
      </button>
      <div class="hud-bar-wrap">
        <div class="hud-bar">
          <div class="hud-bar-fill" style="width:{(setsCompleted / setsPerRound) * 100}%"
            class:combo={comboActive}></div>
        </div>
      </div>
      <div class="hud-count">{setsCompleted}/{setsPerRound}</div>
      <div class="hud-lives">
        {#each livesRange as i}
          <div class="life-dot" class:live={i < livesLeft}></div>
        {/each}
      </div>
    </div>

    <!-- HUD row 2: section label + direction badge + score -->
    <div class="hud-meta">
      <span class="hud-section">{sectionLabel}</span>
      <div class="hud-dir">{currentDirLabel}</div>
      <div class="hud-score">
        <svg width="11" height="11" viewBox="0 0 24 24" style="flex-shrink:0">
          <path d="M12 2.5l2.95 6.3 6.55.85-4.85 4.6 1.25 6.95L12 17.95 6.1 21.2l1.25-6.95L2.5 9.65l6.55-.85L12 2.5z" fill="#D49A4A"/>
        </svg>
        <span>{score}</span>
      </div>
    </div>

    <!-- Combo streak bar -->
    <div class="combo-strip">
      {#key comboRestartKey}
        <div
          class="combo-drain"
          class:active={comboRestartKey > 0}
          style={comboRestartKey > 0 ? `animation-duration:${comboDurationMs}ms` : ''}
          onanimationend={comboExpired}
        ></div>
      {/key}
    </div>

    <!-- Board -->
    <div class="board">
      {#each displayCards as card (card.id)}
        {@const tint = CARD_TINTS[card.id % 6]}
        <div class="card-anchor" style="left:{card.left}; top:{card.top}">
          <button
            class="board-card"
            class:wrong={wrongCardId === card.id}
            class:matched={matchedIds.has(card.id)}
            style="--rot:{card.rot || 0}deg; --tint:{tint}"
            onclick={() => clickCard(card)}
          >
            <div class="card-inner">
              {#if boardLang === 'english' && card.icon}
                <img class="card-icon" src="{import.meta.env.BASE_URL}icons/{card.icon}" alt={card.base}/>
                {#if !clickedIds.has(card.icon)}
                  <span class="card-icon-label">{card.base}</span>
                {/if}
              {:else}
                {@const cardArticle = boardLang !== 'german' ? '' : card.grammar === 'm' ? 'der' : card.grammar === 'f' ? 'die' : card.grammar === 'n' ? 'das' : ''}
                {#if cardArticle}
                  <span class="card-article">{cardArticle}</span>
                {/if}
                <span class="card-word">{card.base}</span>
              {/if}
            </div>
            {#if wrongCardId === card.id}
              <div class="card-hint-bubble">{card.target}</div>
            {/if}
          </button>
        </div>
      {/each}
    </div>

    <!-- Target panel -->
    <div class="target-panel">
      <div class="target-label">{bottomLabel}</div>
      <div class="target-row">
        {#each targetWords as word}
          {@const iconCard = displayCards.find(c => c.target === word)}
          {@const grammar = iconCard?.grammar ?? ''}
          {@const article = targetLang === 'german'
            ? (grammar === 'm' ? 'der' : grammar === 'f' ? 'die' : grammar === 'n' ? 'das' : '')
            : ''}
          <button
            class="target-card"
            class:peeking={previewTargetWord === word}
            class:matched={matchedIds.has(iconCard?.id)}
            onclick={() => clickTargetWord(word)}
          >
            {#if targetLang === 'english' && iconCard?.icon}
              <img class="target-icon" src="{import.meta.env.BASE_URL}icons/{iconCard.icon}" alt={word}/>
            {:else}
              {#if article}
                <span class="target-article">{article}</span>
              {/if}
              <span class="target-word">{word.replace(/^(der|die|das) /, '')}</span>
            {/if}
            {#if previewTargetWord === word}
              <span class="card-hint-bubble">{iconCard?.base ?? ''}</span>
            {/if}
          </button>
        {/each}
      </div>
    </div>

  </div>

{:else if screen === 'complete'}
  <ScreenComplete
    lesson={selectedLesson}
    {sectionLabel}
    dir={selectedDir}
    baseScore={lastBaseScore}
    timeBonus={lastTimeBonus}
    streakBonus={lastStreakBonus}
    elapsedSecs={lastElapsedSecs}
    wrongWords={wrongWords}
    correctClicks={correctClicks}
    wrongClicks={wrongInRound}
    {isNewBest}
    starThresholds={globals?.star_thresholds ?? [1, 10, 20]}
    nextLabel={lastNextLabel}
    onContinue={handleContinue}
    onRetry={handleRetry}
  />
{/if}

<style>
  @keyframes drain {
    from { width: 100%; }
    to   { width: 0%; }
  }
  @keyframes vmShake {
    0%, 100% { transform: rotate(var(--rot, 0deg)) translateX(0); }
    25%       { transform: rotate(var(--rot, 0deg)) translateX(-5px); }
    75%       { transform: rotate(var(--rot, 0deg)) translateX(5px); }
  }

  :global(body) { margin: 0; background: #FBFAF7; }

  .page {
    max-width: 600px;
    margin: 0 auto;
    padding: 0.6rem 0.75rem 0.5rem;
    font-family: 'Inter', system-ui, sans-serif;
    min-height: 100dvh;
    display: flex;
    flex-direction: column;
    background: #FBFAF7;
  }

  /* HUD row 1 */
  .hud {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0.3rem 0 0.2rem;
  }

  .quit-btn {
    appearance: none;
    cursor: pointer;
    width: 32px;
    height: 32px;
    border-radius: 10px;
    background: #F4F2EC;
    border: none;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .hud-bar-wrap {
    flex: 1;
    height: 4px;
    border-radius: 999px;
    background: #E8E3D9;
    overflow: hidden;
  }

  .hud-bar {
    height: 100%;
    border-radius: 999px;
    overflow: hidden;
  }

  .hud-bar-fill {
    height: 100%;
    background: #2F8F6E;
    border-radius: 999px;
    transition: width 300ms ease;
  }

  .hud-bar-fill.combo { background: #D49A4A; }

  .hud-count {
    font-size: 0.72rem;
    font-weight: 600;
    color: #7A7269;
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }

  .hud-lives { display: flex; gap: 3px; align-items: center; flex-shrink: 0; }

  .life-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #E8E3D9;
    transition: background 200ms;
  }
  .life-dot.live { background: #2F8F6E; }

  /* HUD row 2 */
  .hud-meta {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0.3rem 0 0.4rem;
    font-size: 0.8rem;
  }

  .hud-section {
    font-weight: 600;
    color: #1F1D1A;
    flex: 1;
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .hud-dir {
    display: inline-flex;
    align-items: center;
    padding: 3px 9px;
    border-radius: 999px;
    background: #F4F2EC;
    color: #7A7269;
    font-size: 0.72rem;
    font-weight: 600;
    font-family: ui-monospace, monospace;
    letter-spacing: 0.4px;
    flex-shrink: 0;
  }

  .hud-score {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 0.8rem;
    font-weight: 600;
    color: #1F1D1A;
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }

  /* Combo streak strip */
  .combo-strip {
    position: relative;
    height: 3px;
    border-radius: 999px;
    background: #E8E3D9;
    margin-bottom: 0.35rem;
    overflow: hidden;
  }
  .combo-drain {
    position: absolute;
    top: 0; left: 0;
    height: 100%;
    width: 0;
    border-radius: 999px;
    background: #D49A4A;
  }
  .combo-drain.active {
    width: 100%;
    animation: drain linear forwards;
  }

  /* Board */
  .board {
    position: relative;
    width: 100%;
    flex: 1;
    min-height: 280px;
    background: #FFFFFF;
    border: 1px solid #E8E3D9;
    border-radius: 18px;
    box-shadow: 0 1px 2px rgba(20,18,15,0.03), 0 4px 16px rgba(20,18,15,0.04);
    overflow: hidden;
    margin-bottom: 0.75rem;
  }

  .card-anchor {
    position: absolute;
    transform: translateX(-50%);
  }

  .board-card {
    appearance: none;
    cursor: pointer;
    background: var(--tint, #F5EFE3);
    border: 1px solid #E8E3D9;
    border-radius: 16px;
    padding: 4px;
    box-shadow: 0 1px 2px rgba(20,18,15,0.04), 0 4px 12px rgba(20,18,15,0.05);
    transform: rotate(var(--rot, 0deg));
    transition: transform 200ms ease, box-shadow 200ms;
    display: flex;
    flex-direction: column;
    align-items: center;
    position: relative;
  }
  .board-card:active {
    transform: rotate(var(--rot, 0deg)) scale(0.96);
    box-shadow: 0 1px 3px rgba(20,18,15,0.08);
  }
  .board-card.matched {
    visibility: hidden;
    pointer-events: none;
  }
  .board-card.wrong {
    border-color: #C75A4A;
    background: #FAE8E5;
    animation: vmShake 280ms ease-in-out;
  }

  .card-inner {
    background: transparent;
    border-radius: 13px;
    width: 104px;
    height: 104px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    position: relative;
  }

  .card-icon {
    width: 100px;
    height: 100px;
    object-fit: contain;
    display: block;
  }

  .card-icon-label {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    text-align: center;
    font-size: 0.58rem;
    font-weight: 600;
    color: rgba(31, 29, 26, .7);
    background: rgba(255, 255, 255, 0.5);
    padding: 2px 4px 3px;
    border-radius: 0 0 13px 13px;
    line-height: 1.3;
    pointer-events: none;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .card-article {
    font-size: 0.65rem;
    font-weight: 700;
    color: #7A7269;
    text-align: center;
    padding-top: 4px;
    font-family: inherit;
  }

  .card-word {
    font-size: 0.8rem;
    font-weight: 600;
    color: #1F1D1A;
    text-align: center;
    /* word-break: break-word; */
    hyphens: auto;
    line-height: 1.25;
    padding: 6px;
    font-family: inherit;
  }

  .card-hint-bubble {
    position: absolute;
    bottom: calc(100% + 6px);
    left: 50%;
    transform: translateX(-50%);
    background: #1F1D1A;
    color: #FFF;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 3px 9px;
    border-radius: 8px;
    white-space: nowrap;
    pointer-events: none;
    z-index: 10;
  }

  /* Target panel */
  .target-panel {
    background: #FFFFFF;
    border: 1px solid #E8E3D9;
    border-radius: 16px;
    box-shadow: 0 1px 2px rgba(20,18,15,0.03);
    padding: 12px 12px 14px;
    margin-bottom: 0.5rem;
  }

  .target-label {
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    color: #B0A89E;
    text-align: center;
    margin-bottom: 10px;
  }

  .target-row { display: flex; gap: 8px; }

  .target-card {
    flex: 1;
    min-width: 0;
    appearance: none;
    cursor: pointer;
    background: #fbfbfb;
    border: 1px solid #E8E3D9;
    border-radius: 12px;
    padding: 8px 4px;
    font-family: inherit;
    text-align: center;
    line-height: 1.2;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    transition: background 150ms, border-color 150ms;
    position: relative;
  }

  .target-card.matched {
    visibility: hidden;
    pointer-events: none;
  }
  .target-card:active, .target-card.peeking {
    background: #E0F0E8;
    border-color: #2F8F6E;
  }

  .target-article {
    font-size: 0.68rem;
    font-weight: 700;
    color: #7A7269;
  }

  .target-word {
    font-size: clamp(0.7rem, 2.6vw, 0.95rem);
    font-weight: 600;
    color: #1F1D1A;
    width: 100%;
    text-align: center;
  }

  .target-icon {
    width: 100px;
    height: 100px;
    object-fit: contain;
    display: block;
    /* background: #E0F0E8;
    border-color: #2F8F6E; */
    background: transparent;
  }
</style>
