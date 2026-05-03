<script>
  import { dirLabel } from './theme.js';

  const base = import.meta.env.BASE_URL;

  let { lesson, sectionLabel, dir, words = [], onBack, onStart } = $props();

  const label      = $derived(dirLabel(lesson, dir));
  const baseLang   = $derived(lesson.languages[dir]);

  // Always show german → english → icon regardless of play direction
  function germanWord(w)  { return baseLang === 'german' ? w.base   : w.target; }
  function englishWord(w) { return baseLang === 'english' ? w.base  : w.target; }

  function speakWord(w) {
    if (w.icon) {
      const stem = w.icon.replace(/\.[^.]+$/, '');
      new Audio(`${base}audio/${stem}.mp3`).play().catch(() => {});
      return;
    }
    if (!window.speechSynthesis) return;
    const word    = germanWord(w);
    const grammar = w.grammar ?? '';
    const article = grammar === 'm' ? 'der' : grammar === 'f' ? 'die' : grammar === 'n' ? 'das' : '';
    const utt = new SpeechSynthesisUtterance(article ? `${article} ${word}` : word);
    utt.lang = 'de-DE';
    utt.rate = 0.9;
    speechSynthesis.cancel();
    speechSynthesis.speak(utt);
  }
</script>

<div class="page">
  <div class="header">
    <button class="back-btn" aria-label="Zurück" onclick={onBack}>
      <svg width="14" height="14" viewBox="0 0 14 14">
        <path d="M9 2L3 7l6 5" stroke="#7A7269" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </button>
    <div>
      <div class="header-eyebrow">Vokabeln</div>
      <div class="header-title">{lesson.name} · {sectionLabel}</div>
    </div>
  </div>

  <div class="dir-badge">{label}</div>

  <div class="word-list">
    {#each words as w, i}
      <button class="word-row" class:alt={i % 2 !== 0} onclick={() => speakWord(w)} aria-label="Anhören: {germanWord(w)}">
        <span class="word-base">{germanWord(w)}</span>
        <span class="word-sep">→</span>
        <span class="word-target">{englishWord(w)}</span>
        {#if w.icon}
          <img class="word-icon" src="{base}icons/{w.icon}" alt={englishWord(w)}/>
        {/if}
      </button>
    {/each}
  </div>

  <div class="footer">
    <button class="btn-start" onclick={onStart}>Jetzt starten</button>
  </div>
</div>

<style>
  :global(body) { margin: 0; background: #FBFAF7; }

  .page {
    height: 100dvh;
    overflow: hidden;
    background: #FBFAF7;
    font-family: 'Inter', system-ui, sans-serif;
    display: flex;
    flex-direction: column;
    max-width: 600px;
    margin: 0 auto;
  }

  .header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 3.5rem 1.25rem 1rem;
    flex-shrink: 0;
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
    font-size: 1.1rem;
    font-weight: 700;
    color: #1F1D1A;
    line-height: 1.15;
    margin-top: 1px;
  }

  .dir-badge {
    align-self: flex-start;
    margin: 0 1.25rem 1rem;
    background: #F4F2EC;
    border: none;
    border-radius: 999px;
    padding: 4px 12px;
    font-family: ui-monospace, monospace;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.5px;
    color: #7A7269;
    flex-shrink: 0;
  }

  .word-list {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
    overscroll-behavior: contain;
    margin: 0 1.25rem;
    border: 1px solid #E8E3D9;
    border-radius: 16px;
    box-shadow: 0 1px 2px rgba(20,18,15,0.03);
    background: #FFFFFF;
  }

  .word-row {
    appearance: none;
    cursor: pointer;
    background: transparent;
    border: none;
    border-bottom: 1px solid #E8E3D9;
    width: 100%;
    text-align: left;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0.2rem 1rem;
    font-size: 0.9rem;
    font-weight: 500;
    font-family: inherit;
    transition: background 80ms;
  }

  .word-row:last-child { border-bottom: none; }
  .word-row.alt { background: #FBFAF7; }
  .word-row:active { background: #F0EDE6; }

  .word-base {
    flex: 1;
    color: #1F1D1A;
    font-weight: 600;
    min-width: 0;
  }

  .word-sep {
    color: #B0A89E;
    font-size: 0.8rem;
    flex-shrink: 0;
  }

  .word-target {
    flex: 1;
    color: #2F8F6E;
    font-weight: 500;
    min-width: 0;
  }

  .word-icon {
    width: 54px;
    height: 54px;
    object-fit: contain;
    flex-shrink: 0;
    border-radius: 8px;
  }

  .footer {
    padding: 1.25rem 1.25rem 2.5rem;
    flex-shrink: 0;
  }

  .btn-start {
    appearance: none;
    cursor: pointer;
    width: 100%;
    background: #2F8F6E;
    color: #FFFFFF;
    border: none;
    border-radius: 12px;
    padding: 0.95rem;
    font-family: inherit;
    font-weight: 600;
    font-size: 1rem;
    box-shadow: 0 1px 2px rgba(20,18,15,0.08), 0 4px 12px rgba(20,18,15,0.06);
    transition: transform 80ms, box-shadow 80ms;
  }

  .btn-start:active {
    transform: translateY(1px);
    box-shadow: 0 1px 2px rgba(20,18,15,0.10) inset;
  }
</style>
