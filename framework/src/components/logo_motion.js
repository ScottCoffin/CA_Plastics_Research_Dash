// Plastiverse Live footer logo animation (LOGO-1). The footer's static poster stays in place until the
// MP4 can replace it: only where the browser plays video/mp4, only once the logo is within 200 px of
// the viewport, and never with reduced motion. The MP4 is owner-supplied (made by
// src/create_plastiverse_animation.py) and copied to site/assets/landing/ by build_landing_assets.py.
import {siteRoot} from "./atlas.js";

const SIZE = 282; // px, the footer logo's box (.plv-flogo in landing_story.css)
const NEAR = "200px"; // start loading when the logo is this close to the viewport
const PAUSE_ICON = '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" focusable="false"><path d="M4 3h2.5v10H4zM9.5 3H12v10H9.5z" fill="currentColor"/></svg>';
const PLAY_ICON = '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" focusable="false"><path d="M5 3l8 5-8 5z" fill="currentColor"/></svg>';

const canPlayMp4 = () => document.createElement("video").canPlayType("video/mp4") !== "";

// Swaps the footer's <img class="plv-flogo"> for the looping MP4 (call once per page).
export function mountLogoMotion(footer) {
  const img = footer?.querySelector("img.plv-flogo");
  const motion = matchMedia("(prefers-reduced-motion: reduce)");
  if (!img || motion.matches || !canPlayMp4()) return;

  let near = null;
  let watch = null;
  let wrap = null;
  let video = null;
  let toggle = null;
  let userPaused = false;

  // Back to the static image: observers and listeners stop, the MP4 is paused and dropped.
  const showStatic = () => {
    near?.disconnect();
    watch?.disconnect();
    motion.removeEventListener("change", onMotion);
    video?.pause();
    if (wrap?.isConnected) wrap.replaceWith(img);
  };
  const onMotion = () => {
    if (motion.matches) showStatic();
  };
  const playVideo = () => {
    const started = video.play();
    // play() rejects with AbortError when a pause() arrives first; that is not a failure.
    started?.catch((error) => {
      if (error.name !== "AbortError") showStatic();
    });
  };
  const showToggle = () => {
    toggle.innerHTML = userPaused ? PLAY_ICON : PAUSE_ICON;
    toggle.setAttribute("aria-label", userPaused ? "Play logo animation" : "Pause logo animation");
    toggle.setAttribute("aria-pressed", String(userPaused));
  };
  const onToggle = () => {
    userPaused = !userPaused;
    if (userPaused) video.pause();
    else playVideo();
    showToggle();
  };

  const attach = () => {
    video = document.createElement("video");
    video.className = "plv-flogo";
    video.muted = true;
    video.setAttribute("muted", "");
    video.loop = true;
    video.playsInline = true;
    video.preload = "auto";
    video.width = SIZE;
    video.height = SIZE;
    video.poster = img.currentSrc || img.src;
    video.setAttribute("aria-hidden", "true");
    video.addEventListener("error", showStatic);
    video.src = new URL("assets/landing/plastiverse_live.mp4", siteRoot()).href;

    // The alt text moves into a visually hidden role="img" span. The button is a sibling, not a
    // child, because children of role="img" are presentational and would hide it from assistive tech.
    const alt = document.createElement("span");
    alt.className = "sr-only";
    alt.setAttribute("role", "img");
    alt.setAttribute("aria-label", img.alt);
    alt.textContent = img.alt;
    toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "plv-flogo-toggle";
    toggle.addEventListener("click", onToggle);
    wrap = document.createElement("span");
    wrap.className = "plv-flogo-wrap";
    wrap.append(alt, video, toggle);
    img.replaceWith(wrap);
    showToggle();

    // Pause when the footer scrolls out of view; resume when it returns unless the user paused.
    watch = new IntersectionObserver((entries) => {
      const [entry] = entries;
      if (!entry || userPaused) return;
      if (entry.isIntersecting) playVideo();
      else video.pause();
    });
    watch.observe(wrap);
    playVideo();
  };

  near = new IntersectionObserver(
    (entries) => {
      if (!entries[0].isIntersecting) return;
      near.disconnect();
      attach();
    },
    {rootMargin: NEAR}
  );
  near.observe(img);
  motion.addEventListener("change", onMotion);
}

// Intro logo (LAND-2, .plv-intro in index.md): the MP4 plays once, muted, over the poster. Its last
// frames are black, so when it ends it fades out and the poster (the logo) shows. It pauses while the
// intro is off screen and stays ended until the viewer replays it. Reduced motion, or a browser that
// cannot play MP4, keeps the poster (the intro gets class "static").
const INTRO_HOLD_AT = 5.6; // s; the 7.0 s MP4 shows the full logo from ~5.5 s, then fades to black

export function mountIntroLogo(intro) {
  const img = intro?.querySelector("img.plv-ilogo");
  const motion = matchMedia("(prefers-reduced-motion: reduce)");
  if (!img || motion.matches || !canPlayMp4()) {
    intro?.classList.add("static");
    return;
  }

  let watch = null;
  let video = null;
  let toggle = null;
  let userPaused = false;
  let finished = false;

  // Back to the static poster: the observer and listener stop, the MP4 is paused and removed.
  const showStatic = () => {
    watch?.disconnect();
    motion.removeEventListener("change", onMotion);
    video?.pause();
    video?.remove();
    toggle?.remove();
    video = null;
    toggle = null;
    intro.classList.add("static");
  };
  const onMotion = () => {
    if (motion.matches) showStatic();
  };
  const playVideo = () => {
    const started = video.play();
    // play() rejects with AbortError when a pause() arrives first; that is not a failure.
    started?.catch((error) => {
      if (error.name !== "AbortError") showStatic();
    });
  };
  const showToggle = () => {
    const label = finished ? "Replay logo animation" : userPaused ? "Play logo animation" : "Pause logo animation";
    toggle.innerHTML = finished || userPaused ? PLAY_ICON : PAUSE_ICON;
    // The label names the next action, so no aria-pressed (a toggle's name must not change).
    toggle.setAttribute("aria-label", label);
  };
  const onToggle = () => {
    if (finished) {
      finished = false;
      userPaused = false;
      video.currentTime = 0;
      playVideo();
    } else {
      userPaused = !userPaused;
      if (userPaused) video.pause();
      else playVideo();
    }
    showToggle();
  };

  video = document.createElement("video");
  video.className = "plv-ilogo-video";
  video.muted = true;
  video.setAttribute("muted", "");
  video.playsInline = true;
  video.autoplay = true;
  video.preload = "auto";
  video.setAttribute("aria-hidden", "true");
  video.addEventListener("playing", () => video.classList.add("playing"));
  // The MP4's last ~1.2 s fade the logo to black; stop just before that and let the poster (the
  // same logo still, revealed underneath) show, so the intro holds on the logo.
  const finish = () => {
    if (finished) return;
    finished = true;
    video.pause();
    video.classList.remove("playing");
    showToggle();
  };
  video.addEventListener("timeupdate", () => {
    if (video.currentTime >= INTRO_HOLD_AT) finish();
  });
  video.addEventListener("ended", finish);
  video.addEventListener("error", showStatic);
  video.src = new URL("assets/landing/plastiverse_live.mp4", siteRoot()).href;

  toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "plv-ilogo-toggle";
  toggle.addEventListener("click", onToggle);
  img.after(video, toggle);
  showToggle();

  // Pause while the intro is off screen; resume on return unless the viewer paused or it ended.
  watch = new IntersectionObserver((entries) => {
    const [entry] = entries;
    if (!entry) return;
    if (!entry.isIntersecting) video.pause();
    else if (!userPaused && !finished) playVideo();
  });
  watch.observe(intro);
  motion.addEventListener("change", onMotion);
}
