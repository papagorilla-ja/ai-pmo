# Antigravity 修正指示: ガントチャートのモード切替・表示不具合の修正

対象: `frontend/src/components/GanttChart.vue`。ライブラリは **frappe-gantt 1.2.2**（交換不要）。
本指示は、実画面+DOM計測で確定した不具合の是正。3モード（年/月/週）構成は維持する。

## 確定した原因（実機検証済み）
1. **凡例とモード切替ボタンがDOMから消える**:`initGantt()` 内の「ラッパー掃除」処理が、凡例・モードボタンを含む**テンプレートのルート `.gantt-container` を `wrapper.remove()` で削除**している。frappe-gantt も初期化時に同名 `.gantt-container` を生成するため名前衝突し、自分のUIごと消している。（DOM計測: モードボタン群・凡例ともに存在せず）
2. **依存矢印が不可視**:矢印の `stroke` が `#1f2937` でダーク背景に埋没。`.gantt .arrow` の色指定が無い。
3. **「6月」が全列に出る**:`upper_text` が「前列と同月なら空文字」方式。frappe-gantt 1.2.2 は `upper_text(date, null, lang)` でも呼びライブラリ側が重複排除するため、**常にフルラベルを返す**のが正しい契約。空文字制御は誤り。
4. **初期表示位置**:`scroll_to` 未指定で、開いた時に当日/タスク範囲が見えないことがある。

---

## 修正タスク

### FIX1【最重要】凡例・モードボタンを消さない（ラッパー削除処理の撤廃）
- `initGantt()` 内にある「`container.closest('.gantt-container')` を取得して `wrapper.remove()` する」一連の掃除処理を**完全に削除**する。これがUI（凡例＋年/月/週ボタン）を破壊している主因。
- 名前衝突を避けるため、**テンプレートのルート要素のクラス名 `gantt-container` を別名へ変更**（例: `wbs-gantt-panel`）。`<style>` の対応セレクタも追従。これで frappe-gantt が生成する `.gantt-container` と衝突しない。
- 再描画で frappe-gantt のラッパーが入れ子になるのを防ぐため、掃除処理の代わりに次の方式にする:
  - `.gantt-wrapper` 内の svg を毎回作り直す。すなわち `initGantt()` の冒頭で `ganttWrapperEl.innerHTML = ''` してから**新しい `<svg>` 要素を生成して append**し、その新svgに対して `new Gantt(newSvg, tasks, options)` を実行する。
  - `ganttSvg` の ref 取得方法も、この「毎回作り直す svg」に合わせて見直す（固定 ref ではなく、`.gantt-wrapper` を ref で持ち、内部svgを都度生成）。
- 受け入れ:再描画・モード切替後も**凡例とモードボタンが常に表示され続ける**こと。

### FIX2 モード切替が機能すること（+ 内部override の見直し）
- 年/月/週ボタンの `changeViewMode(name)` → `ganttInstance.change_view_mode(name)` が確実に動くこと。FIX1で svg を作り直す方式にした場合は、切替時も `initGantt()` 再実行で再構築されるなら `viewMode.value` を保持して再描画する形でよい（どちらの方式でも、切替後に正しいモードで描画されること）。
- `CustomGantt extends Gantt` による内部メソッド `setup_gantt_dates` の override は**壊れやすい**。これが切替時に例外を投げていないか確認し、問題があれば内部API依存を避ける実装へ置換する（年モードの月曜始まりは、`lower_text` 側で「その日の属する週の月曜日」を算出して表示する等、内部に手を入れない方法で実現する）。

### FIX3 `upper_text` / `lower_text` を正しい契約に修正
- **`upper_text` は常にその期間のフルラベルを返す**（空文字を返す分岐を撤廃）:
  - 月モード: `${d.getMonth()+1}月`（年跨ぎ考慮なら `${d.getFullYear()}年${d.getMonth()+1}月`）
  - 年モード: `${d.getFullYear()}年${d.getMonth()+1}月`
  - 週モード: `${d.getMonth()+1}月${d.getDate()}日`
- `lower_text` は最小単位:
  - 月モード: 日（`d.getDate()`）
  - 年モード: その週の**月曜日の日付**（`〇日`）
  - 週モード: 時刻ゼロ埋め（`00`/`06`/`12`/`18`）
- ラベルの重複排除・配置は frappe-gantt に任せる（自前で空文字制御しない）。

### FIX4 依存矢印を視認可能に
- `<style>` に追加: `.gantt .arrow { stroke: #8f9cae !important; stroke-width: 1.4px !important; fill: none !important; }`（背景 #0c111d 系に対し視認できる色）。アクティブ/ホバー時の色も必要に応じて調整。

### FIX5 初期スクロール位置
- `Gantt` オプションに `scroll_to` を指定し、開いた時に**当日（today）または直近タスクの開始日**が見える位置に寄せる。月モードで当月タスクがすぐ見えること。

### 維持するもの（変更しない）
- ステータス色分け（bar-todo/progress/done/delayed）、遅延=赤文字、バーと文字の同系色回避、全高レイアウト、ドラッグでの日程保存、休日グレー表示（土日+DB休日）、リソース/カレンダー管理画面。

---

## 受け入れ条件（dev で実機確認し報告）
1. WBS画面に**凡例カードと「年/月/週」ボタンが常に表示**される（再描画・モード切替後も消えない）。
2. 年/月/週ボタンで**実際に表示が切り替わる**:年=週単位(月曜始まりの日付)/月=日単位/週=6時間単位(00,06,12,18)。
3. **依存関係の矢印がはっきり見える**（背景と区別できる色）。
4. ヘッダの月ラベルが**各月に1つ**だけ表示される（「6月」が全列に出ない）。年=年月、週=日付がヘッダに出る。
5. 月モードで当月（例:6月）がきちんと表示され、開いた時に当日/直近タスク付近が見えている。
6. 休日グレー・ステータス色・遅延赤文字・全高・ドラッグ保存が従来どおり維持。
7. コンソールに致命的エラーが出ない。

## 注意
- frappe-gantt 1.2.2 の API（`scroll_to`、view_mode オブジェクト、`change_view_mode`、upper/lower_text の呼ばれ方）は `node_modules/frappe-gantt` の実装で確認してから実装すること。
- 最大の是正点は FIX1（自前のラッパー削除処理がUIを破壊している）である。ここを直さないと他が直っても操作不能のまま。
