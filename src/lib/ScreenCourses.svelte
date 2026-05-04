<script>
  import { lessonProgress } from './history.js';

  let { courses, sectionsMap, progress, onSelect } = $props();

  function courseStats(course) {
    let donePlays = 0, totalPlays = 0;
    for (const lesson of course.lessons) {
      const secs = sectionsMap[lesson.id] || [];
      const p = lessonProgress(lesson, secs, progress);
      donePlays  += p.doneSectionPlays;
      totalPlays += p.totalSectionPlays;
    }
    return {
      lessonCount: course.lessons.length,
      pct: totalPlays ? Math.round((donePlays / totalPlays) * 100) : 0,
    };
  }
</script>

<div class="page">
  <div class="header">
    <div class="header-eyebrow">Hallo</div>
    <div class="header-title">
      Vocabula <span class="brand-accent">Germanica</span>
    </div>
  </div>

  <div class="section-label">Kurse</div>
  <div class="course-list">
    {#each courses as course}
      {@const stats = courseStats(course)}
      {@const started = stats.pct > 0}
      <button class="course-card" onclick={() => onSelect(course)}>
        <div class="course-emoji-wrap" class:started>
          {course.emoji}
        </div>
        <div class="course-info">
          <div class="course-name">{course.name}</div>
          <div class="course-meta">
            <span class="course-count">{stats.lessonCount} Lektionen</span>
            <div class="prog-track">
              <div class="prog-fill" style="width:{stats.pct}%"></div>
            </div>
            <span class="prog-label">{stats.pct}%</span>
          </div>
        </div>
        <svg width="16" height="16" viewBox="0 0 16 16" style="flex-shrink:0;color:#B0A89E">
          <path d="M6 3l5 5-5 5" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
    {/each}
  </div>
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
    padding: 4rem 0 1.5rem;
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

  .section-label {
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    color: #B0A89E;
    margin-bottom: 0.75rem;
  }

  .course-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .course-card {
    appearance: none;
    cursor: pointer;
    text-align: left;
    background: #FFFFFF;
    border: 1px solid #E8E3D9;
    border-radius: 16px;
    padding: 16px;
    box-shadow: 0 1px 2px rgba(20,18,15,0.03);
    display: flex;
    align-items: center;
    gap: 16px;
    font-family: inherit;
    transition: box-shadow 120ms;
    width: 100%;
  }

  .course-card:active {
    box-shadow: 0 1px 6px rgba(20,18,15,0.1);
  }

  .course-emoji-wrap {
    width: 56px;
    height: 56px;
    border-radius: 14px;
    background: #F4F2EC;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.6rem;
    flex-shrink: 0;
    transition: background 200ms;
  }

  .course-emoji-wrap.started { background: #E0F0E8; }

  .course-info {
    flex: 1;
    min-width: 0;
  }

  .course-name {
    font-size: 1.05rem;
    font-weight: 700;
    color: #1F1D1A;
    line-height: 1.2;
  }

  .course-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 8px;
  }

  .course-count {
    font-size: 0.75rem;
    color: #7A7269;
    white-space: nowrap;
    flex-shrink: 0;
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

  .prog-label {
    font-size: 0.72rem;
    font-weight: 600;
    color: #7A7269;
    flex-shrink: 0;
    font-variant-numeric: tabular-nums;
  }
</style>
