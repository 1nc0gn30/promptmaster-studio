# PromptMaster Studio — Product Reel Brief

This is the creative brief for the short, silent product reel that plays in the hero of
https://promptmaster-studio.netlify.app. The rendered files live in `public/media/`:

| File | Purpose |
| --- | --- |
| `public/media/promptmaster-reel.mp4` | H.264 MP4, primary source (all browsers) |
| `public/media/promptmaster-reel.webm` | VP9 WebM, optional smaller source |
| `public/media/promptmaster-reel-poster.jpg` | First-frame poster, also shown when the visitor prefers reduced motion |

The hero `<video>` is `autoplay muted loop playsinline preload="metadata"` inside a 16:9 frame,
so the reel must read well **without sound** and loop cleanly.

---

## Specs

- 16:9, 1920×1080 (a 1280×720 web encode is fine), 24–30 fps, 12–20 seconds, seamless loop.
- No audio track needed on the web encode (the player is always muted).
- Keep the MP4 under ~4 MB and the poster under ~150 KB so the hero stays fast.
- Every claim on screen must be true for the product as shipped (no user counts, ratings or scarcity).

## Brand

- Background `#07090E`, surface `#0E121B`, emerald `#10B981`, indigo `#6366F1`.
- Type: Syne 800 for punchlines, Space Grotesk for UI labels, Fira Code for prompt text.
- The ⚡ gradient tile logo anchors the opening and the end card.

## Storyboard (on-screen copy)

1. **Hook** — a messy, real-looking prompt types into the editor.
   Text: "Rough prompt in."
2. **Lint** — linter issues light up (negative constraint, vague directive, injection risk) and the
   quality score updates live.
   Text: "Lint & score instantly — free."
3. **Optimize** — target tabs switch between Claude XML, OpenAI, Gemini and CoT; the output panel
   fills with the restructured prompt.
   Text: "Production prompt out."
4. **Privacy** — a short beat on the client-side engine.
   Text: "Runs in your browser. Prompts never leave your device."
5. **Offer** — the Pro unlock card.
   Text: "Pro: $19 once · 30-day refund."
6. **End card** — logo lockup and URL.
   Text: "PromptMaster Studio — promptmaster-studio.netlify.app"
