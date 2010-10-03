= !HyperEstraierによる全文検索プラグイン Ver 0.1(勝手にtrac0.12対応版) =
ここでは、Hirobeさん作、リポジトリ検索プラグインの[http://weekbuild.sakura.ne.jp/trac/wiki/TracDoc/SearchHyperEstraierPlugin SearchHyperEstraier]を[[BR]]「勝手に」修正し、trac0.12に対応、その他機能追加を行ったものについて記述してます。

== 1. 概要 ==
全文検索を行うためのプラグインです。[[BR]]
trac0.12対応としてマルチリポジトリに対応しています。[[BR]] また、機能追加を行ってますので以下のような検索が行えます。[[BR]]

 * リポジトリからチェックアウトしたソースについての検索(従来から機能)
 * チェンジセットのコミットログの検索
 * 添付ファイル内の文字列検索
 * ドキュメントディレクトリの文字列検索

仕組み：バッチを使い、リポジトリのソースやコミットログ、添付ファイルやドキュメントディレクトリの内容から、[[BR]]HyperEstraierのインデックスを生成します。[[BR]]そのインデックスを利用し、Trac内でコマンド版cmdestを実行、その結果を表示します。

'''制限'''

 * ソースの検索は、リポジトリ内の最新のファイルしか検索できません。
 * apacheからcmdest.exeを起動できるように権限設定が必要かもしれません。
 * Windowsでしか動作確認してません。
 * 動作は無保証です。

== 2. セットアップ ==
インストール方法の後、構成例を挙げ、それに沿って、リポジトリ、チェンジセット、添付ファイル、ドキュメントの[[BR]]
それぞれの機能のセットアップを記述してます。[[BR]]
それぞれの機能は独立してますので、いくつかだけを有効にすることもできます。[[BR]]
必要な部分だけ読んでください。[[BR]]
設定例のファイル(makeindex.bat.sample,trac.ini.sample,updateindex.bat.sample)[[BR]]
やコミットログを出力するスクリプト(MkCommentFile.py)も添付してますので[[BR]]
ご利用下さい。

=== 2.0. インストール ===
[http://fallabs.com/hyperestraier/ HyperEstraier]のWindows版バイナリパッケージの中の[[BR]]
estraier.dll,qdbm.dll,mgwz.dll,libiconv-2.dll, [[BR]]regex.dll,pthreadGC2.dll,estcmd.exe,estxfilt.bat,xdoc2txt.exe,zlib.dll[[BR]]
があればHyperEstraierを使えます。pathが通った場所においてください。[[BR]]
TracLightningであればインストールフォルダのbinフォルダがよいでしょう。

そしてこのプラグインを解凍、setup.pyがあるディレクトリに移動して、
{{{
python setup.py install
}}}
を実行してください。
=== 2.1.ディレクトリ構成例 ===
TracLightningでの使用を意識したディレクトリの構成例を示します。

 * c:\TracLight
   * projects
     * svn
       * pj1…default repository
       * repos2
     * trac
       * pj1
     * doc
       * pj1
   * search
     * repos
       * pj1
         * rep
         * casket
       * repos2
         * rep
         * casket
     * changeset
       * pj1
         * rep
         * casket
       * repos2
         * rep
         * casket
     * attach
       * pj1
         * casket
     * doc
       * pj1
         * casket

c:\TracLight\projectsはtracプロジェクトやリポジトリを含むディレクトリを示しています。[[BR]]ここでは、tracプロジェクト1つ(c:\TracLight\projects\trac\pj1)、[[BR]]それに対応するリポジトリ2つ(c:\TracLight\projects\svn\pj1,repos2)と[[BR]]ドキュメントディレクトリ１つ(c:\TracLight\projects\doc\pj1)にしてます。

c:\TracLight\searchはHyperEstraierで使用する検索用のindexデータ(casket)と、[[BR]]検索される内容を入れるディレクトリです。[[BR]]検索される内容としては、

 * リポジトリからチェックアウトしたソース(c:\TracLight\search\repos\pj1\repとc:\TracLight\search\repos\repos2\rep)
 * チェンジセットのコミットログ(c:\TracLight\search\changeset\pj1\repとc:\TracLight\search\changeset\repos2\rep)

を配置してます。

=== 2.2.リポジトリ ===
リポジトリからエクスポートしたソースを検索する設定です。[[BR]]
※tracへのリポジトリの登録は事前にしておいてください。
==== 2.2.1 エクスポート/インデックス生成バッチファイルの作成 ====
リポジトリのエクスポートとインデックス生成を行うバッチを作成します。

上図に沿ったバッチファイルの例を示します。

{{{
set EXPORT_FOLDER=c:\TracLight\search\repos\pj1\rep
set INDEX_FOLDER=c:\TracLight\search\repos\pj1\casket
set REPOS_URI=file:///C:/TracLight/projects/svn/pj1/trunk

rmdir /S /Q %EXPORT_FOLDER%
rmdir /S /Q %INDEX_FOLDER%
svn export %REPOS_URI% %EXPORT_FOLDER%
estcmd gather -cl -fx .pdf,.rtf,.doc,.xls,.ppt T@estxfilt -ic CP932  -pc CP932  -sd %INDEX_FOLDER% %EXPORT_FOLDER%
}}}
上記バッチファイルでは、冒頭部の環境変数により設定をしています。

|| EXPORT_FOLDER || リポジトリのエクスポート先となるディレクトリ。空のディレクトリを指定。 ||
|| REPOS_URI || エクスポート元となるリポジトリのURI ||
|| INDEX_FOLDER || インデックスの生成先ディレクトリ。空のディレクトリを指定。 ||

適切に書き換えてご使用ください。[[BR]]なお、リポジトリのエクスポートの認証は考慮してません。認証が必要であればsvn exportに適切な引数を設定してください。[[BR]] 通常は上記のようにtrunkなどリポジトリの一部を指定します。[[BR]](全体にしてしまうとtagsやbranchesの中身もチェックアウトしてしまいます。)[[BR]]また、上記バッチファイルはフルパス指定であるため、どこにおいてもかまいませんが、[[BR]]tracプロジェクトのconfディレクトリなどにおくのが管理しやすいと思います。[[BR]] また上記では「.pdf,.rtf,.doc,.xls,.ppt」の拡張子のファイルしか検索しません。[[BR]] .txtや.cなどテキストファイルであればestxfilt.batで呼ばれる[[BR]]xdoc2txtはスルーで出しますので[[BR]]「,.txt」のように-fxの後に続く拡張子の列挙の後追記してください。

この例ではpj1リポジトリのみ設定してますが、バッチファイル中の「pj1」を[[BR]] 「repos2」に置き換えて下方に同様の処理を書くか、別のバッチファイルを作るかすれば[[BR]] 対応できます。
==== 2.2.2 trac.iniの設定 ====
テキストファイルでtrac.ini(上図ではc:\TracLight\projects\trac\pj1\conf配下)を開いて [searchhyperestraier]というブロックを追加してください。

|| xxx.index_path || インデックス生成パス(バッチファイルのINDEX_FOLDER) ||
|| xxx.replace_left || 検索結果のパスの頭で削るべき文字列。 ||
|| xxx.url_left || URLを生成する際に頭につける文字列。browse_trac=enabledの場合は/がリポジトリのルートになるようにすること。 ||
|| browse_trac || Tracのブラウザへのリンクを作るか否か。enabled=Tracのブラウザへのリンクを作る。リポジトリソース検索共通の機能。デフォルトは'enabled'。 ||
|| estcmd_path || 環境変数PATHが設定済みなら設定不要。estcmd.exeの絶対パス。すべての機能に共通の機能。デフォルトは'estcmd' ||
|| estcmd_arg || Windowsでは設定不要。estcmd.exeの引数。すべての機能に共通の機能。デフォルトは'search -vx -sf -ic Shift_JIS' ||
|| estcmd_encode || Windowsでは設定不要。コマンド実行時のエンコード(Pythonでの形式)。すべての機能に共通の機能。デフォルトは'mbcs' ||

  ここではdefaultリポジトリであるかを意識して設定する必要があります。[[BR]]  上表で「xxx」になっている部分はリポジトリ名を記述します。[[BR]]  ただし、defaultリポジトリであれば、何も書きません。[[BR]]  たとえば、「.index_path」のように記述します[[BR]]
(元のSearchHyperEstraierを使っていた人は変更が必要です)。[[BR]]
index_path,replace_left,url_leftはリポジトリごとに設定できます。[[BR]]

例：

{{{
[searchhyperestraier]
.index_path = C:\TracLight\search\repos\pj1\casket
.replace_left = C:\TracLight\search\repos\pj1\rep
.url_left = /trunk
repos2.index_path = C:\TracLight\search\repos\repos2\casket
repos2.replace_left = C:\TracLight\search\repos\repos2\rep
repos2.url_left = /trunk
}}}
browser_tracがenabledになる場合は、登録されるURLはTracのリポジトリブラウザでRoot直下が/となるように replace_left,url_leftを調整する必要があります。[[BR]]たとえば、リポジトリブラウザでRoot/trunk/test3/検索のテスト.docと表示されるファイルは、/trunk/test3/検索のテスト.docとなるように調整してください。[[BR]]難しければ、何も設定せずに、検索結果として表示されたURLを見ながら調整してください。[[BR]]通常、EXPORT_FOLDER=replace_left、INDEX_FOLDER=index_pathになります。[[BR]]

また、[components]ブロックでこの機能を有効にしてください。

{{{
[components]
searchhyperestraier.searchhyperestraier.searchhyperestraiermodule = enabled
}}}
=== 2.3.チェンジセット ===
「direct-svnfs」専用です。[[BR]]
チェンジセットはtracにも機能がありますが、[[BR]]
typeが「direct-svnfs」の場合、DBに取り込まれないので[[BR]]
検索できません。そういう場合にお使いください。[[BR]]
「direct-svnfs」以外のものは検索しないようにしてますので[[BR]]
併用していただいても大丈夫です。[[BR]]

※tracへのリポジトリの登録は事前にしておいてください。
==== 2.3.1.コミットログファイル/インデックス生成バッチファイルの作成 ====
コミットログを一つ一つのファイルとして出力し、インデックス生成を行うバッチを作成します。[[BR]]
コミットログをファイルとして出力するために、MkCommentFile.pyというスクリプトを[[BR]]
用意しました。[[BR]]

上図に沿ったバッチファイルの例を示します。

{{{
set EXPORT_FOLDER=c:\TracLight\search\changeset\pj1\rep
set INDEX_FOLDER=c:\TracLight\search\changeset\pj1\casket
set REPOS_FOLDER=C:/TracLight/projects/svn/pj1

for /F %%i in ('svnlook youngest %REPOS_FOLDER%') do set LASTREVISION=%%i
python MkCommentFile.py %REPOS_FOLDER% %EXPORT_FOLDER% 1 %LASTREVISION%
estcmd gather -cl -fx.pdf,.rtf,.doc,.xls,.ppt T@estxfilt -ic CP932  -pc CP932  -sd %INDEX_FOLDER% %EXPORT_FOLDER%

}}}
2.2.1.と同様、上記バッチファイルでは、冒頭部の環境変数により設定をしています。

|| EXPORT_FOLDER || コミットログが入るディレクトリ。空のディレクトリを指定。 ||
|| REPOS_FOLDER || 対象リポジトリのディレクトリ。ここではtrunkなどの指定をしません。 ||
|| INDEX_FOLDER || インデックスの生成先ディレクトリ。空のディレクトリを指定。 ||

適切に書き換えてご使用ください。

この例ではpj1リポジトリのみ設定してますが、バッチファイル中の「pj1」を[[BR]] 「repos2」に置き換えて下方に同様の処理を書くか、別のバッチファイルを作るかすれば[[BR]] 対応できます。
==== 2.3.2.trac.iniの設定 ====
trac.iniを開いて [searchhyperestraier]ブロックに追加してください。

|| xxx.cs_index_path || インデックス生成パス(バッチファイルのINDEX_FOLDER) ||

2.2.2.と同様、ここではdefaultリポジトリであるかを意識して設定する必要があります。[[BR]]  上表で「xxx」になっている部分はリポジトリ名を記述します。[[BR]]  ただし、defaultリポジトリであれば、何も書きません。[[BR]]  「.cs_index_path」のように記述します。[[BR]]
xxxの部分を変えて設定することでリポジトリごとに設定できます。[[BR]]

例：

{{{
[searchhyperestraier]
.cs_index_path = C:\TracLight\search\changeset\pj1\casket
repos2.cs_index_path = C:\TracLight\search\changeset\repos2\casket
}}}

また、[components]ブロックでこの機能を有効にしてください。

{{{
[components]
searchhyperestraier.searchhyperestraier.searchchangesethyperestraiermodule = enabled
}}}
=== 2.4.添付ファイル ===
tracのチケットやwikiの添付ファイル中の文字列検索を行うための設定です。
==== 2.4.1.インデックス生成バッチファイルの作成 ====
インデックス生成を行うバッチを作成します。[[BR]]

上図に沿ったバッチファイルの例を示します。

{{{
set INDEX_FOLDER=c:\TracLight\search\attach\pj1\casket
set ATT_FOLDER=c:\TracLight\projects\trac\pj1\attachments

estcmd gather -cl -fx .pdf,.rtf,.doc,.xls,.ppt,.c,.asm,.py,.txt T@estxfilt -ic CP932  -pc CP932  -sd %INDEX_FOLDER% %ATT_FOLDER%
}}}
2.2.1.と同様、上記バッチファイルでは、冒頭部の環境変数により設定をしています。

|| ATT_FOLDER || tracの添付ファイルディレクトリ。tracプロジェクトのattachmentsディレクトリを指定。 ||
|| INDEX_FOLDER || インデックスの生成先ディレクトリ。空のディレクトリを指定。 ||

適切に書き換えてご使用ください。

==== 2.4.2.trac.iniの設定 ====
trac.iniを開いて [searchhyperestraier]ブロックに追加してください。

|| att_index_path || インデックス生成パス(バッチファイルのINDEX_FOLDER) ||

単純にインデックス生成パスを設定してください。

例：

{{{
[searchhyperestraier]
att_index_path = C:\TracLight\search\attach\pj1\casket
}}}

また、[components]ブロックでこの機能を有効にしてください。

{{{
[components]
searchhyperestraier.searchhyperestraier.searchattachmenthyperestraiermodule = enabled
}}}
=== 2.5.ドキュメント ===
ドキュメントディレクトリにある指定ファイル中の文字列検索を行うための設定です。
ドキュメントディレクトリがブラウザで見られるようにhttpd.confを設定しておく必要があります。
例
{{{
Alias /doc "c:\tracpj\doc"
<Directory "c:\tracpj\doc">
    Options Indexes
    IndexOptions +FancyIndexing +NameWidth=* +SuppressDescription +SuppressIcon
    Allow from all
</Directory>
}}}
==== 2.5.1.インデックス生成バッチファイルの作成 ====
インデックス生成を行うバッチを作成します。[[BR]]

上図に沿ったバッチファイルの例を示します。

{{{
set DOC_FOLDER=c:\TracLight\projects\doc\pj1
set INDEX_FOLDER=c:\TracLight\search\doc\pj1\casket

estcmd gather -cl -fx .pdf,.rtf,.doc,.xls,.ppt,.c,.asm,.py,.txt T@estxfilt -ic CP932  -pc CP932  -sd %INDEX_FOLDER% %DOC_FOLDER%
}}}
2.2.1.と同様、上記バッチファイルでは、冒頭部の環境変数により設定をしています。

|| DOC_FOLDER || ドキュメントディレクトリ。 ||
|| INDEX_FOLDER || インデックスの生成先ディレクトリ。空のディレクトリを指定。 ||

適切に書き換えてご使用ください。

==== 2.5.2.trac.iniの設定 ====
trac.iniを開いて [searchhyperestraier]ブロックに追加してください。

|| doc_index_path || インデックス生成パス(バッチファイルのINDEX_FOLDER) ||
|| doc_replace_left || 検索結果のパスの頭で削るべき文字列(バッチファイルのDOC_FOLDER)。 ||
|| doc_url_left || URLを生成する際に頭につける文字列。 ||

単純にインデックス生成パスを設定してください。

例：

{{{
[searchhyperestraier]
doc_index_path = C:\TracLight\search\doc\pj1\casket
doc_replace_left = c:\TracLight\projects\doc\pj1
doc_url_left = /doc/pj1
}}}

また、[components]ブロックでこの機能を有効にしてください。

{{{
[components]
searchhyperestraier.searchhyperestraier.searchdocumenthyperestraiermodule = enabled
}}}
== 3. apacheを再起動する ==
trac.iniを設定したら、apacheを再起動してください。[[BR]](「サービスのアンインストール」を実行、再度「サービスのインストール」を実行。)

== 4. バッチファイルを実行する ==
作成したバッチファイルを実行してください。

== 5. 検索してみる ==
検索タブをクリックして、チェックボックスが表示されることを確認してください。[[BR]]同様の機能と区別するため、頭に「he:」と表記してます。[[BR]]
he:リポジトリ,he:添付ファイル,he:チェンジセット,he:ドキュメントのうち[[BR]]
機能を有効にしているものが表示されているか確認してください。[[BR]]
リポジトリは'BROWSER_VIEW'、チェンジセットは'CHANGESET_VIEW'、[[BR]]
添付ファイルatt_index_pathが設定されていること、
ドキュメントはdoc_index_path,doc_replace_left,doc_url_leftが[[BR]]
設定されていることが表示条件です。[[BR]]
表示されていればチェックを入れ、適当なキーワードで検索して、結果を確認してください。[[BR]]リンクをクリックして、画面がリポジトリブラウザに切り替わり、正しくそのファイルを表示していることを確認してください。

== 6. バッチファイルをタスク設定する ==
動作確認ができたら必要なバッチファイルが１日１回実行できるようにWindowsのタスクを設定してください。[[BR]] 2000またはXPでは、タスクの追加は、以下のように行います。[[BR]] ［スタート］メニューから［プログラム］－［アクセサリ］－［システムツール］－［タスク］[[BR]] または[[BR]] ［コントロール パネル］の［タスク］[[BR]] を開き、［スケジュールされたタスクの追加］をクリックします。[[BR]] するとタスクウィザードが起動します。[[BR]] 「実行するプログラムを１つ選択してください。」のところで、[[BR]] 参照ボタンを押し、バッチファイルを指定してください。[[BR]] 「このタスクの実行」で「日単位」を選択してください。[[BR]] その後、開始日時などを設定します。[[BR]] 最後にユーザー名とパスワードの入力を行って終了です。[[BR]] 完了ボタンを押すと登録されます。

== 7. 設定時刻を待たずにすぐ更新する ==
もし、設定時刻を待たずにすぐ更新したい場合は、[[BR]] バッチファイルを直接実行してください。