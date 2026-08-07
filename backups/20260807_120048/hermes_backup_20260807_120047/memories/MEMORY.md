User: شاهرخ / ShahrokhVanguard. Telegram ID: 8848298889. Speaks Persian. Deploys on Railway (434MB). Main use: YouTube summarization. Likes anime Kingdom. Prefers technical terms with explanations. Descriptive bot names.
§
PITFALL: Railway /data = 434MB only. Clean .npm/_cacache, .cache, /tmp often. npm install fails with ENOSPC. Use Python packages over npm. Cloudflare blocked — use free alternatives like Gemini API.
§
Work style: Quality over speed for creative/research tasks. User corrected: "تو اصلا تحقیق کردی ؟ سرعتت خیلی بالا بود". Do deep research first for important work. For routine tasks: efficient, no unnecessary actions. Test before reporting. Prefers single-shot scripts. Wants step-by-step reports during long tasks.
§
Models: Mimo 2.5 (7B+72B, free on OpenRouter), Nemotron 3 Ultra (530B, main), DeepSeek V3, Qwen 2.5. Free Gemini: AI Studio (1500/day). Rate-limit: batch, delegate_task, wait between ops. Multi-instance Hermes → SQLite lock → misleading 'No space' error. Fix: restart from separate shell.
§
Preferences: PDF for docs. Quality > speed. Thorough research before writing. Batch proposals. No jailbreak examples. Wants step-by-step reports during long tasks. Prefers functional PDFs (not decorative). Proactively manages rate limits (delegate_task for heavy work).
§
Paths: Bot=/data/workspace/bots/summarizer/bot_final.py, SOUL=/data/.hermes/SOUL.md, AgentSoul=/data/workspace/soul-md. Hermes CLI: `source /opt/venv/bin/activate && hermes ...`. GitHub auth: `gh auth login --with-token`. cua-driver v0.19.0 at /data/.cua-driver/, Xvfb on :99.
§
Hermes file architecture: SOUL.md=identity, MEMORY.md=experience, USER.md=profile, TOOLS.md=tool philosophy+platform. skills/=acquired skills. AGENTS.md=per-project (not built yet). Strict: skills→skills/, experience→MEMORY.md, NOT TOOLS.md.
§
Model: Gemini Flash-Lite + Nemotron 3 Ultra via OpenRouter. Rate-limit rule: Use delegate_task for heavy work, avoid rapid sequential API calls, wait between intensive operations. Frustrated by repeated 429/503 errors — proactively manage rate limits.