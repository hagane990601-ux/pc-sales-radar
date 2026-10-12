# PC案件レーダー

公開されている自治体・官公庁の建築・設計・入札情報を確認する、スマホ対応の公開Webサイトです。

**公開サイト：** https://hagane990601-ux.github.io/pc-sales-radar/

## 現時点でできること
- 担当者名・設計事務所・場所で検索（公開情報には社内担当者名なし）
- 自治体の公表資料・PDFリンクを案件詳細から確認
- RSS収集プログラムをGitHub Actionsで日次実行
- 公開PDFをGemini 2.5 Flash-Liteで解析する準備コードと検証テスト
- Geminiが解析した情報を「AI抽出・要原資料確認」と明示して表示（APIキー設定後）
- Geminiキー未設定・無料枠上限・収集先の一時エラーでもサイト表示は継続

## Geminiの接続（利用者による一度だけの設定）

1. [Google AI Studio — API Keys](https://aistudio.google.com/app/apikey) で自分のGemini APIキーを作成。利用規約・無料枠・請求設定を確認。
2. **キーはチャット・コード・README・Issuesに貼らないでください。**
3. [GitHub Actions secrets](https://github.com/hagane990601-ux/pc-sales-radar/settings/secrets/actions) で **New repository secret** を開く。
4. Nameに `GEMINI_API_KEY`、SecretにAPIキーを貼り付けて保存。
5. [GitHub Actions](https://github.com/hagane990601-ux/pc-sales-radar/actions/workflows/daily.yml) で **Run workflow** を実行する（または次の定期実行を待つ）。
6. `ai_status.json` を確認。成功すると `ai_results.json` に分析結果が追加され、対象案件の詳細画面に「AI資料解析」が表示される。

## 制限と安全対策
- AIへ送信するのは `official_documents.json` に固定登録した **公表済みPDFのみ**。
- 公式ドメイン・HTTPS・PDF形式を検証し、1資料8MBまで、1実行2回までに制限。
- 解析済み資料は21日間キャッシュし、繰り返しのAPI消費を抑える。
- 解析結果のページ番号・構造形式・スパン等は誤る可能性があるため、根拠となる原典PDFと必ず照合。
- 社内PDF、営業担当者名、訪問履歴、顧客メモ、非公開情報はGitHubに置かず、Geminiにも送信しない。
- 公開済みのRSSで見つけたニュースは未検証として扱い、主案件一覧へ自動混入させない。
- 月次の社内PDFとの自動重複除外は未接続。収集網羅性・出典PDFリンクの継続利用は保証されない。
- Gemini APIは無料枠が変更・制限される場合がある。無料枠の範囲外に達した際は解析をスキップまたはエラーとして記録する。

## 構成
`index.html` は検索UI、`scripts/collect.py` は公開RSS候補の収集、`scripts/gemini_enrich.py` は登録済み公式PDF解析、`tests/test_gemini.py` は外部通信なしの安全テスト。GitHub Actionsから毎日実行され、サイトを再デプロイします。

**次の段階：** 入札ポータルごとに適切なアクセス方法を確認し、案件ID、正式案件名、落札設計事務所、地域、PDFを原典から抽出するコネクタを追加する。

## Gemini接続テスト

GitHubのRepository secretを設定した後、mainブランチへのプッシュで新しいワークフロー実行が起動します。公開PDFの取得・AI分析の成否は `ai_status.json` に記録されます。`ai_results.json` が空ならGeminiによる解析はまだ完了していません。
