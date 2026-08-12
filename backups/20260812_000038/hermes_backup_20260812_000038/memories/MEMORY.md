User: ShahrokhVanguard (8848298889). Persian. Quality>speed. Railway 434MB. SSH→GraphQL (account token UUID). Mobile-only. MiMo v2.5 for Persian.
§
PITFALL: Railway /data = 434MB. Requires frequent manual cleanup of /data/.hermes/ (logs, cache, state-snapshots, terminal-output) and /tmp. Use Python over npm. Avoid heavy packages. Handle rate-limits (429/503) proactively with delegate_task.
§
Work style: Quality over speed for creative/research tasks. User corrected: "تو اصلا تحقیق کردی ؟ سرعتت خیلی بالا بود". Do deep research first for important work. For routine tasks: efficient, no unnecessary actions. Test before reporting. Prefers single-shot scripts. Wants step-by-step reports during long tasks.
§
Hermes file architecture: SOUL.md=identity, MEMORY.md=experience, USER.md=profile, TOOLS.md=tool philosophy+platform. skills/=acquired skills. AGENTS.md=per-project (not built yet). Strict: skills→skills/, experience→MEMORY.md, NOT TOOLS.md.
§
Railway SSH to containers hangs when co-located Hermes process is running. Use GraphQL API instead (https://backboard.railway.com/graphql/v2). Key mutations: deploymentRedeploy, serviceInstanceUpdate (preDeployCommand for auto-cleanup), variableUpsert. serviceInstanceUpdate returns Boolean! — no selection set. Account token (UUID) works for GraphQL but NOT SSH. Mobile Railway Console has no Enter key — GraphQL API is the workaround.
§
User wants ROUTER pattern for skill loading (like MasterMind) - dynamically load only needed skills
§
User rejected purely action-only SOUL.md - wants balance of philosophy + operational rules
§
model_router.py created but NOT connected - wait for user instruction
§
3 bots: @Ali7rezabot (8713269492, Hermes here, local), @Shg4lbot (8629792707, Assistant on Railway, memory 88% full), @videoshahbot (8633608471, 'اطلاعات لینک', runs LOCALLY: cd /data/workspace/bots/summarizer && python3 bot_final.py). model_router.py NOT connected.
§
Railway API: Token=6291e864-21e1-4967-8ce6-437f7df93033, Project=miraculous-cat (fde983f6). GraphQL works for deployments/services/variables. Account token (UUID) works for GraphQL but NOT SSH. Mobile Railway Console has no Enter key — GraphQL API is the workaround.