User: شاهرخ / ShahrokhVanguard (ID: 8848298889). Prefers technical terms, Persian language, quality over speed, and surgical disk management (Railway 434MB limit). Manages multiple Railway instances; uses CLI-based cleanup for disk space. Needs proactive cleanup strategies for small-disk environments.
§
PITFALL: Railway /data = 434MB. Requires frequent manual cleanup of /data/.hermes/ (logs, cache, state-snapshots, terminal-output) and /tmp. Use Python over npm. Avoid heavy packages. Handle rate-limits (429/503) proactively with delegate_task.
§
Work style: Quality over speed for creative/research tasks. User corrected: "تو اصلا تحقیق کردی ؟ سرعتت خیلی بالا بود". Do deep research first for important work. For routine tasks: efficient, no unnecessary actions. Test before reporting. Prefers single-shot scripts. Wants step-by-step reports during long tasks.
§
Models: Nemotron 3 Ultra (530B, main free on OpenRouter), Laguna S 2.1 (free), North Mini Code (free), Mimo 2.5 (free), Ling 3.0 Tiny (free). Big-pickle does NOT exist. LongCat 2.0 & DeepSeek V4 Flash are paid. Rate-limit: delegate_task for heavy work.
§
User prefers simple, functional PDFs — not decorative. Hermes capabilities doc translated to MD. Skills list from PDF added. Rate-limit errors (429/503) frustrate user — proactively use delegate_task and wait between heavy ops.
§
Paths: Bot=/data/workspace/bots/summarizer/bot_final.py, SOUL=/data/.hermes/SOUL.md, AgentSoul=/data/workspace/soul-md. Hermes CLI: `source /opt/venv/bin/activate && hermes ...`. GitHub auth: `gh auth login --with-token`. cua-driver v0.19.0 at /data/.cua-driver/, Xvfb on :99.
§
Hermes file architecture: SOUL.md=identity, MEMORY.md=experience, USER.md=profile, TOOLS.md=tool philosophy+platform. skills/=acquired skills. AGENTS.md=per-project (not built yet). Strict: skills→skills/, experience→MEMORY.md, NOT TOOLS.md.