User: ShahrokhVanguard (8848298889). Persian. Quality>speed. Railway 434MB. Multiple Railway instances. SSH→GraphQL API workaround. Prefers MiMo v2.5 for Persian. Simple PDFs. Wants ROUTER pattern. Execute First rule.
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
User prefers MiMo v2.5 over Nemotron 3 Ultra for Persian/Arabic content
§
User wants simple functional PDFs - not decorative/showy
§
TG sticker creation via API (`addStickerToSet`) fails with "can't parse sticker JSON object" for PNG and WEBP via curl/requests/python-telegram-bot. Use @Stickers bot for manual creation instead.