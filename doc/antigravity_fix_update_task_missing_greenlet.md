# 【AI-PMO バグ修正指示】update_task MissingGreenlet エラー

## 概要

`PUT /api/v1/tasks/{task_id}` でタスクの設定を変更すると 500 Internal Server Error が発生する。

## エラー内容

```
sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call await_only() here.
```

発生箇所:
```
File ".../app/api/v1/endpoints/tasks.py", line 189, in update_task
    task.dependencies.clear()
```

## 原因

`update_task` 関数（`tasks.py` L158〜）でタスクを取得する際に `db.get()` を使用している。  
`db.get()` はリレーションを eager load しないため、`task.dependencies` が未ロードの状態になる。

その後 L189 で `task.dependencies.clear()` を呼ぶと、SQLAlchemy が `lazy="select"` の設定に従い同期的な遅延ロードを試みる。  
しかし asyncpg を使う async セッションでは同期 IO が禁止されており、`MissingGreenlet` エラーになる。

## 修正内容

**ファイル:** `backend/app/api/v1/endpoints/tasks.py`

`update_task` 関数の冒頭でタスクを取得している部分（L160）を、`selectinload` を使った select クエリに置き換える。

### 修正前（L158〜162）

```python
@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: UUID, task_in: TaskUpdate, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
```

### 修正後（L158〜165）

```python
@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: UUID, task_in: TaskUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Task)
        .where(Task.id == task_id)
        .options(selectinload(Task.dependencies))
    )
    task = result.scalar()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
```

## 確認事項

- `select` と `selectinload` は同ファイル内の他の関数（`get_task`, `list_tasks` など）で既にインポート済みのため、追加インポートは不要。
- 修正箇所は L160 の `db.get()` の差し替えのみ。他の行（L161〜209）は変更不要。

## 修正後の動作確認

バックエンドを再起動し、以下を確認する。

```bash
# JWTトークン取得
TOKEN=$(curl -s -X POST http://localhost:8008/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"nhigashira@example.com","password":"password"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# タスク更新（存在するタスクIDを使用）
curl -s -X PUT http://localhost:8008/api/v1/tasks/<task_id> \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "修正確認テスト"}' | python3 -m json.tool
```

HTTP 200 かつレスポンスに `"title": "修正確認テスト"` が含まれれば修正完了。
