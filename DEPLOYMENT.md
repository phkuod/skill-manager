# Production Deployment — 需要手動置換的 Config 清單

部署到 production 前，請依序檢查並置換下列位置。分成三類：

1. **必改（安全性）** — 不改會造成資安風險或服務無法啟動
2. **依環境改** — 視部署拓樸（單機 / 前後端分離 / 反向代理）決定
3. **調校用** — 依流量與硬體調整

---

## 1. 必改（安全性）

### 1.1 `SECRET_KEY`
- **檔案**：`backend/skill_market/settings.py:8`
- **現值**：`'dev-insecure-key-change-in-production'`（僅 dev fallback）
- **做法**：在 production 環境的 `.env`（或系統環境變數）設定 `SECRET_KEY=<隨機長字串>`。
  - 產生範例：`python -c "import secrets; print(secrets.token_urlsafe(50))"`
- **不要**將真實 `SECRET_KEY` commit 進 git。

### 1.2 `DEBUG`
- **檔案**：`backend/skill_market/settings.py:9`、`start.sh:42`、`ecosystem.config.cjs:15`
- **現值**：dev 預設 `True`
- **做法**：production 必須為 `False`。`./start.sh prod` 與 `ecosystem.config.cjs` 的 `env_production` 已強制 `DEBUG=False`，只需確認沒有被 `.env` 覆蓋。

### 1.3 `ALLOWED_HOSTS`
- **檔案**：`backend/skill_market/settings.py:10`、`start.sh:43`、`ecosystem.config.cjs:16`
- **現值**：`start.sh` 預設 `localhost,127.0.0.1`；`ecosystem.config.cjs` 同上
- **做法**：改為實際對外域名，例如 `ALLOWED_HOSTS=skills.example.com,www.skills.example.com`。
  - `ecosystem.config.cjs:16` 的字串需手動更新，或改由外部 env 注入。

### 1.4 `CORS_ALLOWED_ORIGINS`
- **檔案**：`backend/skills/middleware.py:20`
- **現值**：`'*'`（允許任何來源）
- **做法**：若 `/api/*` 會被其他 origin 的前端呼叫，設為單一 origin，例如
  `CORS_ALLOWED_ORIGINS=https://skills.example.com`。
  注意：瀏覽器的 `Access-Control-Allow-Origin` 不支援逗號分隔多值；若要多 origin 需改用反向代理或擴充 middleware。

---

## 2. 依環境改

### 2.1 `SKILL_REPO_PATH`
- **檔案**：`backend/skill_market/settings.py:43`、`start.sh:41,50`、`ecosystem.config.cjs:14`
- **現值**：預設為 repo 根目錄下的 `skill_repo/`
- **做法**：若 skill 資料夾放在專案外（例如 `/var/data/skill_repo`），設定 `SKILL_REPO_PATH=/var/data/skill_repo`。Watchdog 會監看此目錄。

### 2.2 前端 API base URL
- **檔案**：`frontend/config.js:19`
- **現值**：`window.API_BASE = '';`（同 origin）
- **做法**：
  - 前後端同 host → 維持空字串
  - 前端獨立部署（CDN / 不同網域） → `window.API_BASE = 'https://api.example.com';`
  - 反向代理把 API 掛在子路徑 → `window.API_BASE = '/backend';`
- 無 build step，改完直接重新部署靜態檔即可。

### 2.3 監聽 port / bind
- **檔案**：`start.sh:45,51`、`ecosystem.config.cjs:6`
- **現值**：`0.0.0.0:3000`
- **做法**：若 production 走反向代理（nginx / Caddy），通常改為 bind 內網或 unix socket，例如：
  ```
  --bind 127.0.0.1:3000          # 僅本機 proxy 進來
  --bind unix:/run/skill-market.sock
  ```
  同時更新 nginx upstream 指向對應位置。

---

## 3. 調校用

### 3.1 Gunicorn workers
- **檔案**：`start.sh:46`、`ecosystem.config.cjs:6`
- **現值**：`--workers 2`
- **做法**：建議依 CPU 核心數調整（常用公式 `2 * cores + 1`）。記憶體吃緊時可考慮 `--worker-class gthread --threads N`。

### 3.2 Static files
- `./start.sh` 每次啟動都跑 `collectstatic --noinput`（`start.sh:35`）。
- WhiteNoise 直接提供靜態檔；若 production 前方有 CDN，可改用 `STATIC_URL = 'https://cdn.example.com/static/'` 並把 `staticfiles/` 同步到 CDN。

### 3.3 In-memory catalog 的副作用
- `DATABASES` 使用 `sqlite3 :memory:`（`settings.py:27-32`），catalog 完全存在 process 記憶體。
- 多 worker 時每個 worker 各自持有一份 `_skills` dict；watcher 也是每個 worker 一個。這目前可接受（全部讀同一份檔案），但若改成可寫入資料，需要換掉這個架構。

---

## 4. 不建議用內建腳本上 production 的部分

- `ecosystem.config.cjs` 內的 `ALLOWED_HOSTS` / `SKILL_REPO_PATH` 是 hardcoded 字串；長期建議改成從系統 env 讀取，避免把環境特定值 commit 進 repo。
- `backend/e2e/conftest.py:9` 寫死 Linux Chromium 路徑（`/opt/pw-browsers/chromium-1194/chrome-linux/chrome`），僅限該測試環境，production 部署不受影響，但跑 E2E 測試前要先改此常數。

---

## 快速 checklist

部署前從上到下確認：

- [ ] `.env`（production 機器上）已設 `SECRET_KEY`
- [ ] `.env` 或啟動腳本已設 `ALLOWED_HOSTS=<實際域名>`
- [ ] `.env` 已設 `CORS_ALLOWED_ORIGINS=<前端 origin>`（若跨 origin）
- [ ] `.env` 已設 `SKILL_REPO_PATH=<實際路徑>`（若非預設）
- [ ] `frontend/config.js` 的 `window.API_BASE` 已依拓樸調整
- [ ] `ecosystem.config.cjs` 的 `env_production` 已改或改由外部注入
- [ ] gunicorn `--bind` 與 `--workers` 已依反向代理與硬體調整
- [ ] `DEBUG=False` 最終生效（`printenv DEBUG` 驗證）

---

## 5. 本機 Production 模擬（docker compose）

repo 根目錄附了 `docker-compose.yml`，可以在本機跑一份貼近 prod 的雙容器設定（gunicorn backend + 獨立 origin 的靜態 frontend），用來驗 CORS / `API_BASE` / `DEBUG=False` 的行為，**不適合做為實際部署用的 compose**（沒有 traefik、沒有 healthcheck、沒有 logging driver）。

```bash
# 1. 在 repo 根目錄建立 .env，設定 SECRET_KEY
echo "SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(50))')" > .env

# 2. 啟動
docker compose up -d --build

# 3. 驗證
curl http://localhost:3000/api/health        # backend (gunicorn)
open http://localhost:8080                   # frontend (不同 origin)

# 4. 收尾
docker compose down
```

`docker-compose.yml` 內的 `ALLOWED_HOSTS` / `CORS_ALLOWED_ORIGINS` / `SKILL_REPO_PATH` 都是模擬值；改投到 traefik 環境時，請把它們搬到該環境自己的 env 機制（例如 docker swarm secrets、k8s ConfigMap、或部署平台的環境變數）。

`frontend-server.py` 是極簡 Python 靜態伺服器（含 SPA fallback 與 `/static/*` alias），只給這份模擬用。Production 環境 frontend 的服務方式由 traefik 指向的實際 host 決定。
