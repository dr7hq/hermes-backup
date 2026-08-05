User: شاهرخ / ShahrokhVanguard. Telegram ID: 8848298889. Speaks Persian. Deploys on Railway (434MB volume). Admin of "AI Advanced" (chat_id: -1003957762420). Main use: YouTube summarization (CRITICAL). Likes anime Kingdom. Prefers technical terms with explanations. Chose symbolic nickname "ShahrokhVanguard" (Vanguard = پیشگام). Prefers descriptive/clear bot names (like "اطلاعات ویدئو و لینک") over creative ones.
§
PITFALL: Railway /data = 434MB only. Clean .npm/_cacache, .cache, /tmp often. npm install fails with ENOSPC. Use Python packages over npm. Cloudflare blocked — use free alternatives like Gemini API.
§
Work style: Efficient, no unnecessary actions. Use web scraping for public channels. User frustrated by repeated failures — test before reporting. Prefers thoroughness over speed ("به اندازه کافی وقت داری نیازی به سریع جواب دادن نیست"). Prefers single-shot scripts for multi-step auth flows.
§
Project: @videoshahbot on Railway. Nemotron 3 Ultra 550B via OpenRouter (free). Features: YouTube info extraction, transcript extraction (yt-dlp), AI summarization, web extraction (article detection), Persian translation, inline buttons (translate/download/copy), smart splitting (3500 chars). Issues: timeout for long pages, message splitting broken, Conflict errors, Vision needed, translation callback broken, web_content_store not persistent.
§
Key files: /data/workspace/bots/summarizer/bot_final.py (main), /data/workspace/summarizer_bot.db (SQLite), /data/workspace/backup/backup.sh (GitHub backup). Cron: a56c3b761601 every 12h to dr7hq/hermes-backup. OpenRouter: «REDACTED_OPENROUTER_KEY» (free models only). GitHub backup: «REDACTED_GITHUB_TOKEN».
§
Monitoring: User prefers in-code error notification (webhook-style) over log-monitoring cron jobs. Gateway logs NOT useful — only bot logs matter. For Railway bots: add send_error_notification() sending errors to admin's Telegram DM in real-time. Cron job 0071f4bda6ff (log check every 6h) is not useful — consider removing.