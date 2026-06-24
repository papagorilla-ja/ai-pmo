# Gitea セットアップ手順書

対象: AI-PMO Gitea連携  
最終更新: 2026-06-24

---

## 目次

1. [Gitea の起動](#1-gitea-の起動)
2. [初回セットアップ（管理者アカウント作成）](#2-初回セットアップ管理者アカウント作成)
3. [管理者アクセストークンの発行](#3-管理者アクセストークンの発行)
4. [.env への設定とバックエンド再起動](#4-env-への設定とバックエンド再起動)
5. [リポジトリの作成](#5-リポジトリの作成)
6. [Webhook の登録](#6-webhook-の登録)
7. [動作確認](#7-動作確認)
8. [コミットメッセージ記法リファレンス](#8-コミットメッセージ記法リファレンス)
9. [トラブルシューティング](#9-トラブルシューティング)

---

## 1. Gitea の起動

プロジェクトルートで以下を実行する。

```bash
cd /Users/nhigashira/Documents/dev/ai-pmo
docker compose up gitea -d
```

起動確認:

```bash
docker ps | grep gitea
# 出力例: ai_pmo_gitea   Up 10 seconds   0.0.0.0:3000->3000/tcp
```

ブラウザで `http://localhost:3000` にアクセスし、Gitea のページが表示されれば起動完了。

---

## 2. 初回セットアップ（管理者アカウント作成）

初回アクセス時に初期設定画面が表示される。

1. `http://localhost:3000` を開く
2. 以下の設定はそのままで「Gitea をインストール」をクリック:
   - データベース種類: SQLite3
   - サイトURL: `http://localhost:3000/`
3. **管理者アカウントの設定**（ページ下部）:
   - ユーザー名: 任意（例: `admin`）
   - パスワード: 任意（例: `admin1234`）
   - メールアドレス: 任意（例: `admin@example.com`）
4. 「Gitea をインストール」ボタンをクリック

> 初期設定画面が表示されない場合（既にインストール済み）は手順 3 へ進む。

---

## 3. 管理者アクセストークンの発行

トークンは **画面を閉じると二度と表示されない** ため、発行後すぐに `.env` へ保存すること。

1. 右上のアバターアイコン → **設定（Settings）** をクリック
2. 左メニュー → **アプリケーション（Applications）** をクリック
3. 「アクセストークンを生成」セクションで以下を入力:
   - **トークン名**: `ai-pmo-admin`
   - **権限（スコープ）**:

     | スコープ | 権限 |
     |---|---|
     | `issue` | Read / Write |
     | `repository` | Read |
     | `user` | Read |

4. 「トークンを生成」ボタンをクリック
5. 表示されたトークン文字列（例: `0528c45a7d1d9bf6...`）をコピーしておく

---

## 4. .env への設定とバックエンド再起動

### 4.1 .env を編集する

`/Users/nhigashira/Documents/dev/ai-pmo/.env` を開き、以下を設定する:

```
GITEA_ADMIN_TOKEN=<手順3でコピーしたトークン>
GITEA_WEBHOOK_SECRET=87af6297c8aa60e15ff87793f8286e16
```

> `GITEA_WEBHOOK_SECRET` は初期生成済み。変更する場合は手順6のWebhook設定と必ず一致させること。

### 4.2 バックエンドを再起動する

```bash
# バックエンドプロセスを停止
kill $(ps aux | grep "run.py" | grep -v grep | awk '{print $2}')

# 再起動
cd /Users/nhigashira/Documents/dev/ai-pmo/backend
source venv/bin/activate
python run.py &
```

### 4.3 設定確認

```bash
# JWTトークン取得
TOKEN=$(curl -s -X POST http://localhost:8008/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"nhigashira@example.com","password":"password"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Gitea連携確認
curl -s http://localhost:8008/api/v1/gitea/repos \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**期待結果:**

```json
{
    "configured": true,
    "repos": [...]
}
```

`"configured": true` になれば設定完了。

---

## 5. リポジトリの作成

1. Gitea トップページ右上の **「+」** → **新しいリポジトリ**
2. 以下を入力:
   - **オーナー**: `admin`（またはログインユーザー）
   - **リポジトリ名**: 任意（例: `payment-service`）
   - **可視性**: プライベート or パブリック（任意）
3. 「リポジトリを作成」をクリック

ローカルからプッシュする場合:

```bash
git remote add origin http://localhost:3000/admin/payment-service.git
git push -u origin main
```

---

## 6. Webhook の登録

コミットや PR からタスクを自動更新するために、各リポジトリに Webhook を登録する。

### 6.1 Webhook の追加

1. リポジトリページ → **設定（Settings）** → **Webhooks** → **Webhook を追加** → **Gitea**
2. 以下を設定:

   | 項目 | 値 |
   |---|---|
   | ターゲット URL | `http://host.docker.internal:8008/api/v1/webhooks/gitea` |
   | シークレット | `87af6297c8aa60e15ff87793f8286e16` |
   | トリガー | **プッシュイベント** ＋ **プルリクエスト** にチェック |
   | 有効 | チェック済み |

3. 「Webhook を追加」をクリック

> `host.docker.internal` は Docker コンテナからホスト PC のポートへアクセスするための特殊ホスト名。Mac では標準で使用可能。

### 6.2 Webhook の動作テスト

1. 登録した Webhook の行をクリック → ページ下部の「テスト配信」ボタンをクリック
2. **HTTP 200** が返れば接続成功

---

## 7. 動作確認

### コミットによるタスク更新テスト

1. AI-PMO のタスク ID の先頭8文字を確認する（例: `a1b2c3d4`）
2. 以下のコミットメッセージでプッシュする:

   ```bash
   git commit --allow-empty -m "[PMO:a1b2c3d4] テスト #完了 [2h]"
   git push origin main
   ```

3. AI-PMO の該当タスクが `status=DONE` / `actual_hours+=2` になっていることを確認

### タスクへの Gitea リポジトリ紐付け

AI-PMO フロントエンドのタスク編集ダイアログ → **Gitea 連携** セクションで、
リポジトリとIssue番号を設定して保存する。

> `GITEA_ADMIN_TOKEN` が設定済みの場合のみ Gitea セクションが表示される。

---

## 8. コミットメッセージ記法リファレンス

```
[PMO:{task_id先頭8文字以上}] タイトル {ステータスキーワード} [{工数}]
```

### ステータスキーワード

| キーワード | 変更後ステータス |
|---|---|
| `#完了` / `#done` / `#fix` / `#close` | DONE |
| `#進行中` / `#wip` / `#start` | IN_PROGRESS |
| `#レビュー` / `#review` | REVIEW |
| （なし） | 変更なし（工数のみ加算） |

### 工数記法

| 記法 | 意味 |
|---|---|
| `[3h]` | 3時間を actual_hours に**加算** |
| `[30m]` | 30分（0.5時間）を actual_hours に加算 |

### 記述例

```bash
# タスクを完了にして3時間加算
git commit -m "[PMO:a1b2c3d4] Stripe SDK 統合完了 #完了 [3h]"

# ステータス変更なし・工数のみ加算
git commit -m "[PMO:a1b2c3d4] 実装中 [2h]"

# レビュー待ちに変更
git commit -m "[PMO:a1b2c3d4] コードレビュー依頼 #レビュー"
```

---

## 9. トラブルシューティング

### `"configured": false` になる

- `.env` の `GITEA_ADMIN_TOKEN` が空になっていないか確認
- バックエンドを再起動したか確認（`.env` 変更はプロセス再起動が必要）

### Webhook テスト配信が失敗する（接続拒否）

- バックエンドが起動しているか確認: `ps aux | grep run.py`
- URL が `host.docker.internal` になっているか確認（`localhost` は Docker 内から到達不可）

### コミットしてもタスクが更新されない

- コミットメッセージの `[PMO:...]` の ID が正しいか確認（タスクID先頭8文字以上）
- Webhook の署名シークレットが `.env` の `GITEA_WEBHOOK_SECRET` と一致しているか確認
- バックエンドログを確認: `tail -f /Users/nhigashira/Documents/dev/ai-pmo/backend/backend.log`

### PR マージ後に教訓が登録されない

- PR 本文が 100 文字以上あるか確認（未満の場合は LLM 呼び出しをスキップ）
- LM Studio が起動しているか確認
