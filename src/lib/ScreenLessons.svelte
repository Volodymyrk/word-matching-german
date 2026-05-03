<script>
  import { roman } from './theme.js';
  import { lessonProgress } from './history.js';

  let { lessons, sectionsMap, progress, onSelect } = $props();

  const groups = $derived.by(() => {
    const map = new Map();
    for (const l of lessons) {
      const key = l.languages.join('-');
      if (!map.has(key)) map.set(key, { langs: l.languages, items: [] });
      map.get(key).items.push(l);
    }
    return [...map.values()];
  });

  const totalStars = $derived(
    lessons.reduce((sum, l) => {
      const p = lessonProgress(l, sectionsMap[l.id] || [], progress);
      // sum stars from best scores — approximate with done plays
      return sum + (p.finalDone ? 3 : 0);
    }, 0)
  );

  function groupLabel(langs) {
    const names = { german: 'Deutsch', latin: 'Latein', english: 'Englisch' };
    return langs.map(l => names[l] || l).join(' & ');
  }
</script>

<div class="page">
  <div class="header">
    <div class="header-eyebrow">Hallo</div>
    <div class="header-title">
      Vocabula <span class="brand-accent">Germanica</span>
    </div>

    <div class="stat-row">
      <div class="stat-item">
        <svg width="13" height="13" viewBox="0 0 24 24" style="flex-shrink:0">
          <path d="M12 2.5l2.95 6.3 6.55.85-4.85 4.6 1.25 6.95L12 17.95 6.1 21.2l1.25-6.95L2.5 9.65l6.55-.85L12 2.5z" fill="#D49A4A"/>
        </svg>
        <span class="stat-val">{totalStars}</span>
        <span class="stat-unit">Sterne</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat-item">
        <span class="stat-val">{lessons.length}</span>
        <span class="stat-unit">Lektionen</span>
      </div>
    </div>
  </div>

  {#each groups as group}
    <div class="group-label">{groupLabel(group.langs)}</div>
    <div class="lesson-list">
      {#each group.items as lesson}
        {@const prog = lessonProgress(lesson, sectionsMap[lesson.id] || [], progress)}
        {@const pct  = prog.totalSectionPlays
            ? Math.round((prog.doneSectionPlays / prog.totalSectionPlays) * 100)
            : 0}
        {@const isComplete = pct === 100 && prog.finalDone}
        {@const isStarted = pct > 0}
        <button class="lesson-card" onclick={() => onSelect(lesson)}>
          <div class="lesson-badge"
            style="background:{isComplete ? '#E0F0E8' : isStarted ? '#2F8F6E' : '#F4F2EC'};
                   color:{isComplete ? '#2F8F6E' : isStarted ? '#FFF' : '#B0A89E'}">
            {lesson.emoji ?? roman(group.items.indexOf(lesson))}
          </div>
          <div class="lesson-info">
            <div class="lesson-subtitle">{lesson.name}</div>
            <div class="lesson-name">{lesson.name}</div>
            <div class="lesson-progress">
              <div class="prog-track">
                <div class="prog-fill" style="width:{pct}%"></div>
              </div>
              <div class="lesson-stars">
                {#each [0, 1, 2] as s}
                  <svg width="11" height="11" viewBox="0 0 24 24">
                    <path d="M12 2.5l2.95 6.3 6.55.85-4.85 4.6 1.25 6.95L12 17.95 6.1 21.2l1.25-6.95L2.5 9.65l6.55-.85L12 2.5z"
                      fill={s < (prog.finalDone ? 3 : isStarted ? 1 : 0) ? '#D49A4A' : '#E8E3D9'} />
                  </svg>
                {/each}
              </div>
            </div>
          </div>
          <svg width="16" height="16" viewBox="0 0 16 16" style="flex-shrink:0;color:#B0A89E">
            <path d="M6 3l5 5-5 5" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      {/each}
    </div>
  {/each}
</div>

<style>
  .page {
    min-height: 100dvh;
    background: #FBFAF7;
    padding: 0 1.25rem 3rem;
    font-family: 'Inter', system-ui, sans-serif;
    max-width: 600px;
    margin: 0 auto;
  }

  :global(body) { margin: 0; background: #FBFAF7; }

  .header {
    padding: 4rem 0 1.25rem;
  }

  .header-eyebrow {
    font-size: 0.75rem;
    font-weight: 500;
    color: #7A7269;
    letter-spacing: 0.2px;
  }

  .header-title {
    font-size: 1.75rem;
    font-weight: 700;
    color: #1F1D1A;
    letter-spacing: -0.5px;
    line-height: 1.1;
    margin-top: 2px;
  }

  .brand-accent { color: #2F8F6E; font-weight: 600; }

  .stat-row {
    display: flex;
    align-items: center;
    gap: 18px;
    margin-top: 16px;
    padding: 10px 14px;
    border-radius: 12px;
    background: #F4F2EC;
    font-size: 0.8rem;
    color: #7A7269;
  }

  .stat-item { display: flex; align-items: center; gap: 5px; }
  .stat-val { color: #1F1D1A; font-weight: 600; }
  .stat-unit { color: #7A7269; }
  .stat-divider { width: 1px; height: 14px; background: #E8E3D9; }

  .group-label {
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    color: #B0A89E;
    margin: 1.5rem 0 0.6rem;
  }

  .lesson-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .lesson-card {
    appearance: none;
    cursor: pointer;
    text-align: left;
    background: #FFFFFF;
    border: 1px solid #E8E3D9;
    border-radius: 14px;
    padding: 14px;
    box-shadow: 0 1px 2px rgba(20,18,15,0.03);
    display: flex;
    align-items: center;
    gap: 14px;
    font-family: inherit;
    transition: box-shadow 120ms;
  }

  .lesson-card:active {
    box-shadow: 0 1px 4px rgba(20,18,15,0.08);
  }

  .lesson-badge {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.3rem;
    flex-shrink: 0;
    transition: background 200ms;
  }

  .lesson-info {
    flex: 1;
    min-width: 0;
  }

  .lesson-subtitle {
    font-size: 0;  /* hidden — name is used directly */
    display: none;
  }

  .lesson-name {
    font-size: 1rem;
    font-weight: 600;
    color: #1F1D1A;
    line-height: 1.2;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .lesson-progress {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 8px;
  }

  .prog-track {
    flex: 1;
    height: 4px;
    border-radius: 999px;
    background: #E8E3D9;
    overflow: hidden;
  }

  .prog-fill {
    height: 100%;
    background: #2F8F6E;
    border-radius: 999px;
    transition: width 400ms ease;
  }

  .lesson-stars { display: flex; gap: 2px; flex-shrink: 0; }
</style>
