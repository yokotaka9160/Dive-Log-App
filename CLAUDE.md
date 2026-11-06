# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

DEEPLOG は、スキューバダイビングのログを記録する Django 5.2(Python 3.12)のサーバーサイドレンダリングアプリです。UI、`verbose_name`、コードコメントは日本語で書かれています。ユーザーに表示する文字列を追加するときも日本語にしてください。

## コマンド

開発は Docker Compose で行います。リポジトリは `web` コンテナにバインドマウントされているため、コードを変更すると再ビルドなしで反映されます。起動時にマイグレーションは実行されません。

```sh
docker compose up --build                                  # http://localhost:8000 で起動
docker compose exec web python manage.py migrate
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py createsuperuser   # メールアドレスとユーザー名を入力
docker compose exec web python manage.py test              # 全テスト
docker compose exec web python manage.py test divelogs.tests.SomeTestCase.test_method   # 単一テスト
```

リンター、フォーマッター、CI は設定されていません。両アプリの `tests.py` は現在空なので、`manage.py test` を実行しても「NO TESTS RAN」と表示されるだけです。

この Windows + WSL 環境では、リポジトリを `\\wsl.localhost` パスで開いており、Windows の PATH に `git` がありません。git と docker は WSL 経由で実行してください: `wsl.exe -d Ubuntu --cd /home/yokot/mywork/deeplog -- git status`

## アーキテクチャ

`deeplog/urls.py` の下に 2 つのアプリがあり、それぞれ URL 名前空間を持っています。URL を逆引きするときは必ず名前空間を付けてください(`divelogs:log_list`、`accounts:login`)。付けないと `NoReverseMatch` になります。

- **`accounts`**(`/accounts/` にマウント): カスタム `User` モデル(`AUTH_USER_MODEL = 'accounts.User'`)と、登録・ログイン・ログアウトのビュー。
- **`divelogs`**(`/` にマウント): `DiveLog` モデル、ランディングページ、`/logs/` 配下の CRUD ビュー。

**認証はメールアドレスで行います。** `User.USERNAME_FIELD = 'email'` で、`EmailAuthenticationForm` がログイン欄をメールアドレス用にしています。`username` は登録時に必須ですが、ログインには使えません。`LOGIN_URL` は未設定で、`LoginRequiredMixin` が動くのは Django のデフォルト `/accounts/login/` がマウント先と偶然一致しているためです。`LogoutView.next_page` が `LOGOUT_REDIRECT_URL` より優先されるので、ログアウト後の遷移先はランディングページではなくログインページです。

**アクセス権限。** ログの一覧と詳細は公開されていて、全ユーザーのログが見えます(`?mine=1` で自分のログに絞り込み)。作成にはログインが必要です。更新と削除には本人であることも必要で、`OwnerRequiredMixin` により本人以外は 403 になります。`user` は `LogCreateView.form_valid` で設定するため、フォームのフィールドではありません。

**`DiveLog` の算出値。** `calculated_dive_number` と `duration_minutes` はカラムではなく Python のプロパティなので、`filter()` や `order_by()` には使えません。`calculated_dive_number` はインスタンスごとにクエリを発行するため、一覧ページと管理画面では 1 行につき 1 クエリが走ります。

**テンプレートと静的ファイル** はアプリごとではなくプロジェクト直下にあります(`templates/`、`static/css/style.css`)。`divelogs` アプリのテンプレートは `templates/divelogs/` ではなく `templates/logs/` にあります。`LogDetailView` が未バインドの `DiveLogForm` を渡しているのは、テンプレートで `form.<field>.label` からラベルを読むためだけです。

**`DiveLog` にフィールドを追加するとき** は、モデル、`DiveLogForm` の `fields` リスト、`log_form.html`、`log_detail.html` を更新してください。フォームテンプレートは各フィールドを手書きで描画しています。

## 見た目と実際の動作が違う設定

- **実際に使っているデータベースは SQLite です。** `settings.py` は `db.sqlite3` を指しており、このファイルは Git で管理されています。Compose の `db` サービスで Postgres も起動しますが、どこからも接続されておらず、`requirements.txt` に Postgres ドライバもありません。
- **`.env` は Django に影響しません。** `settings.py` は `environ.Env` を作成するだけで値を読み込まず、`DEBUG`、`ALLOWED_HOSTS`、`SECRET_KEY` はハードコードされています。ただし Compose が参照するので、`.env` ファイル自体は必要です。
- **アップロードメディアは未設定です。** `User.image` はありますが、`MEDIA_ROOT` と `MEDIA_URL` は未設定で、メディア用の URL ルートもなく、このフィールドを扱うユーザー向けフォームもありません。
- **`LOCALE_PATHS` が指す `locale/` は存在しません。** コンパイル済みの翻訳がないので、画面には日本語のソース文字列がそのまま表示されます。

## 旧スキーマに起因する既知の問題

ビューとテンプレートは以前のモデル(`title`、`site`、`creatures`、`notes`、`photo`、`owner`、`buddy`、`favorites`)から流用されたもので、今もこれらの名前を参照しています。以下は現在の動作です。

- `divelogs/views.py` の `landing` が名前空間なしで `redirect("log_list")` を呼ぶため、ログイン中のユーザーが `/` を開くと 500 エラーになります。登録後もここにリダイレクトされるので、新規ユーザーは登録直後にこのエラーに遭遇します。
- `LogListView` は `?q=...`(削除済みフィールドでフィルター)と `?sort=duration`(存在しない `duration` で並び替え)で `FieldError` によりクラッシュします。検索と並び替えの UI はコメントアウトされているため、今は URL を直接入力したときにしか発生しません。UI を復活させるには両方の修正が必要です。
- `log_detail.html` は自由記述の表示条件が `log.notes` になっているため、`free_text_field` が表示されません。その `<div class="notes">` も閉じられていません。`log.buddy` と `log.owner` も同様に古い名前です。正しく動く編集・削除ボタンは、ファイル末尾の `log.user` のブロックです。
- `log_form.html` は `form.title` と `form.photo` を描画していて、空のラベルが出ます。

テンプレートでは古い名前を参照してもエラーにならず、空文字列として描画されます。テンプレートのフィールド参照は `DiveLog` の定義と直接照らし合わせて確認してください。

**コメントアウトされたコードは未完成のものであり、手本にしないでください。** お気に入り機能はビュー、URL、テンプレートにわたってコメントアウトされています。`divelogs` の `signup` と `SignUpForm` は、`accounts` アプリに置き換えられたデッドコードです。また、HTML コメントでは Django のタグは無効になりません。`<!-- {% url 'x' %} -->` は実行され、エラーになることもあります。テンプレートのコードを無効にするには `{% comment %}` を使ってください。
