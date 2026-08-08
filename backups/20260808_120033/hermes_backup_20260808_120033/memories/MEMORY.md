User: شاهرخ / ShahrokhVanguard (ID: 8848298889). Prefers technical terms, Persian language, quality over speed, and surgical disk management (Railway 434MB limit). Manages multiple Railway instances; uses CLI-based cleanup for disk space. Needs proactive cleanup strategies for small-disk environments.
§
PITFALL: Railway /data = 434MB. Requires frequent manual cleanup of /data/.hermes/ (logs, cache, state-snapshots, terminal-output) and /tmp. Use Python over npm. Avoid heavy packages. Handle rate-limits (429/503) proactively with delegate_task.
§
Work style: Quality over speed for creative/research tasks. User corrected: "تو اصلا تحقیق کردی ؟ سرعتت خیلی بالا بود". Do deep research first for important work. For routine tasks: efficient, no unnecessary actions. Test before reporting. Prefers single-shot scripts. Wants step-by-step reports during long tasks.
§
Hermes file architecture: SOUL.md=identity, MEMORY.md=experience, USER.md=profile, TOOLS.md=tool philosophy+platform. skills/=acquired skills. AGENTS.md=per-project (not built yet). Strict: skills→skills/, experience→MEMORY.md, NOT TOOLS.md.
§
User is a 12th grade experimental math student (ریاضی دوازدهم تجربی) with final exam tomorrow.
§
User operates Railway exclusively from mobile — no computer access. Railway Console on mobile lacks Enter key; uses browser workaround.
§
User has 3 Telegram bots: 1) @videoshahbot (YouTube summarization, primary), 2) Hermes on Railway (miraculous-cat project), 3) One inactive bot needing upgrade/activation.
§
Railway SSH to containers hangs when co-located Hermes process is running. Use GraphQL API instead (https://backboard.railway.com/graphql/v2). Key mutations: deploymentRedeploy, serviceInstanceUpdate (preDeployCommand for auto-cleanup), variableUpsert. serviceInstanceUpdate returns Boolean! — no selection set. Account token (UUID) works for GraphQL but NOT SSH. Mobile Railway Console has no Enter key — GraphQL API is the workaround.