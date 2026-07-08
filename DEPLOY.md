# Deploy — reflect-revise

**TL;DR:** a public URL in ~5 minutes on Streamlit Community Cloud (free). Works with **no API key** (offline deterministic reviser genuinely lowers the score each pass); add `ANTHROPIC_API_KEY` for a live Claude author+critic.

## 0. Prerequisites
- GitHub account + a Streamlit Community Cloud account ([share.streamlit.io](https://share.streamlit.io), sign in with GitHub — free).
- *(Optional, live mode only)* an Anthropic API key.

## 1. Own public GitHub repo
```bash
cd "06_projects/reflect-revise"
git init && git add . && git commit -m "reflect-revise: self-critiquing reflection agent with score-deltas"
gh repo create reflect-revise --public --source=. --push
```

## 2. Deploy on Streamlit Community Cloud
1. [share.streamlit.io](https://share.streamlit.io) → **Create app** → **Deploy from GitHub**.
2. Repo `<you>/reflect-revise` · Branch `main` · **Main file path: `app.py`**.
3. *(Optional, live author+critic)* **Advanced settings → Secrets**:
   ```toml
   ANTHROPIC_API_KEY="sk-ant-..."
   ```
   (Streamlit exposes secrets as env vars; the app's `os.getenv` reads it.)
4. **Deploy** → permanent URL `https://<app>.streamlit.app`.

## What a reviewer sees
Pick a heavy-slop seed draft → watch the **SLOP INDEX fall across passes on a live curve** (e.g. **239 → 98 → 5**) with the score-delta and cost per pass, plus side-by-side draft diffs. Pick the `04_uniform_halt` draft to see the loop **correctly stop on no-progress** — reflection gated on measured gain, not run blindly.

## Run locally
```bash
pip install -r requirements.txt
python eval/curve.py           # prints the improvement curve, writes scorecard.json
streamlit run app.py
```

## Alternative host: Hugging Face Spaces (SDK: Streamlit). Add the key under **Settings → Variables and secrets** for live mode.

---
*Christian Macion — AI / Agent Engineer.*
