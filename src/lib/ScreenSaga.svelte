<script>
  import { onMount } from 'svelte';
  import { roman, dirLabel, levelLocked, finalLocked } from './theme.js';

  let { lesson, sections, progress, starThresholds = [1, 10, 20], onBack, onStart } = $props();

  let finalPanelOpen = $state(false);
  const FINAL = 'final';

  function isDone(sectionId, dir) {
    return !!progress[lesson.id]?.[sectionId]?.[String(dir)]?.done;
  }

  function bestScore(sectionId, dir) {
    return progress[lesson.id]?.[sectionId]?.[String(dir)]?.best ?? -1;
  }

  function starsFor(sectionId, dir) {
    const b = bestScore(sectionId, dir);
    return b >= starThresholds[2] ? 3 : b >= starThresholds[1] ? 2 : b >= starThresholds[0] ? 1 : 0;
  }

  function hasEnoughStars(sectionId, dir) {
    return bestScore(sectionId, dir) >= starThresholds[1];
  }

  const isFinalUnlocked = $derived(!finalLocked(lesson, sections, progress, starThresholds));

  // One node per (section × direction): dir=1 first, then dir=0
  const levels = $derived(sections.flatMap((section, i) => [
    { section, sectionIdx: i, dir: 1 },
    { section, sectionIdx: i, dir: 0 },
  ]));

  const currentLevelKey = $derived.by(() => {
    for (const lv of levels) {
      if (levelLocked(lesson, lv.sectionIdx, lv.dir, sections, progress, starThresholds)) continue;
      if (!hasEnoughStars(lv.section.id, lv.dir)) return `${lv.section.id}:${lv.dir}`;
    }
    if (isFinalUnlocked && (!isDone(FINAL, 0) || !isDone(FINAL, 1))) return FINAL;
    return null;
  });

  const fAllDone   = $derived(hasEnoughStars(FINAL, 0) && hasEnoughStars(FINAL, 1));
  const fIsCurrent = $derived(currentLevelKey === FINAL);
  const fAlignRight = $derived(levels.length % 2 !== 0);

  function startFinal(dir) {
    onStart({ id: FINAL, isFinal: true }, dir);
    finalPanelOpen = false;
  }

  // Refs to each circle element — index 0..levels.length-1 for level nodes,
  // index levels.length for the final node.
  let circleEls = [];
  let sagaEl    = $state(null);
  let pathD     = $state('');
  let pathH     = $state(800);

  function measurePath() {
    if (!sagaEl) return;
    const sagaRect = sagaEl.getBoundingClientRect();
    const pts = circleEls
      .filter(Boolean)
      .map(el => {
        const r = el.getBoundingClientRect();
        return {
          x: +(r.left + r.width  / 2 - sagaRect.left).toFixed(1),
          y: +(r.top  + r.height / 2 - sagaRect.top  + sagaEl.scrollTop).toFixed(1),
        };
      });
    if (pts.length < 2) return;
    pathH = pts[pts.length - 1].y + 60;
    let d = `M ${pts[0].x} ${pts[0].y}`;
    for (let i = 1; i < pts.length; i++) {
      const p0 = pts[i - 1], p1 = pts[i];
      const dy = p1.y - p0.y;
      d += ` C ${p0.x} ${+(p0.y + dy * 0.5).toFixed(1)},`
         + ` ${p1.x} ${+(p1.y - dy * 0.5).toFixed(1)},`
         + ` ${p1.x} ${p1.y}`;
    }
    pathD = d;
  }

  onMount(() => {
    // Two rAF passes: first lets Svelte flush DOM, second waits for paint/layout.
    requestAnimationFrame(() => requestAnimationFrame(measurePath));
    const ro = new ResizeObserver(() => requestAnimationFrame(measurePath));
    ro.observe(sagaEl);
    return () => ro.disconnect();
  });
</script>

<div class="page">
  <div class="header">
    <button class="back-btn" aria-label="Zurück" onclick={onBack}>
      <svg width="14" height="14" viewBox="0 0 14 14">
        <path d="M9 2L3 7l6 5" stroke="#7A7269" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </button>
    <div>
      <div class="header-eyebrow">{lesson.name}</div>
      <div class="header-title">Lernpfad</div>
    </div>
  </div>

  <div class="saga" bind:this={sagaEl}>
    <!-- Path rendered first; bubbles (z-index:1) sit on top -->
    <svg class="path-svg" width="100%" height={pathH}>
      {#if pathD}
        <path d={pathD} stroke="#D4CDC0" stroke-width="2" stroke-dasharray="2 6" fill="none" stroke-linecap="round"/>
      {/if}
    </svg>

    {#each levels as lv, i}
      {@const locked   = levelLocked(lesson, lv.sectionIdx, lv.dir, sections, progress, starThresholds)}
      {@const cleared  = hasEnoughStars(lv.section.id, lv.dir)}
      {@const isCurrent = currentLevelKey === `${lv.section.id}:${lv.dir}`}
      {@const stars    = starsFor(lv.section.id, lv.dir)}
      {@const secName  = lv.section.id.split('/').pop()}

      <div class="node-row" class:right={i % 2 !== 0}>
        {#if isCurrent}
          <div class="callout">weiter hier<div class="callout-arrow"></div></div>
        {/if}
        <button
          class="node-btn"
          class:locked
          class:flipped={i % 2 !== 0}
          onclick={() => !locked && onStart(lv.section, lv.dir)}
        >
          <div
            class="circle"
            bind:this={circleEls[i]}
            style="
              background: {locked ? '#E8E3D9' : cleared ? '#E0F0E8' : isCurrent ? '#2F8F6E' : '#FFFFFF'};
              border: 1.5px solid {locked ? '#E8E3D9' : (cleared || isCurrent) ? '#2F8F6E' : '#D4CDC0'};
              box-shadow: {isCurrent ? '0 0 0 5px #E0F0E8, 0 1px 2px rgba(20,18,15,0.05)' : !locked ? '0 1px 3px rgba(20,18,15,0.07)' : 'none'};
            "
          >
            {#if locked}
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <rect x="5" y="11" width="14" height="9" rx="2" fill="#B0A89E"/>
                <path d="M8 11V8a4 4 0 1 1 8 0v3" stroke="#B0A89E" stroke-width="2" stroke-linecap="round"/>
              </svg>
            {:else}
              <span class="circle-numeral" style="color:{isCurrent ? '#FFFFFF' : cleared ? '#2F8F6E' : '#1F1D1A'}">{roman(lv.sectionIdx)}</span>
            {/if}
          </div>
          <div class="node-info">
            <div class="node-label" style="color:{locked ? '#B0A89E' : '#1F1D1A'}">{secName}</div>
            {#if !locked}
              <div class="node-sub">{dirLabel(lesson, lv.dir)} · {lv.section.wordCount} Wörter</div>
              <div class="node-stars">
                {#each [0, 1, 2] as st}
                  <svg width="10" height="10" viewBox="0 0 24 24">
                    <path d="M12 2.5l2.95 6.3 6.55.85-4.85 4.6 1.25 6.95L12 17.95 6.1 21.2l1.25-6.95L2.5 9.65l6.55-.85L12 2.5z"
                      fill={st < stars ? '#D49A4A' : '#E8E3D9'}/>
                  </svg>
                {/each}
              </div>
            {/if}
          </div>
        </button>
      </div>
    {/each}

    <!-- Final node -->
    <div class="node-row" class:right={fAlignRight}>
      {#if fIsCurrent}
        <div class="callout">weiter hier<div class="callout-arrow"></div></div>
      {/if}
      <button
        class="node-btn"
        class:locked={!isFinalUnlocked}
        class:flipped={fAlignRight}
        onclick={() => isFinalUnlocked && (finalPanelOpen = true)}
      >
        <div
          class="circle circle-final"
          bind:this={circleEls[levels.length]}
          style="
            background: {!isFinalUnlocked ? '#E8E3D9' : fAllDone ? '#E0F0E8' : fIsCurrent ? '#2F8F6E' : '#FFFFFF'};
            border: 1.5px solid {!isFinalUnlocked ? '#E8E3D9' : (fAllDone || fIsCurrent) ? '#2F8F6E' : '#D4CDC0'};
            box-shadow: {fIsCurrent ? '0 0 0 5px #E0F0E8, 0 1px 2px rgba(20,18,15,0.05)' : isFinalUnlocked ? '0 1px 3px rgba(20,18,15,0.07)' : 'none'};
          "
        >
          {#if !isFinalUnlocked}
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <rect x="5" y="11" width="14" height="9" rx="2" fill="#B0A89E"/>
              <path d="M8 11V8a4 4 0 1 1 8 0v3" stroke="#B0A89E" stroke-width="2.2" stroke-linecap="round"/>
            </svg>
          {:else}
            <svg width="28" height="28" viewBox="0 0 24 24">
              <path d="M12 2.5l2.95 6.3 6.55.85-4.85 4.6 1.25 6.95L12 17.95 6.1 21.2l1.25-6.95L2.5 9.65l6.55-.85L12 2.5z"
                fill={fAllDone ? '#2F8F6E' : '#D49A4A'}/>
            </svg>
          {/if}
        </div>
        <div class="node-info">
          <div class="node-label" style="color:{!isFinalUnlocked ? '#B0A89E' : '#1F1D1A'}">Finalrunde</div>
          {#if isFinalUnlocked}
            <div class="node-stars">
              {#each [0, 1, 2] as st}
                {@const best = Math.max(starsFor(FINAL, 0), starsFor(FINAL, 1))}
                <svg width="10" height="10" viewBox="0 0 24 24">
                  <path d="M12 2.5l2.95 6.3 6.55.85-4.85 4.6 1.25 6.95L12 17.95 6.1 21.2l1.25-6.95L2.5 9.65l6.55-.85L12 2.5z"
                    fill={st < best ? '#D49A4A' : '#E8E3D9'}/>
                </svg>
              {/each}
            </div>
          {/if}
        </div>
      </button>
    </div>
  </div>

  <!-- Direction picker only for final round -->
  {#if finalPanelOpen}
    <div class="dir-panel">
      <div class="dir-panel-label">Finalrunde · Richtung wählen</div>
      <div class="dir-btns">
        {#each [1, 0] as dir}
          {@const isDn = hasEnoughStars(FINAL, dir)}
          <button class="dir-btn" class:done={isDn} onclick={() => startFinal(dir)}>
            <span class="dir-btn-label">{dirLabel(lesson, dir)}</span>
            {#if isDn}<span class="dir-check">✓</span>{/if}
          </button>
        {/each}
      </div>
      <button class="dir-cancel" onclick={() => finalPanelOpen = false}>Abbrechen</button>
    </div>
  {/if}
</div>

<style>
  .page {
    min-height: 100dvh;
    background: #FBFAF7;
    font-family: 'Inter', system-ui, sans-serif;
    padding-bottom: 7rem;
    max-width: 600px;
    margin: 0 auto;
  }

  :global(body) { margin: 0; background: #FBFAF7; }

  .header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 3.5rem 1.25rem 1rem;
  }

  .back-btn {
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

  .header-eyebrow {
    font-size: 0.68rem;
    font-weight: 500;
    color: #B0A89E;
    letter-spacing: 0.3px;
  }

  .header-title {
    font-size: 1.3rem;
    font-weight: 700;
    color: #1F1D1A;
    line-height: 1.15;
    margin-top: 1px;
  }

  .saga {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    padding: 1rem 0 2rem;
    gap: 0;
  }

  .path-svg {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    z-index: 0;
    pointer-events: none;
    width: 100%;
    overflow: visible;
  }

  .node-row {
    padding-left: 2.5rem;
    padding-top: 1rem;
    padding-bottom: 1rem;
    position: relative;
    z-index: 1;
    min-height: 110px;
    display: flex;
    align-items: flex-start;
  }

  .node-row.right {
    align-self: flex-end;
    padding-left: 0;
    padding-right: 2.5rem;
  }

  .callout {
    position: absolute;
    top: 0;
    left: 50%;
    transform: translateX(-50%);
    background: #2F8F6E;
    color: #FFF;
    padding: 3px 10px;
    border-radius: 8px;
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.3px;
    white-space: nowrap;
    z-index: 2;
  }

  .callout-arrow {
    position: absolute;
    bottom: -5px;
    left: 50%;
    transform: translateX(-50%);
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #2F8F6E;
  }

  .node-btn {
    appearance: none;
    cursor: pointer;
    background: transparent;
    border: none;
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 0;
    font-family: inherit;
  }

  .node-btn.locked  { cursor: default; opacity: 0.7; }
  .node-btn.flipped { flex-direction: row-reverse; }

  .circle {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: background 200ms, border-color 200ms, box-shadow 200ms;
  }

  .circle-final {
    width: 76px;
    height: 76px;
  }

  .circle-numeral {
    font-size: 1.2rem;
    font-weight: 700;
    line-height: 1;
    font-family: inherit;
  }

  .node-info {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 3px;
  }

  .node-label {
    font-size: 0.85rem;
    font-weight: 600;
    line-height: 1.2;
  }

  .node-sub {
    font-size: 0.72rem;
    color: #7A7269;
    font-weight: 400;
  }

  .node-stars { display: flex; gap: 2px; }

  /* Direction picker for final round */
  .dir-panel {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: #FFFFFF;
    border-top: 1px solid #E8E3D9;
    box-shadow: 0 -4px 20px rgba(20,18,15,0.08);
    padding: 1rem 1.25rem 2.5rem;
    z-index: 10;
    max-width: 600px;
    margin: 0 auto;
  }

  .dir-panel-label {
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    color: #B0A89E;
    text-align: center;
    margin-bottom: 0.9rem;
  }

  .dir-btns { display: flex; gap: 0.75rem; }

  .dir-btn {
    flex: 1;
    appearance: none;
    cursor: pointer;
    background: #2F8F6E;
    color: #FFFFFF;
    border: none;
    border-radius: 12px;
    padding: 0.85rem;
    font-family: inherit;
    font-weight: 600;
    font-size: 0.95rem;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    box-shadow: 0 1px 2px rgba(20,18,15,0.08), 0 4px 12px rgba(20,18,15,0.06);
    transition: transform 80ms, box-shadow 80ms;
  }

  .dir-btn:active {
    transform: translateY(1px);
    box-shadow: 0 1px 2px rgba(20,18,15,0.10) inset;
  }

  .dir-btn.done {
    background: #E0F0E8;
    color: #2F8F6E;
    box-shadow: none;
  }

  .dir-btn-label {
    font-size: 0.9rem;
    font-weight: 600;
    letter-spacing: 0.5px;
    font-family: ui-monospace, monospace;
  }

  .dir-check { font-size: 0.9rem; font-weight: 700; }

  .dir-cancel {
    appearance: none;
    cursor: pointer;
    background: transparent;
    border: none;
    width: 100%;
    padding: 0.6rem;
    margin-top: 0.4rem;
    font-family: inherit;
    font-size: 0.9rem;
    font-weight: 500;
    color: #7A7269;
    text-align: center;
  }
</style>
