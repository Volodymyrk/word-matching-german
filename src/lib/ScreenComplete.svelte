<script>
  import { onMount, onDestroy } from 'svelte';
  import { dirLabel } from './theme.js';

  const base = import.meta.env.BASE_URL;

  let {
    lesson, sectionLabel, dir,
    baseScore, timeBonus, streakBonus, elapsedSecs,
    wrongWords = [], correctClicks, wrongClicks,
    isNewBest, starThresholds = [1, 10, 20],
    nextLabel = '',
    onContinue, onRetry,
  } = $props();

  const label      = $derived(dirLabel(lesson, dir));
  const totalScore = $derived(baseScore + timeBonus);
  const accuracy   = $derived(
    correctClicks + wrongClicks > 0
      ? Math.round(correctClicks / (correctClicks + wrongClicks) * 100)
      : 100
  );

  let displayScore = $state(0);
  let showStars    = $state(false);
  let starsVal     = $state(0);

  function formatTime(s) {
    const m = Math.floor(s / 60);
    return `${m}:${String(s % 60).padStart(2, '0')}`;
  }

  function computeStars(s) {
    return s >= starThresholds[2] ? 3
         : s >= starThresholds[1] ? 2
         : s >= starThresholds[0] ? 1 : 0;
  }

  let animInterval;
  let starTimeout;

  onMount(() => {
    displayScore = baseScore;

    if (timeBonus <= 0) {
      displayScore = totalScore;
      showStars    = true;
      starsVal     = computeStars(totalScore);
      return;
    }

    animInterval = setInterval(() => {
      if (displayScore < totalScore) displayScore++;
      if (displayScore >= totalScore) {
        clearInterval(animInterval);
        starTimeout = setTimeout(() => {
          starsVal  = computeStars(totalScore);
          showStars = true;
        }, 350);
      }
    }, 80);
  });

  onDestroy(() => {
    clearInterval(animInterval);
    clearTimeout(starTimeout);
  });
</script>

<div class="page">
  <div class="content">
    <div class="eyebrow">Geschafft</div>
    <div class="title">Super gemacht</div>
    <div class="subtitle">{lesson.name} · {sectionLabel} · {label}</div>

    <!-- Stars with scale-in animation -->
    <div class="stars">
      {#each [0, 1, 2] as i}
        <div class="star-wrap" style="animation-delay:{showStars ? i * 120 : 0}ms">
          <svg width="48" height="48" viewBox="0 0 24 24" class="star" class:earned={showStars && i < starsVal}>
            <path d="M12 2.5l2.95 6.3 6.55.85-4.85 4.6 1.25 6.95L12 17.95 6.1 21.2l1.25-6.95L2.5 9.65l6.55-.85L12 2.5z"
              fill={showStars && i < starsVal ? '#D49A4A' : '#E8E3D9'}/>
          </svg>
        </div>
      {/each}
    </div>

    <!-- Stat row -->
    <div class="stat-row">
      <div class="stat-item">
        <div class="stat-label">Punkte</div>
        <div class="stat-val">+{displayScore}</div>
        {#if isNewBest}<div class="new-best">★ Rekord</div>{/if}
      </div>
      <div class="stat-divider"></div>
      <div class="stat-item">
        <div class="stat-label">Zeit</div>
        <div class="stat-val">{formatTime(elapsedSecs)}</div>
      </div>
      <div class="stat-divider"></div>
      <div class="stat-item">
        <div class="stat-label">Treffer</div>
        <div class="stat-val">{accuracy}%</div>
      </div>
    </div>

    <!-- Bonus breakdown -->
    <div class="bonus-card">
      <div class="bonus-line">
        <span class="bonus-lbl">Kombo Bonus</span>
        <span class="bonus-pts" class:dim={streakBonus === 0}>+{streakBonus}</span>
      </div>
      <div class="bonus-sep"></div>
      <div class="bonus-line">
        <span class="bonus-lbl">Zeit Bonus</span>
        <span class="bonus-pts" class:dim={timeBonus === 0}>+{timeBonus}</span>
      </div>
    </div>

    <!-- Wrong words — review list -->
    {#if wrongWords.length > 0}
      <div class="review-section">
        <div class="review-title">Wiederholen</div>
        <div class="review-card">
          {#each wrongWords as w, i}
            <div class="review-row" class:border-top={i > 0}>
              <div class="review-icon-wrap">
                {#if w.icon}
                  <img src="{base}icons/{w.icon}" alt={w.clicked} class="review-icon"/>
                {:else}
                  <span class="review-icon-text">{w.clicked.slice(0, 2)}</span>
                {/if}
              </div>
              <span class="review-clicked">{w.clicked}</span>
              <svg width="14" height="10" viewBox="0 0 14 10" style="flex-shrink:0;color:#B0A89E">
                <path d="M1 5h11m-3-3l3 3-3 3" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              <span class="review-correct">{w.correct}</span>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- Actions -->
    <div class="actions">
      <button class="btn-primary" onclick={onContinue}>
        Weiter{nextLabel ? ` · ${nextLabel}` : ''}
      </button>
      <button class="btn-ghost" onclick={onRetry}>Wiederholen</button>
    </div>
  </div>
</div>

<style>
  @keyframes v2Star {
    0%   { transform: scale(0); }
    60%  { transform: scale(1.25); }
    100% { transform: scale(1); }
  }

  :global(body) { margin: 0; background: #FBFAF7; }

  .page {
    min-height: 100dvh;
    background: #FBFAF7;
    font-family: 'Inter', system-ui, sans-serif;
    display: flex;
    flex-direction: column;
  }

  .content {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 5rem 1.5rem 3rem;
    text-align: center;
    max-width: 600px;
    margin: 0 auto;
    width: 100%;
    box-sizing: border-box;
  }

  .eyebrow {
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    color: #B0A89E;
  }

  .title {
    font-size: 2rem;
    font-weight: 700;
    color: #1F1D1A;
    letter-spacing: -0.5px;
    line-height: 1.1;
    margin-top: 4px;
  }

  .subtitle {
    font-size: 0.85rem;
    color: #7A7269;
    margin-top: 6px;
  }

  /* Stars */
  .stars {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    margin: 2rem 0 1.5rem;
    min-height: 52px;
  }

  .star-wrap { display: flex; }

  .star { display: block; transition: fill 200ms; }

  .star.earned {
    animation: v2Star 480ms ease-out backwards;
  }

  /* Stat row */
  .stat-row {
    display: flex;
    align-items: center;
    width: 100%;
    max-width: 360px;
    padding: 14px 18px;
    background: #F4F2EC;
    border-radius: 14px;
    margin-bottom: 8px;
  }

  .stat-item {
    flex: 1;
    text-align: center;
  }

  .stat-label {
    font-size: 0.68rem;
    font-weight: 500;
    color: #7A7269;
    letter-spacing: 0.2px;
  }

  .stat-val {
    font-size: 1.25rem;
    font-weight: 700;
    color: #1F1D1A;
    margin-top: 2px;
    font-variant-numeric: tabular-nums;
  }

  .new-best {
    font-size: 0.6rem;
    font-weight: 600;
    color: #2F8F6E;
    letter-spacing: 0.3px;
    margin-top: 2px;
  }

  .stat-divider {
    width: 1px;
    height: 28px;
    background: #E8E3D9;
  }

  /* Bonus card */
  .bonus-card {
    width: 100%;
    max-width: 360px;
    background: #F4F2EC;
    border-radius: 10px;
    padding: 6px 18px;
    margin-bottom: 1.25rem;
  }

  .bonus-line {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 0;
  }

  .bonus-sep {
    height: 1px;
    background: #E8E3D9;
  }

  .bonus-lbl {
    font-size: 0.78rem;
    font-weight: 500;
    color: #7A7269;
  }

  .bonus-pts {
    font-size: 0.85rem;
    font-weight: 700;
    color: #1F1D1A;
    font-variant-numeric: tabular-nums;
  }

  .bonus-pts.dim {
    color: #B0A89E;
  }

  /* Review list */
  .review-section {
    width: 100%;
    max-width: 360px;
    margin-bottom: 1.25rem;
    text-align: left;
  }

  .review-title {
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    color: #B0A89E;
    margin-bottom: 8px;
    padding: 0 4px;
  }

  .review-card {
    background: #FFFFFF;
    border: 1px solid #E8E3D9;
    border-radius: 14px;
    padding: 4px;
    box-shadow: 0 1px 2px rgba(20,18,15,0.03);
  }

  .review-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
  }

  .review-row.border-top { border-top: 1px solid #E8E3D9; }

  .review-icon-wrap {
    width: 38px;
    height: 38px;
    border-radius: 10px;
    background: #F5EFE3;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    overflow: hidden;
  }

  .review-icon { width: 32px; height: 32px; object-fit: contain; }

  .review-icon-text {
    font-size: 0.75rem;
    font-weight: 700;
    color: #7A7269;
  }

  .review-clicked {
    flex: 1;
    font-size: 0.9rem;
    font-weight: 600;
    color: #1F1D1A;
    min-width: 0;
    text-align: left;
  }

  .review-correct {
    font-size: 0.9rem;
    font-weight: 600;
    color: #2F8F6E;
    flex-shrink: 0;
  }

  /* Actions */
  .actions {
    display: flex;
    flex-direction: column;
    gap: 6px;
    width: 100%;
    max-width: 360px;
    margin-top: auto;
    padding-top: 1rem;
  }

  .btn-primary {
    appearance: none;
    cursor: pointer;
    background: #2F8F6E;
    color: #FFFFFF;
    border: none;
    border-radius: 12px;
    padding: 14px 24px;
    font-family: inherit;
    font-weight: 600;
    font-size: 1rem;
    box-shadow: 0 1px 2px rgba(20,18,15,0.08), 0 4px 12px rgba(20,18,15,0.06);
    transition: transform 100ms, box-shadow 100ms;
  }

  .btn-primary:active {
    transform: translateY(1px);
    box-shadow: 0 1px 2px rgba(20,18,15,0.10) inset;
  }

  .btn-ghost {
    appearance: none;
    cursor: pointer;
    background: transparent;
    border: none;
    padding: 10px 16px;
    font-family: inherit;
    font-size: 0.9rem;
    font-weight: 500;
    color: #7A7269;
  }
</style>
