# 【AI-PMO Gitea トークンセットアップ指示】

## 前提

- Gitea が `http://localhost:3000` で起動済み
- Gitea 管理者アカウント作成済み
- 発行したアクセストークンを手元に用意している

---

## 作業内容

`/Users/nhigashira/Documents/dev/ai-pmo/.env` ファイルを編集して、Gitea の認証情報を設定する。

---

## ステップ 1: .env を編集する

`/Users/nhigashira/Documents/dev/ai-pmo/.env` を開き、以下の 2 行を更新する。

### 変更前

```
GITEA_ADMIN_TOKEN=
GITEA_WEBHOOK_SECRET=87af6297c8aa60e15ff87793f8286e16
```

### 変更後

```
GITEA_ADMIN_TOKEN=<ここに Gitea で発行した管理者アクセストークンを貼り付ける>
GITEA_WEBHOOK_SECRET=87af6297c8aa60e15ff87793f8286e16
```

※ `GITEA_WEBHOOK_SECRET` はすでにランダム生成済み。変更不要。  
※ Gitea の Webhook 設定画面のシークレット欄にも同じ値 `87af6297c8aa60e15ff87793f8286e16` を入力する。

---

## ステップ 2: バックエンドを再起動する

```bash
# プロジェクトルートから実行
./stop.sh
./start.sh
```

または FastAPI だけ再起動する場合:

```bash
cd /Users/nhigashira/Documents/dev/ai-pmo/backend
pkill -f "uvicorn" 2>/dev/null || true
source venv/bin/activate
python run.py &
```

---

## ステップ 3: 設定の動作確認

以下の curl コマンドで Gitea 連携が有効になったことを確認する。  
（`<JWT_TOKEN>` は `/api/v1/auth/login` で取得したトークン）

```bash
curl -s http://localhost:8008/api/v1/gitea/repos \
  -H "Authorization: Bearer <JWT_TOKEN>" | python3 -m json.tool
```

**期待レスポンス（トークン設定後）:**

```json
{
  "configured": true,
  "repos": [...]
}
```

`"configured": true` になれば設定完了。

---

## ステップ 4: Gitea Webhook を登録する

Gitea 上の各リポジトリで以下の設定を行う。

1. リポジトリ → 設定 → Webhook → 追加 → Gitea
2. 設定値:
   - **URL**: `http://host.docker.internal:8008/api/v1/webhooks/gitea`
   - **シークレット**: `87af6297c8aa60e15ff87793f8286e16`
   - **トリガー**: プッシュ ＋ プルリクエスト
3. 保存後、「テスト配信」ボタンで HTTP 200 が返れば完了。

---

## 注意事項

- `.env` ファイルは `.gitignore` で除外済みのため、Git にコミットされない。
- `.env.example` は安全な値（トークンなし）で Git 管理されており、別マシンでのセットアップ手順として機能する。
- GITEA_WEBHOOK_SECRET は Gitea Webhook 設定と必ず一致させること（不一致時は 403 エラー）。
