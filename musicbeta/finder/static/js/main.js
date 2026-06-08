// Smooth navbar scroll effect
let lastScroll = 0;
const navbar = document.querySelector('.navbar');
const loadingOverlay = document.getElementById('pageLoadingOverlay');

function showLoadingOverlay(message) {
  if (!loadingOverlay) {
    return;
  }

  const textEl = loadingOverlay.querySelector('.page-loading-text');
  if (textEl && message) {
    textEl.textContent = message;
  }

  loadingOverlay.hidden = false;
  loadingOverlay.setAttribute('aria-hidden', 'false');
}

function hideLoadingOverlay() {
  if (!loadingOverlay) {
    return;
  }

  loadingOverlay.hidden = true;
  loadingOverlay.setAttribute('aria-hidden', 'true');
}

window.showLoadingOverlay = showLoadingOverlay;
window.hideLoadingOverlay = hideLoadingOverlay;

window.addEventListener('scroll', () => {
  const currentScroll = window.pageYOffset;
  
  if (currentScroll > 100) {
    navbar.classList.add('scrolled');
  } else {
    navbar.classList.remove('scrolled');
  }
  
  lastScroll = currentScroll;
});

// Add smooth scroll only for real in-page section links.
// Ignore Bootstrap toggles (modals/dropdowns) and plain '#' links.
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function (e) {
    const href = this.getAttribute('href');
    const isBootstrapToggle = this.hasAttribute('data-bs-toggle');

    if (!href || href === '#') {
      e.preventDefault();
      return;
    }

    if (isBootstrapToggle) {
      return;
    }

    let target = null;
    try {
      target = document.querySelector(href);
    } catch (err) {
      return;
    }

    if (target) {
      e.preventDefault();
      target.scrollIntoView({
        behavior: 'smooth',
        block: 'start'
      });
    }
  });
});

// Intersection Observer for fade-in animations (without blocking interaction)
const observerOptions = {
  threshold: 0.1,
  rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.style.opacity = '1';
      entry.target.style.transform = 'translateY(0)';
    }
  });
}, observerOptions);

// Observe all cards for animation
document.addEventListener('DOMContentLoaded', () => {
  hideLoadingOverlay();

  const cards = document.querySelectorAll('.card');
  cards.forEach(card => {
    card.style.opacity = '0';
    card.style.transform = 'translateY(30px)';
    card.style.transition = 'all 0.6s cubic-bezier(0.4, 0, 0.2, 1)';
    observer.observe(card);
  });

  document.querySelectorAll('form').forEach((form) => {
    if (form.dataset.noLoading === 'true') {
      return;
    }

    form.addEventListener('submit', () => {
      const loadingMessage = form.dataset.loadingText || 'Loading, please wait...';
      showLoadingOverlay(loadingMessage);
    });
  });

  document.querySelectorAll('a[href]').forEach((anchor) => {
    const href = anchor.getAttribute('href') || '';
    const isInternalNavigation = href && !href.startsWith('#') && !href.startsWith('mailto:') && !href.startsWith('tel:') && !anchor.hasAttribute('download') && anchor.getAttribute('target') !== '_blank';
    const isBootstrapToggle = anchor.hasAttribute('data-bs-toggle');

    if (!isInternalNavigation || isBootstrapToggle) {
      return;
    }

    anchor.addEventListener('click', () => {
      showLoadingOverlay(anchor.dataset.loadingText || 'Loading page...');
    });
  });
  
  // No custom interception for modal buttons — let Bootstrap handle clicks
});

// Global mini player with queue support
document.addEventListener('DOMContentLoaded', () => {
  const miniPlayer = document.getElementById('miniPlayer');
  const globalAudio = document.getElementById('globalAudioPlayer');
  const titleEl = document.getElementById('miniPlayerTitle');
  const metaEl = document.getElementById('miniPlayerMeta');
  const queueCountEl = document.getElementById('miniQueueCount');
  const playPauseBtn = document.getElementById('miniPlayPauseBtn');
  const nextBtn = document.getElementById('miniNextBtn');
  const prevBtn = document.getElementById('miniPrevBtn');
  const closeBtn = document.getElementById('miniCloseBtn');

  if (!miniPlayer || !globalAudio) {
    return;
  }

  const queue = [];
  const history = [];
  let currentTrack = null;
  let playerDismissed = false;

  const defaultTitle = 'No track selected';
  const defaultMeta = 'Use Play or Queue from your playlist songs.';

  function pauseInlineAudioPlayers() {
    document.querySelectorAll('audio').forEach((audioEl) => {
      if (audioEl !== globalAudio) {
        audioEl.pause();
      }
    });
  }

  function setBufferingState(isBuffering) {
    miniPlayer.classList.toggle('is-buffering', isBuffering);
    const metaText = isBuffering ? 'Buffering music...' : (currentTrack?.artist || defaultMeta);
    metaEl.textContent = metaText;
  }

  function updateQueueCount() {
    queueCountEl.textContent = `Queue: ${queue.length}`;
  }

  function setTrack(track) {
    if (!track || !track.url) return;
    if (currentTrack) {
      history.push(currentTrack);
    }
    pauseInlineAudioPlayers();
    playerDismissed = false;
    currentTrack = track;
    globalAudio.src = track.url;
    titleEl.textContent = track.title || 'Unknown title';
    metaEl.textContent = track.artist || 'Unknown artist';
    miniPlayer.hidden = false;
    setBufferingState(true);
    globalAudio.play().catch(() => {});
  }

  function closePlayer() {
    playerDismissed = true;
    globalAudio.pause();
    globalAudio.removeAttribute('src');
    globalAudio.load();
    currentTrack = null;
    queue.length = 0;
    history.length = 0;
    titleEl.textContent = defaultTitle;
    metaEl.textContent = defaultMeta;
    miniPlayer.hidden = true;
    miniPlayer.classList.remove('is-buffering');
    updateQueueCount();
  }

  function playNext() {
    const next = queue.shift();
    updateQueueCount();
    if (next) {
      setTrack(next);
    }
  }

  function playPrev() {
    const prev = history.pop();
    if (prev) {
      currentTrack = prev;
      globalAudio.src = prev.url;
      titleEl.textContent = prev.title || 'Unknown title';
      metaEl.textContent = prev.artist || 'Unknown artist';
      miniPlayer.hidden = false;
      setBufferingState(true);
      globalAudio.play().catch(() => {});
    }
  }

  document.querySelectorAll('[data-mini-player-track="true"][data-queue-title]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const track = {
        title: btn.dataset.queueTitle,
        artist: btn.dataset.queueArtist,
        url: btn.dataset.queueUrl,
      };
      queue.push(track);
      updateQueueCount();
      if (!currentTrack) {
        playNext();
      }
    });
  });

  document.querySelectorAll('[data-mini-player-track="true"][data-play-now-title]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const track = {
        title: btn.dataset.playNowTitle,
        artist: btn.dataset.playNowArtist,
        url: btn.dataset.playNowUrl,
      };
      setTrack(track);
    });
  });

  playPauseBtn?.addEventListener('click', () => {
    if (globalAudio.paused) {
      if (globalAudio.src) {
        playerDismissed = false;
      }
      globalAudio.play().catch(() => {});
    } else {
      globalAudio.pause();
    }
  });

  nextBtn?.addEventListener('click', playNext);
  prevBtn?.addEventListener('click', playPrev);
  closeBtn?.addEventListener('click', closePlayer);
  document.addEventListener('click', (event) => {
    if (event.target.closest('#miniCloseBtn')) {
      closePlayer();
    }
  });

  globalAudio.addEventListener('ended', playNext);
  globalAudio.addEventListener('play', () => {
    pauseInlineAudioPlayers();
    setBufferingState(false);
    playPauseBtn.innerHTML = '<i class="fas fa-pause"></i>';
    if (!playerDismissed) {
      miniPlayer.hidden = false;
    }
  });
  globalAudio.addEventListener('pause', () => {
    if (!globalAudio.seeking) {
      setBufferingState(false);
    }
    playPauseBtn.innerHTML = '<i class="fas fa-play"></i>';
  });
  globalAudio.addEventListener('waiting', () => setBufferingState(true));
  globalAudio.addEventListener('stalled', () => setBufferingState(true));
  globalAudio.addEventListener('canplay', () => setBufferingState(false));
  globalAudio.addEventListener('canplaythrough', () => setBufferingState(false));

  updateQueueCount();
});
