/***** ラブキャラ 営業メール下書き作成・送信済み確認エージェント 完全版（2026-07-12） *****/

/**
 * 主な変更点
 * 1. 対象シートを「整形済み_診断サイト受託」のみに限定
 * 2. アプローチ方法が「メール候補」の行だけを対象化
 * 3. 1日あたり15件のGmail下書きを作成
 * 4. 業界カテゴリ（ターゲット）ごとに件名・本文を切り替え
 * 5. テンプレート表が未更新でも動くよう、最新テンプレートをスクリプト内にも保持
 *
 * 2026-07-12更新
 * - 業界カテゴリごとの件名・本文を最新のトーク例に全面差し替え
 * - 本文テンプレートに「ご担当者様」の宛名・結び・P.S.（診断リンク）まで含める形へ変更
 * - buildEmailBody は会社名を先頭に付け、末尾に署名（株式会社ラブキャラ / 奥田）を添える
 * - 業界カテゴリがどのテンプレートにも一致しない（空欄含む）場合は
 *   汎用テンプレート「その他の業界（汎用版）」にフォールバックして送る
 */

const SCRIPT_VERSION = '2026-07-12';

/**
 * 営業リスト本体のスプレッドシートID
 * https://docs.google.com/spreadsheets/d/1J748-Kt8OOxlOh6iEfLv6Viya9nuzBB1xVsZ38jZdS0/edit
 */
const SALES_SPREADSHEET_ID = '1J748-Kt8OOxlOh6iEfLv6Viya9nuzBB1xVsZ38jZdS0';

/**
 * メールテンプレート表のスプレッドシートID
 * 【共有用】ラブキャラ ターゲットリスト
 */
const TEMPLATE_SPREADSHEET_ID = '1MJkXwWG1t5IWaiz8ThNfwEadMXYlph_40PXMcbBeyPg';

// 対象シート
const SALES_SHEET_NAME = '整形済み_診断サイト受託';
const TEMPLATE_SHEET_NAME = '診断サイト受託';

// 1日あたりの下書き作成上限
const DAILY_DRAFT_LIMIT = 15;

// メール本文の最後に追加する署名
const EMAIL_SIGNATURE = `株式会社ラブキャラ
奥田`;

// 営業リスト側の列番号
const COL_INDUSTRY = 3;       // C列：業界カテゴリ
const COL_COMPANY = 5;        // E列：会社名
const COL_EMAIL = 9;          // I列：メールアドレス
const COL_APPROACH = 12;      // L列：アプローチ方法
const COL_STATUS = 13;        // M列：ステータス
const COL_DATE_NOTE = 14;     // N列：下書き作成日時・送信確認日時
const COL_ERROR = 15;         // O列：エラー内容

// テンプレート側の列番号
const TEMPLATE_COL_TARGET = 1;   // A列：ターゲット / 業界カテゴリ
const TEMPLATE_COL_SUBJECT = 4;  // D列：件名
const TEMPLATE_COL_BODY = 5;     // E列：本文

// ステータス
const STATUS_UNTOUCHED = '未対応';
const STATUS_PROCESSING = '下書き作成中';
const STATUS_DRAFT_CREATED = 'メール下書き作成済み';
const STATUS_SENT = 'メール送信済み';
const STATUS_ERROR = 'エラー';

// アプローチ方法
const APPROACH_EMAIL_CANDIDATE = 'メール候補';

// 業界カテゴリがどのテンプレートにも一致しない場合に使う汎用テンプレートのターゲット名
const DEFAULT_TEMPLATE_TARGET = 'その他の業界（汎用版）';

// 添付内容ベースの埋め込みテンプレート
// 本文には宛名（ご担当者様）・結び・P.S.（診断リンク）まで含める
const EMBEDDED_TEMPLATE_ROWS = [
  {
    target: 'D2C/EC 食品・美容・アパレル',
    subject: 'Z世代の初回購入率とCPA、診断で改善しませんか（ラブキャラ）',
    body: `ご担当者様

突然のご連絡失礼いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田と申します。

D2C/EC事業では、SKUが増えるほどお客様が
「自分に合う商品」を選びきれずカゴ落ちし、
広告依存でCPAが上がり続ける、というお声をよく伺います。

御社でも近い状況はございませんでしょうか。

私たちは「商品レコメンド診断」で、
この"選べない離脱"を"自分ごと化した納得購入"へ変えるお手伝いをしています。
診断→結果別LP→LINE友だち化→購入まで、導線ごと設計・制作します。

自社の恋愛診断は広告費をかけず累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。
このオーガニック拡散のノウハウをそのままEC販促へ転用します。

もしご関心をお持ちいただけましたら、
御社の商品ラインに合わせた「商品診断」のラフ案を1つお作りし、
15分ほどでご説明させていただきます。

ぜひ候補日を2〜3ついただけますと幸いです。
よろしくお願いいたします。

P.S. 実際の診断はこちらから1〜2分でご体験いただけます（恋愛診断ですが、"数問で自分ごと化しシェアしたくなる設計"をご覧ください）：
https://lovecharacter64.jp/quiz`
  },
  {
    target: 'Z世代向け消費財メーカー（菓子・飲料・日用品）',
    subject: 'Z世代との接点とSNS話題化、"診断"で作りませんか（ラブキャラ）',
    body: `ご担当者様

突然のご連絡失礼いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田と申します。

消費財メーカー様からは、若年層とのブランド接点が年々細り、
キャンペーンを打ってもSNSでの話題化が一瞬で終わってしまう、
というお声をよく伺います。

御社でも近い状況はございませんでしょうか。

私たちは「あなたにぴったりの○○診断」のような商品タイプ診断キャンペーンで、
Z世代が結果を思わずシェアしたくなる参加型企画を設計し、
診断→結果シェア→商品指名→LINE友だち化まで、導線ごと制作しています。

自社の恋愛診断は広告費をかけず累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。
このオーガニック拡散のノウハウを、そのまま御社ブランドのキャンペーンへ転用します。

もしご関心をお持ちいただけましたら、
御社の商品に合わせた診断キャンペーンのラフ案を1つお作りし、
15分ほどでご説明させていただきます。

ぜひ候補日を2〜3ついただけますと幸いです。
よろしくお願いいたします。

P.S. 実際の診断はこちらから1〜2分でご体験いただけます（恋愛診断ですが、"数問で自分ごと化しシェアしたくなる設計"をご覧ください）：
https://lovecharacter64.jp/quiz`
  },
  {
    target: '専門学校・大学・通信制高校（学生募集）',
    subject: 'オープンキャンパス申込、"診断"で増やしませんか（ラブキャラ）',
    body: `ご担当者様

突然のご連絡失礼いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田と申します。

18歳人口の減少で、資料請求やオープンキャンパス申込の獲得単価が年々上がり、
広告を出しても高校生本人には届きにくい、というお声を学校広報のご担当者様からよく伺います。

貴校でも近い状況はございませんでしょうか。

私たちは「学科・進路タイプ診断」で、
高校生が"自分に向いている学び"を数問で自分ごと化し、
診断→結果別ページ→資料請求・オープンキャンパス申込→LINE友だち化まで、
募集導線をまるごと設計・制作しています。

自社の恋愛診断は広告費をかけず累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。
高校生・Z世代に"シェアで広がる"この仕組みを、そのまま学生募集へ転用します。

もしご関心をお持ちいただけましたら、
貴校の学科構成に合わせた「進路診断」のラフ案を1つお作りし、
15分ほどでご説明させていただきます。

ぜひ候補日を2〜3ついただけますと幸いです。
よろしくお願いいたします。

P.S. 実際の診断はこちらから1〜2分でご体験いただけます（恋愛診断ですが、"数問で自分ごと化しシェアしたくなる設計"をご覧ください）：
https://lovecharacter64.jp/quiz`
  },
  {
    target: '採用/求人/人材・採用難業界',
    subject: '若手採用の母集団形成、"診断"で変えませんか（ラブキャラ）',
    body: `ご担当者様

突然のご連絡失礼いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田と申します。

新卒・若手採用では、ナビ媒体や広告にコストをかけても
エントリーが集まらない、説明会に来ない、会社の魅力が伝わる前に離脱される、
というお声をよく伺います。

御社でも近い状況はございませんでしょうか。

私たちは「社風・職種マッチ診断」で、
学生・求職者が"自分に合う会社・仕事"を数問で自分ごと化し、
診断→結果別ページ→エントリー・説明会申込→LINE友だち化まで、
採用導線をまるごと設計・制作しています。

自社の恋愛診断は広告費をかけず累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。
若年層に"シェアで広がる"この仕組みを、そのまま母集団形成へ転用します。

もしご関心をお持ちいただけましたら、
御社の職種・社風に合わせた「採用診断」のラフ案を1つお作りし、
15分ほどでご説明させていただきます。

ぜひ候補日を2〜3ついただけますと幸いです。
よろしくお願いいたします。

P.S. 実際の診断はこちらから1〜2分でご体験いただけます（恋愛診断ですが、"数問で自分ごと化しシェアしたくなる設計"をご覧ください）：
https://lovecharacter64.jp/quiz`
  },
  {
    target: 'ゲーム・アプリ・エンタメサービス運営',
    subject: 'CPI高騰と休眠ユーザー、"診断"で動かしませんか（ラブキャラ）',
    body: `ご担当者様

突然のご連絡失礼いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田と申します。

ゲーム・アプリ運営では、新規獲得のCPIが上がり続ける一方、
話題化施策が単発で終わり、休眠ユーザーも戻ってこない、
というお声をよく伺います。

御社でも近い状況はございませんでしょうか。

私たちは「キャラ・タイプ診断」を使った参加型キャンペーンで、
ユーザーが結果をシェアしたくなる仕掛けを作り、
診断→結果シェア→DL/復帰→LINE・プッシュ導線まで、まるごと設計・制作しています。

自社の恋愛診断は広告費をかけず累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破し、
番組への新規流入にもつながりました。エンタメ作品との相性は実証済みです。

もしご関心をお持ちいただけましたら、
御社のタイトル・サービスに合わせた診断キャンペーンのラフ案を1つお作りし、
15分ほどでご説明させていただきます。

ぜひ候補日を2〜3ついただけますと幸いです。
よろしくお願いいたします。

P.S. 実際の診断はこちらから1〜2分でご体験いただけます：
https://lovecharacter64.jp/quiz`
  },
  {
    target: '推し活・IP・ファンビジネス',
    subject: 'ファンのUGCと新規ファン獲得、"診断"で仕掛けませんか（ラブキャラ）',
    body: `ご担当者様

突然のご連絡失礼いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田と申します。

IP・タレント・VTuberの運営では、コアファンは熱いものの
新規ファンとの接点が作りにくく、UGCが盛り上がるのは発表時だけ、
グッズ販促も既存ファン頼みになりがち、というお声をよく伺います。

御社でも近い状況はございませんでしょうか。

私たちは64タイプの恋愛診断IPを自社運営しており、
「推しタイプ診断」「あなたは○○メンバー診断」のようなコラボ診断で、
ファンが結果を競うようにシェアするUGCの波を設計します。
診断→結果シェア→新規ファン流入→グッズ・イベント導線まで一括制作です。

自社の恋愛診断は広告費をかけず累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。

もしご関心をお持ちいただけましたら、
御社のIP・タレントに合わせたコラボ診断のラフ案を1つお作りし、
15分ほどでご説明させていただきます。

ぜひ候補日を2〜3ついただけますと幸いです。
よろしくお願いいたします。

P.S. 実際の診断はこちらから1〜2分でご体験いただけます：
https://lovecharacter64.jp/quiz`
  },
  {
    target: '音楽・ライブ・フェス',
    subject: 'ライブ・フェスの新規客層、"診断"で広げませんか（ラブキャラ）',
    body: `ご担当者様

突然のご連絡失礼いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田と申します。

音楽・ライブ・フェスの集客では、既存ファンには届くものの
「行ってみたいけど自分向けか分からない」ライト層・新規層に届かず、
SNSの話題化もリリース時の一瞬で終わってしまう、というお声をよく伺います。

御社でも近い状況はございませんでしょうか。

私たちは「あなたに合うアーティスト診断」「フェスの回り方タイプ診断」のような参加型診断で、
ライト層が"自分ごと化"して結果をシェアしたくなる仕掛けを作り、
診断→結果シェア→チケット・配信・LINE導線まで、まるごと設計・制作しています。

自社の恋愛診断は広告費をかけず累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。

もしご関心をお持ちいただけましたら、
御社の公演・フェスに合わせた診断企画のラフ案を1つお作りし、
15分ほどでご説明させていただきます。

ぜひ候補日を2〜3ついただけますと幸いです。
よろしくお願いいたします。

P.S. 実際の診断はこちらから1〜2分でご体験いただけます：
https://lovecharacter64.jp/quiz`
  },
  {
    target: '商業施設・小売施設',
    subject: '来館促進と館内回遊、"診断"で仕掛けませんか（ラブキャラ）',
    body: `ご担当者様

突然のご連絡失礼いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田と申します。

商業施設様からは、若年層の来館が減り、
館内イベントを打っても回遊やテナント送客につながりにくい、
アプリ・LINE会員も伸び悩む、というお声をよく伺います。

御施設でも近い状況はございませんでしょうか。

私たちは「あなたにぴったりの過ごし方診断」「ギフト診断」のような参加型診断で、
診断→結果別のおすすめ店舗・フロア案内→来館・回遊→LINE会員化まで、
館内イベントとデジタル施策をまるごと設計・制作しています。

自社の恋愛診断は広告費をかけず累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。

もしご関心をお持ちいただけましたら、
御施設のテナント構成に合わせた診断企画のラフ案を1つお作りし、
15分ほどでご説明させていただきます。

ぜひ候補日を2〜3ついただけますと幸いです。
よろしくお願いいたします。

P.S. 実際の診断はこちらから1〜2分でご体験いただけます（恋愛診断ですが、"数問で自分ごと化しシェアしたくなる設計"をご覧ください）：
https://lovecharacter64.jp/quiz`
  },
  {
    target: 'フィットネス・パーソナルジム',
    subject: '体験申込の壁、"診断"で下げませんか（ラブキャラ）',
    body: `ご担当者様

突然のご連絡失礼いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田と申します。

フィットネス・ジム運営では、広告からのCPAが上がる一方、
「興味はあるが自分に続けられるか不安」という層が体験申込の手前で離脱してしまう、
というお声をよく伺います。

御社でも近い状況はございませんでしょうか。

私たちは「あなたに合うトレーニングタイプ診断」で、
見込み客が"自分に合うやり方"を数問で自分ごと化し、
診断→結果別ページ→体験予約→LINE友だち化まで、集客導線をまるごと設計・制作しています。

自社の恋愛診断は広告費をかけず累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。

もしご関心をお持ちいただけましたら、
御社のプログラムに合わせた診断のラフ案を1つお作りし、
15分ほどでご説明させていただきます。

ぜひ候補日を2〜3ついただけますと幸いです。
よろしくお願いいたします。

P.S. 実際の診断はこちらから1〜2分でご体験いただけます（恋愛診断ですが、"数問で自分ごと化しシェアしたくなる設計"をご覧ください）：
https://lovecharacter64.jp/quiz`
  },
  {
    target: '美容クリニック・歯科・小児科・動物病院',
    subject: '初診・カウンセリング予約の心理的ハードル、"診断"で下げませんか（ラブキャラ）',
    body: `ご担当者様

突然のご連絡失礼いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田と申します。

クリニック・医院の集患では、興味を持った方が
「自分の悩みで行っていいのか分からない」「何を相談すればいいか分からない」と
予約の手前で離脱してしまう、というお声をよく伺います。

貴院でも近い状況はございませんでしょうか。

私たちは「お悩みタイプ診断」「自分に合うケアの考え方診断」のような診断コンテンツで、
来院前の不安を整理し、診断→結果別の案内ページ→カウンセリング・初診予約→LINE友だち化まで、
導線をまるごと設計・制作しています。医療広告ガイドラインに配慮した表現設計で制作します。

自社の恋愛診断は広告費をかけず累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。

もしご関心をお持ちいただけましたら、
貴院の診療内容に合わせた診断のラフ案を1つお作りし、
15分ほどでご説明させていただきます。

ぜひ候補日を2〜3ついただけますと幸いです。
よろしくお願いいたします。

P.S. 実際の診断はこちらから1〜2分でご体験いただけます（恋愛診断ですが、"数問で自分ごと化しシェアしたくなる設計"をご覧ください）：
https://lovecharacter64.jp/quiz`
  },
  {
    target: 'スポーツブランド・スポーツチーム',
    subject: 'ライト層のファン化、"診断"で仕掛けませんか（ラブキャラ）',
    body: `ご担当者様

突然のご連絡失礼いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田と申します。

スポーツブランド・チームの運営では、コアファンには届くものの、
「興味はあるが自分ごとになっていない」ライト層が観戦・購入まで進まず、
SNSの話題も試合日・発売日の一瞬で終わる、というお声をよく伺います。

御社でも近い状況はございませんでしょうか。

私たちは「観戦タイプ診断」「あなたに合うギア診断」「推し選手診断」のような参加型診断で、
ライト層が自分ごと化して結果をシェアしたくなる仕掛けを作り、
診断→結果シェア→チケット・EC・ファンクラブ→LINE導線まで、まるごと設計・制作しています。

自社の恋愛診断は広告費をかけず累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。

もしご関心をお持ちいただけましたら、
御社・御チームに合わせた診断企画のラフ案を1つお作りし、
15分ほどでご説明させていただきます。

ぜひ候補日を2〜3ついただけますと幸いです。
よろしくお願いいたします。

P.S. 実際の診断はこちらから1〜2分でご体験いただけます：
https://lovecharacter64.jp/quiz`
  },
  {
    target: '結婚相談所・ブライダル',
    subject: '入会前の心理的ハードル、恋愛診断IPで下げませんか（ラブキャラ）',
    body: `ご担当者様

突然のご連絡失礼いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田と申します。

婚活・ブライダル業界では、興味を持った方が
「いきなり相談・入会はハードルが高い」と手前で離脱してしまい、
広告からの獲得単価も上がり続ける、というお声をよく伺います。

御社でも近い状況はございませんでしょうか。

私たちは64タイプの恋愛診断「ラブキャラ」を自社運営しており、
広告費をかけず累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。

この恋愛診断を御社の集客導線に組み込むと、
「まず自分の恋愛タイプを知る」という気軽な入口から、
診断→結果別ページ→無料相談・来店予約→LINE友だち化まで、
入会前の心理的ハードルを段階的に下げる導線をまるごと設計・制作できます。
恋愛・婚活の文脈にそのまま使える診断IPを持つ制作会社は、ほぼ弊社だけかと思います。

もしご関心をお持ちいただけましたら、
御社のサービスに合わせた活用ラフ案を1つお作りし、15分ほどでご説明させていただきます。

ぜひ候補日を2〜3ついただけますと幸いです。
よろしくお願いいたします。

P.S. 実際の診断はこちらから1〜2分でご体験いただけます：
https://lovecharacter64.jp/quiz`
  },
  {
    target: '住宅・リフォーム・不動産',
    subject: '来場・資料請求の獲得単価、"診断"で下げませんか（ラブキャラ）',
    body: `ご担当者様

突然のご連絡失礼いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田と申します。

住宅・不動産の集客では、検討期間が長いお客様に対して
広告からの来場予約・資料請求の単価が上がり続け、
検討初期の"まだ動かない層"との接点が作れない、というお声をよく伺います。

御社でも近い状況はございませんでしょうか。

私たちは「理想の暮らしタイプ診断」「あなたに合う間取り診断」のような診断コンテンツで、
検討初期のお客様が"自分の理想"を数問で自分ごと化し、
診断→結果別ページ→来場予約・資料請求→LINE友だち化まで、
長期検討を前提とした導線をまるごと設計・制作しています。

自社の恋愛診断は広告費をかけず累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。

もしご関心をお持ちいただけましたら、
御社の商品・物件に合わせた診断のラフ案を1つお作りし、
15分ほどでご説明させていただきます。

ぜひ候補日を2〜3ついただけますと幸いです。
よろしくお願いいたします。

P.S. 実際の診断はこちらから1〜2分でご体験いただけます（恋愛診断ですが、"数問で自分ごと化しシェアしたくなる設計"をご覧ください）：
https://lovecharacter64.jp/quiz`
  },
  {
    target: '通信・金融・生活インフラ',
    subject: '若年層との接点とプラン選びの迷い、"診断"で解決しませんか（ラブキャラ）',
    body: `ご担当者様

突然のご連絡失礼いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田と申します。

通信・金融・インフラ業界では、サービスの違いが若年層に伝わりにくく、
「プランが複雑で選べない」まま比較サイト経由の価格競争に巻き込まれる、
Z世代とのブランド接点が作れない、というお声をよく伺います。

御社でも近い状況はございませんでしょうか。

私たちは「あなたに合うプラン診断」「お金・スマホの使い方タイプ診断」のような診断コンテンツで、
複雑なサービスを"自分ごと"に翻訳し、
診断→結果別の案内ページ→申込・相談→LINE友だち化まで、導線をまるごと設計・制作しています。
業界の広告表現ルールに配慮した設計で制作します。

自社の恋愛診断は広告費をかけず累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。

もしご関心をお持ちいただけましたら、
御社のサービスに合わせた診断のラフ案を1つお作りし、
15分ほどでご説明させていただきます。

ぜひ候補日を2〜3ついただけますと幸いです。
よろしくお願いいたします。

P.S. 実際の診断はこちらから1〜2分でご体験いただけます（恋愛診断ですが、"数問で自分ごと化しシェアしたくなる設計"をご覧ください）：
https://lovecharacter64.jp/quiz`
  },
  {
    target: 'メーカー（家電・文具・自動車・バイク）',
    subject: '「どれを選べばいいか分からない」離脱、"診断"で解決しませんか（ラブキャラ）',
    body: `ご担当者様

突然のご連絡失礼いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田と申します。

メーカー様からは、ラインナップが充実しているほどお客様が
「自分にはどれが合うのか」を選びきれず、比較検討のまま離脱してしまう、
若年層に商品の魅力が届かない、というお声をよく伺います。

御社でも近い状況はございませんでしょうか。

私たちは「あなたにぴったりの○○診断」のような商品マッチ診断で、
お客様が"自分に合う一台・一本"を数問で自分ごと化し、
診断→結果別の商品ページ→EC・店頭送客→LINE友だち化まで、導線をまるごと設計・制作しています。

自社の恋愛診断は広告費をかけず累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。

もしご関心をお持ちいただけましたら、
御社の商品ラインに合わせた診断のラフ案を1つお作りし、
15分ほどでご説明させていただきます。

ぜひ候補日を2〜3ついただけますと幸いです。
よろしくお願いいたします。

P.S. 実際の診断はこちらから1〜2分でご体験いただけます（恋愛診断ですが、"数問で自分ごと化しシェアしたくなる設計"をご覧ください）：
https://lovecharacter64.jp/quiz`
  },
  {
    target: '教育・スクール',
    subject: '体験授業・入塾の申込、"診断"で増やしませんか（ラブキャラ）',
    body: `ご担当者様

突然のご連絡失礼いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田と申します。

塾・スクール運営では、広告や紹介だけでは新規の体験申込が伸びず、
「うちの子・自分に合うか分からない」という不安が申込の手前の壁になっている、
というお声をよく伺います。

御社でも近い状況はございませんでしょうか。

私たちは「学び方タイプ診断」「向いてる習い事診断」のような診断コンテンツで、
生徒本人と保護者が"合いそう"を数問で自分ごと化し、
診断→結果別ページ→体験授業・見学申込→LINE友だち化まで、集客導線をまるごと設計・制作しています。

自社の恋愛診断は広告費をかけず累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。
利用者の中心は10代です。

もしご関心をお持ちいただけましたら、
御社のコースに合わせた診断のラフ案を1つお作りし、
15分ほどでご説明させていただきます。

ぜひ候補日を2〜3ついただけますと幸いです。
よろしくお願いいたします。

P.S. 実際の診断はこちらから1〜2分でご体験いただけます（恋愛診断ですが、"数問で自分ごと化しシェアしたくなる設計"をご覧ください）：
https://lovecharacter64.jp/quiz`
  },
  {
    target: '保育園・幼稚園・こども園',
    subject: '保育士採用の応募数、"診断"で増やしませんか（ラブキャラ）',
    body: `ご担当者様

突然のご連絡失礼いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田と申します。

保育業界では、求人媒体にコストをかけても保育士の応募が集まらず、
園の魅力や雰囲気が伝わる前に他園と比較されて終わってしまう、
というお声をよく伺います。

貴園でも近い状況はございませんでしょうか。

私たちは「保育タイプ診断」「あなたに合う園の雰囲気診断」のような診断コンテンツで、
求職者が"自分に合う園"を数問で自分ごと化し、
診断→結果別の園紹介ページ→見学・応募→LINE友だち化まで、採用導線をまるごと設計・制作しています。

自社の恋愛診断は広告費をかけず累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。
利用者の中心は、まさに保育士志望者と重なる10代〜20代の女性層です。

もしご関心をお持ちいただけましたら、
貴園に合わせた診断のラフ案を1つお作りし、15分ほどでご説明させていただきます。

ぜひ候補日を2〜3ついただけますと幸いです。
よろしくお願いいたします。

P.S. 実際の診断はこちらから1〜2分でご体験いただけます（恋愛診断ですが、"数問で自分ごと化しシェアしたくなる設計"をご覧ください）：
https://lovecharacter64.jp/quiz`
  },
  {
    // どの業界カテゴリにも一致しなかった場合に使用する汎用テンプレート
    target: 'その他の業界（汎用版）',
    subject: '広告費ゼロで累計8,000万回 — "診断"で御社の集客を変えるご提案',
    body: `ご担当者様

はじめてご連絡いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田です。

私たちの診断は、広告費をかけずに累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。

この"シェアされて自然に広がる診断"の仕組みを、
さまざまな業界の集客・販促向けに「○○タイプ診断」として提供しています。
広告費の高騰／若年層との接点不足／申込・購入の一歩手前での離脱
こうした課題に、診断→結果別ページ→申込・予約・購入→LINEの導線を
まるごと設計・制作でお応えします。

御社の事業に合わせた診断のラフ案を1つお持ちし、
15分でご説明させていただけないでしょうか。

ぜひ、ご都合のよい候補日をいただけますと幸いです。
よろしくお願いいたします。

P.S. 拡散の元になっている診断そのものは、こちらから2分〜3分でご体験いただけます：
https://lovecharacter64.jp/quiz`
  }
];

/**
 * スプレッドシートを開いたときにメニューを追加
 */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('ラブキャラ営業メール')
    .addItem('対象スプシ・対象件数を確認する', 'debugCheckTargetSpreadsheet')
    .addItem('書き込みテストをする', 'testWriteToSheet')
    .addSeparator()
    .addItem('下書きを作成する', 'manualCreateDraftsForAllSheets')
    .addItem('送信済みを確認する', 'manualCheckSentEmailsForAllSheets')
    .addSeparator()
    .addItem('下書き作成中を未対応に戻す', 'resetProcessingRows')
    .addSeparator()
    .addItem('毎日実行トリガーを設定する', 'createDailyTriggers')
    .addItem('毎日実行トリガーを削除する', 'deleteDailyTriggers')
    .addToUi();
}

function getSalesSpreadsheet() {
  return SpreadsheetApp.openById(SALES_SPREADSHEET_ID);
}

function getTemplateSpreadsheet() {
  return SpreadsheetApp.openById(TEMPLATE_SPREADSHEET_ID);
}

function manualCreateDraftsForAllSheets() {
  const result = createDraftsForAllSheetsCore();
  showMessage(
    `下書き作成が完了しました。\n\n対象シート：${SALES_SHEET_NAME}\n下書き作成：${result.created}件\nエラー：${result.error}件`
  );
}

function scheduledCreateDraftsForAllSheets() {
  const result = createDraftsForAllSheetsCore();
  Logger.log(`下書き作成完了：${result.created}件 / エラー：${result.error}件 / 対象シート：${SALES_SHEET_NAME}`);
}

/**
 * 互換のため旧関数名を残しつつ、実際には診断サイト受託シートのみ処理する
 */
function createDraftsForAllSheetsCore() {
  const lock = LockService.getScriptLock();

  try {
    lock.waitLock(30000);

    const salesSS = getSalesSpreadsheet();
    const salesSheet = getSalesSheetOrThrow(salesSS);
    const templateMap = loadUnifiedTemplateMap();

    Logger.log(`スクリプト版: ${SCRIPT_VERSION}`);
    Logger.log(`処理対象スプレッドシート名: ${salesSS.getName()}`);
    Logger.log(`処理対象スプレッドシートID: ${salesSS.getId()}`);
    Logger.log(`処理対象シート: ${salesSheet.getName()}`);
    Logger.log(`テンプレート件数: ${Object.keys(templateMap).length}`);

    return createDraftsForOneSheet(salesSheet, templateMap, DAILY_DRAFT_LIMIT);

  } catch (e) {
    Logger.log(`全体エラー: ${e.message}`);
    return { created: 0, error: 1 };
  } finally {
    try {
      lock.releaseLock();
    } catch (e) {
      Logger.log(`ロック解除エラー: ${e.message}`);
    }
  }
}

function createDraftsForOneSheet(sheet, templateMap, limit) {
  const lastRow = sheet.getLastRow();
  const lastCol = Math.max(sheet.getLastColumn(), COL_ERROR);

  if (lastRow < 2) {
    return { created: 0, error: 0 };
  }

  const values = sheet.getRange(1, 1, lastRow, lastCol).getValues();
  let createdCount = 0;
  let errorCount = 0;

  for (let i = 1; i < values.length; i++) {
    if (createdCount >= limit) {
      break;
    }

    const row = values[i];
    const rowNumber = i + 1;
    const industry = normalizeText(row[COL_INDUSTRY - 1]);
    const company = normalizeText(row[COL_COMPANY - 1]);
    const email = normalizeText(row[COL_EMAIL - 1]);
    const approach = normalizeText(row[COL_APPROACH - 1]);
    const status = normalizeText(row[COL_STATUS - 1]);

    if (approach !== APPROACH_EMAIL_CANDIDATE) {
      continue;
    }

    if (!isEligibleDraftStatus(status)) {
      continue;
    }

    const validationError = validateRow(industry, company, email, templateMap);
    if (validationError) {
      markError(sheet, rowNumber, validationError);
      errorCount++;
      continue;
    }

    const template = resolveTemplate(templateMap, industry);
    const subject = template.subject;
    const body = buildEmailBody(company, template.body);

    try {
      const processingAt = formatDateTime(new Date());
      sheet.getRange(rowNumber, COL_STATUS).setValue(STATUS_PROCESSING);
      sheet.getRange(rowNumber, COL_DATE_NOTE).setValue(`下書き作成開始：${processingAt}`);
      sheet.getRange(rowNumber, COL_ERROR).setValue('');
      SpreadsheetApp.flush();

      const writtenStatus = normalizeText(sheet.getRange(rowNumber, COL_STATUS).getValue());
      if (writtenStatus !== STATUS_PROCESSING) {
        throw new Error('スプレッドシートへの書き込み確認に失敗しました。Gmail下書きは作成していません。');
      }

      GmailApp.createDraft(email, subject, body);

      const draftCreatedAt = formatDateTime(new Date());
      sheet.getRange(rowNumber, COL_STATUS).setValue(STATUS_DRAFT_CREATED);
      sheet.getRange(rowNumber, COL_DATE_NOTE).setValue(`下書き作成：${draftCreatedAt}`);
      sheet.getRange(rowNumber, COL_ERROR).setValue('');
      SpreadsheetApp.flush();

      createdCount++;
    } catch (e) {
      markError(sheet, rowNumber, `Gmail下書き作成エラー: ${e.message}`);
      errorCount++;
    }
  }

  return {
    created: createdCount,
    error: errorCount
  };
}

function manualCheckSentEmailsForAllSheets() {
  const result = checkSentEmailsForAllSheetsCore();
  showMessage(
    `送信済み確認が完了しました。\n\n対象シート：${SALES_SHEET_NAME}\nメール送信済みに更新：${result.updated}件\n確認対象：${result.checked}件\nエラー：${result.error}件`
  );
}

function scheduledCheckSentEmailsForAllSheets() {
  const result = checkSentEmailsForAllSheetsCore();
  Logger.log(`送信済み確認完了：更新 ${result.updated}件 / 確認対象 ${result.checked}件 / エラー ${result.error}件 / 対象シート：${SALES_SHEET_NAME}`);
}

function checkSentEmailsForAllSheetsCore() {
  try {
    const salesSS = getSalesSpreadsheet();
    const salesSheet = getSalesSheetOrThrow(salesSS);
    const templateMap = loadUnifiedTemplateMap();

    Logger.log(`送信済み確認対象シート: ${salesSheet.getName()}`);
    return checkSentEmailsForOneSheet(salesSheet, templateMap);
  } catch (e) {
    Logger.log(`送信済み確認の全体エラー: ${e.message}`);
    return { checked: 0, updated: 0, error: 1 };
  }
}

function checkSentEmailsForOneSheet(sheet, templateMap) {
  const lastRow = sheet.getLastRow();
  const lastCol = Math.max(sheet.getLastColumn(), COL_ERROR);

  if (lastRow < 2) {
    return { checked: 0, updated: 0, error: 0 };
  }

  const values = sheet.getRange(1, 1, lastRow, lastCol).getValues();
  let checkedCount = 0;
  let updatedCount = 0;
  let errorCount = 0;

  for (let i = 1; i < values.length; i++) {
    const row = values[i];
    const rowNumber = i + 1;
    const industry = normalizeText(row[COL_INDUSTRY - 1]);
    const email = normalizeText(row[COL_EMAIL - 1]);
    const status = normalizeText(row[COL_STATUS - 1]);
    const dateNoteValue = row[COL_DATE_NOTE - 1];

    if (status !== STATUS_DRAFT_CREATED) {
      continue;
    }

    checkedCount++;

    if (!email) {
      markError(sheet, rowNumber, '送信済み確認エラー: メールアドレスが空欄です');
      errorCount++;
      continue;
    }

    if (!isValidEmail(email)) {
      markError(sheet, rowNumber, '送信済み確認エラー: メールアドレス形式が不正です');
      errorCount++;
      continue;
    }

    const draftDate = parseDraftCreatedDate(dateNoteValue);
    if (!draftDate) {
      markError(sheet, rowNumber, '送信済み確認エラー: N列から下書き作成日時を読み取れません');
      errorCount++;
      continue;
    }

    const template = resolveTemplate(templateMap, industry);
    if (!template) {
      markError(sheet, rowNumber, `送信済み確認エラー: メールテンプレートが見つかりません（汎用テンプレート「${DEFAULT_TEMPLATE_TARGET}」も未登録です）`);
      errorCount++;
      continue;
    }

    const subject = template.subject;

    try {
      const sentDate = findSentEmailDate(email, subject, draftDate);
      if (sentDate) {
        const checkedAt = formatDateTime(new Date());
        const currentNote = normalizeText(sheet.getRange(rowNumber, COL_DATE_NOTE).getValue());
        const updatedNote = appendSentCheckedNote(currentNote, checkedAt);

        sheet.getRange(rowNumber, COL_STATUS).setValue(STATUS_SENT);
        sheet.getRange(rowNumber, COL_DATE_NOTE).setValue(updatedNote);
        sheet.getRange(rowNumber, COL_ERROR).setValue('');
        SpreadsheetApp.flush();

        updatedCount++;
      }
    } catch (e) {
      markError(sheet, rowNumber, `送信済み確認エラー: ${e.message}`);
      errorCount++;
    }
  }

  return {
    checked: checkedCount,
    updated: updatedCount,
    error: errorCount
  };
}

function findSentEmailDate(email, subject, draftDate) {
  const afterDate = formatDateForGmailSearch(addDays(draftDate, -1));
  const safeSubject = escapeGmailSearchText(subject);
  const query = `in:sent to:${email} subject:"${safeSubject}" after:${afterDate}`;
  const threads = GmailApp.search(query, 0, 20);

  for (let i = 0; i < threads.length; i++) {
    const messages = threads[i].getMessages();

    for (let j = 0; j < messages.length; j++) {
      const message = messages[j];
      const messageDate = message.getDate();
      const messageTo = normalizeText(message.getTo());
      const messageSubject = normalizeText(message.getSubject());

      if (messageDate < draftDate) {
        continue;
      }

      if (!messageTo.toLowerCase().includes(email.toLowerCase())) {
        continue;
      }

      if (messageSubject !== subject) {
        continue;
      }

      return messageDate;
    }
  }

  return null;
}

function loadUnifiedTemplateMap() {
  const templateMap = loadEmbeddedTemplateMap();

  try {
    const templateSS = getTemplateSpreadsheet();
    const templateSheet = templateSS.getSheetByName(TEMPLATE_SHEET_NAME);

    if (!templateSheet) {
      Logger.log(`テンプレートシートが見つからないため、埋め込みテンプレートのみ使用します: ${TEMPLATE_SHEET_NAME}`);
      return templateMap;
    }

    const sheetTemplateMap = loadTemplateMap(templateSheet);
    Object.keys(sheetTemplateMap).forEach(key => {
      templateMap[key] = sheetTemplateMap[key];
    });

    return templateMap;
  } catch (e) {
    Logger.log(`テンプレート表の読込に失敗したため、埋め込みテンプレートのみ使用します: ${e.message}`);
    return templateMap;
  }
}

function loadEmbeddedTemplateMap() {
  const templateMap = {};

  EMBEDDED_TEMPLATE_ROWS.forEach(template => {
    const key = normalizeKey(template.target);
    templateMap[key] = {
      target: template.target,
      subject: normalizeText(template.subject),
      body: normalizeTemplateBody(template.body)
    };
  });

  return templateMap;
}

function loadTemplateMap(templateSheet) {
  const lastRow = templateSheet.getLastRow();
  const lastCol = Math.max(templateSheet.getLastColumn(), TEMPLATE_COL_BODY);

  if (lastRow < 2) {
    return {};
  }

  const values = templateSheet.getRange(1, 1, lastRow, lastCol).getValues();
  const templateMap = {};

  values.forEach(row => {
    const target = normalizeText(row[TEMPLATE_COL_TARGET - 1]);
    const subject = normalizeText(row[TEMPLATE_COL_SUBJECT - 1]);
    const body = normalizeText(row[TEMPLATE_COL_BODY - 1]);

    if (!target || target === 'ターゲット') {
      return;
    }

    if (!subject || subject === 'お問い合わせフォーム・メール（件名）') {
      return;
    }

    if (!body || body === 'お問い合わせフォーム・メール・トーク例（本文）') {
      return;
    }

    templateMap[normalizeKey(target)] = {
      target: target,
      subject: subject,
      body: normalizeTemplateBody(body)
    };
  });

  return templateMap;
}

/**
 * 業界カテゴリに対応するテンプレートを返す。
 * 完全一致するテンプレートが無い（未一致・空欄を含む）場合は汎用テンプレートを返す。
 */
function resolveTemplate(templateMap, industry) {
  const key = normalizeKey(industry);
  if (key && templateMap[key]) {
    return templateMap[key];
  }
  return templateMap[normalizeKey(DEFAULT_TEMPLATE_TARGET)] || null;
}

/**
 * 会社名を先頭に付け、末尾に署名を添えて本文を組み立てる。
 * テンプレート本文には「ご担当者様」の宛名・結び・P.S.（診断リンク）まで含まれている前提。
 */
function buildEmailBody(company, templateBody) {
  return `${company}
${normalizeTemplateBody(templateBody)}

${EMAIL_SIGNATURE}`;
}

function validateRow(industry, company, email, templateMap) {
  if (!company) {
    return '会社名が空欄です';
  }

  if (!email) {
    return 'メールアドレスが空欄です';
  }

  if (!isValidEmail(email)) {
    return 'メールアドレス形式が不正です';
  }

  // 業界カテゴリが一致しない場合は汎用テンプレートにフォールバックするため、
  // 汎用テンプレートすら存在しないときだけエラーとする。
  if (!resolveTemplate(templateMap, industry)) {
    return `メールテンプレートが見つかりません（汎用テンプレート「${DEFAULT_TEMPLATE_TARGET}」も未登録です）`;
  }

  return '';
}

function markError(sheet, rowNumber, message) {
  sheet.getRange(rowNumber, COL_STATUS).setValue(STATUS_ERROR);
  sheet.getRange(rowNumber, COL_ERROR).setValue(message);
  SpreadsheetApp.flush();
}

function resetProcessingRows() {
  const salesSS = getSalesSpreadsheet();
  const sheet = getSalesSheetOrThrow(salesSS);
  const lastRow = sheet.getLastRow();
  let resetCount = 0;

  if (lastRow >= 2) {
    const values = sheet.getRange(2, COL_STATUS, lastRow - 1, 1).getValues();

    values.forEach((row, index) => {
      const status = normalizeText(row[0]);
      if (status === STATUS_PROCESSING) {
        const rowNumber = index + 2;
        sheet.getRange(rowNumber, COL_STATUS).setValue(STATUS_UNTOUCHED);
        sheet.getRange(rowNumber, COL_DATE_NOTE).setValue('');
        sheet.getRange(rowNumber, COL_ERROR).setValue('');
        resetCount++;
      }
    });
  }

  SpreadsheetApp.flush();
  showMessage(`下書き作成中の行を未対応に戻しました。\n\n対象シート：${SALES_SHEET_NAME}\nリセット件数：${resetCount}件`);
}

function debugCheckTargetSpreadsheet() {
  const salesSS = getSalesSpreadsheet();
  const sheet = getSalesSheetOrThrow(salesSS);
  const lastRow = sheet.getLastRow();

  Logger.log(`スクリプト版: ${SCRIPT_VERSION}`);
  Logger.log(`GASが見ているスプレッドシート名: ${salesSS.getName()}`);
  Logger.log(`GASが見ているスプレッドシートID: ${salesSS.getId()}`);
  Logger.log(`GASが見ているスプレッドシートURL: ${salesSS.getUrl()}`);
  Logger.log(`対象シート: ${sheet.getName()}`);

  if (lastRow < 2) {
    Logger.log(`${sheet.getName()}: データ行なし`);
    showMessage('対象スプレッドシートと対象件数をログに出力しました。Apps Scriptの実行ログを確認してください。');
    return;
  }

  const values = sheet.getRange(2, 1, lastRow - 1, COL_ERROR).getValues();
  let mailCandidateCount = 0;
  let untouchedCount = 0;
  let targetCount = 0;

  values.forEach(row => {
    const approach = normalizeText(row[COL_APPROACH - 1]);
    const status = normalizeText(row[COL_STATUS - 1]);

    if (approach === APPROACH_EMAIL_CANDIDATE) {
      mailCandidateCount++;
    }

    if (isEligibleDraftStatus(status)) {
      untouchedCount++;
    }

    if (approach === APPROACH_EMAIL_CANDIDATE && isEligibleDraftStatus(status)) {
      targetCount++;
    }
  });

  Logger.log(`${sheet.getName()}: メール候補 ${mailCandidateCount}件 / 未対応相当 ${untouchedCount}件 / 今回対象 ${targetCount}件 / 上限 ${DAILY_DRAFT_LIMIT}件`);
  showMessage('対象スプレッドシートと対象件数をログに出力しました。Apps Scriptの実行ログを確認してください。');
}

function testWriteToSheet() {
  const salesSS = getSalesSpreadsheet();
  const sheet = getSalesSheetOrThrow(salesSS);

  sheet.getRange('M2').setValue('書き込みテスト');
  sheet.getRange('N2').setValue(`テスト：${formatDateTime(new Date())}`);
  sheet.getRange('O2').setValue('テスト完了');
  SpreadsheetApp.flush();

  showMessage(`${SALES_SHEET_NAME} の M2/N2/O2 に書き込みテストをしました。確認後、必要に応じて元に戻してください。`);
}

function createDailyTriggers() {
  deleteDailyTriggers();

  ScriptApp.newTrigger('scheduledCreateDraftsForAllSheets')
    .timeBased()
    .everyDays(1)
    .atHour(9)
    .create();

  ScriptApp.newTrigger('scheduledCheckSentEmailsForAllSheets')
    .timeBased()
    .everyDays(1)
    .atHour(7)
    .create();

  showMessage(
    `毎日実行トリガーを設定しました。\n\n対象シート：${SALES_SHEET_NAME}\n下書き作成：毎日9時台（最大${DAILY_DRAFT_LIMIT}件）\n送信済み確認：毎日7時〜8時ごろ`
  );
}

function deleteDailyTriggers() {
  const targetFunctions = [
    'scheduledCreateDraftsForAllSheets',
    'scheduledCheckSentEmailsForAllSheets'
  ];

  ScriptApp.getProjectTriggers().forEach(trigger => {
    if (targetFunctions.includes(trigger.getHandlerFunction())) {
      ScriptApp.deleteTrigger(trigger);
    }
  });
}

function getSalesSheetOrThrow(salesSS) {
  const sheet = salesSS.getSheetByName(SALES_SHEET_NAME);
  if (!sheet) {
    throw new Error(`営業リストシートが見つかりません: ${SALES_SHEET_NAME}`);
  }
  return sheet;
}

function isEligibleDraftStatus(status) {
  return !status || status === STATUS_UNTOUCHED;
}

function normalizeTemplateBody(value) {
  return normalizeText(value).replace(/\r\n/g, '\n').replace(/\r/g, '\n');
}

function normalizeKey(value) {
  return normalizeText(value)
    .replace(/　/g, ' ')
    .replace(/\s+/g, ' ');
}

function isValidEmail(email) {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

function normalizeText(value) {
  if (value === null || value === undefined) {
    return '';
  }
  return String(value).trim();
}

function formatDateTime(date) {
  return Utilities.formatDate(date, Session.getScriptTimeZone(), 'yyyy/MM/dd HH:mm');
}

function formatDateForGmailSearch(date) {
  return Utilities.formatDate(date, Session.getScriptTimeZone(), 'yyyy/MM/dd');
}

function addDays(date, days) {
  const copiedDate = new Date(date.getTime());
  copiedDate.setDate(copiedDate.getDate() + days);
  return copiedDate;
}

function escapeGmailSearchText(text) {
  return normalizeText(text).replace(/"/g, '');
}

function parseDraftCreatedDate(value) {
  if (!value) {
    return null;
  }

  if (Object.prototype.toString.call(value) === '[object Date]') {
    return value;
  }

  const text = normalizeText(value);
  const match = text.match(/下書き作成：(\d{4})\/(\d{2})\/(\d{2}) (\d{2}):(\d{2})/);

  if (!match) {
    return null;
  }

  return new Date(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3]),
    Number(match[4]),
    Number(match[5])
  );
}

function appendSentCheckedNote(currentNote, checkedAt) {
  const sentCheckedText = `送信確認：${checkedAt}`;

  if (!currentNote) {
    return sentCheckedText;
  }

  if (currentNote.includes('送信確認：')) {
    return currentNote.replace(/送信確認：\d{4}\/\d{2}\/\d{2} \d{2}:\d{2}/, sentCheckedText);
  }

  return `${currentNote}\n${sentCheckedText}`;
}

function showMessage(message) {
  try {
    SpreadsheetApp.getUi().alert(message);
  } catch (e) {
    Logger.log(message);
  }
}
