/***** ラブキャラ 営業メール下書き作成・送信済み確認エージェント 完全版（2026-07-14） *****/

/**
 * 主な変更点
 * 1. 対象シートを「整形済み_診断サイト受託」のみに限定
 * 2. アプローチ方法が「メール候補」の行だけを対象化
 * 3. 1日あたり15件のGmail下書きを作成
 * 4. 業界カテゴリ（ターゲット）ごとに件名・本文を切り替え
 * 5. テンプレート表が未更新でも動くよう、最新テンプレートをスクリプト内にも保持
 * 6. 「メール候補」かつステータスが「未対応」または「エラー」の行を下書き作成対象にする
 *
 * 2026-07-12更新
 * - 業界カテゴリごとの件名・本文を最新のトーク例に全面差し替え
 * - 本文テンプレートに「ご担当者様」の宛名・結び・P.S.（診断リンク）まで含める形へ変更
 * - buildEmailBody は会社名を先頭に付け、末尾に署名（株式会社ラブキャラ / 奥田）を添える
 * - 業界カテゴリがどのテンプレートにも一致しない（空欄含む）場合は
 *   汎用テンプレート「その他の業界（汎用版）」にフォールバックして送る
 *
 * 2026-07-14更新
 * - 受託制作ターゲット（業界カテゴリ）ごとの件名・本文を最新版に全面差し替え
 *   （全18カテゴリ＝17業界＋汎用版。ターゲット名・分岐ロジックは従来どおり）
 */

const SCRIPT_VERSION = '2026-07-14';

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
    subject: '広告費ゼロで累計8,000万回 — 診断で御社ECの初回購入を伸ばすご提案',
    body: `ご担当者様

はじめてご連絡いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田です。

私たちの診断は、広告費をかけずに累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。

この"シェアされて自然に広がる診断"の仕組みを、
D2C/EC向けの「商品レコメンド診断」に転用しています。
SKUが多くて選びきれない／広告CPAが高い／初回購入の壁が高い
こうした課題に、診断→結果別LP→LINE→購入の導線をまるごと設計・制作でお応えします。

御社の商品ラインに合わせた診断のラフ案を1つお持ちし、
15分でご説明させていただけないでしょうか。

ぜひ、ご都合のよい候補日をいただけますと幸いです。
よろしくお願いいたします。

P.S. 拡散の元になっている診断そのものは、こちらから2分〜3分でご体験いただけます：
https://lovecharacter64.jp/quiz`
  },
  {
    target: 'Z世代向け消費財メーカー（菓子・飲料・日用品）',
    subject: '広告費ゼロで累計8,000万回 — 診断キャンペーンで御社ブランドにZ世代の波を',
    body: `ご担当者様

はじめてご連絡いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田です。

私たちの診断は、広告費をかけずに累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。
利用者の中心はまさにZ世代です。

この"シェアされて自然に広がる診断"の仕組みを、
消費財メーカー向けの「商品タイプ診断キャンペーン」として提供しています。
SNSでの話題化が続かない／若年層とのブランド接点が細い／キャンペーンが値引き頼みになる
こうした課題に、診断→結果シェア→商品指名→LINEの導線をまるごと設計・制作でお応えします。

御社の商品に合わせた診断キャンペーンのラフ案を1つお持ちし、
15分でご説明させていただけないでしょうか。

ぜひ、ご都合のよい候補日をいただけますと幸いです。
よろしくお願いいたします。

P.S. 拡散の元になっている診断そのものは、こちらから2分〜3分でご体験いただけます：
https://lovecharacter64.jp/quiz`
  },
  {
    target: '専門学校・大学・通信制高校（学生募集）',
    subject: '広告費ゼロで累計8,000万回 — 診断で貴校の学生募集を伸ばすご提案',
    body: `ご担当者様

はじめてご連絡いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田です。

私たちの診断は、広告費をかけずに累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。
利用者の中心は、まさに進路選択期の10代〜20代前半です。

この"シェアされて自然に広がる診断"の仕組みを、
学校向けの「学科・進路タイプ診断」に転用しています。
資料請求・オーキャン申込の獲得単価が高い／広告が高校生本人に届かない／学校の魅力が伝わる前に離脱される
こうした課題に、診断→結果別ページ→申込・LINEの導線をまるごと設計・制作でお応えします。

貴校の学科構成に合わせた診断のラフ案を1つお持ちし、
15分でご説明させていただけないでしょうか。

ぜひ、ご都合のよい候補日をいただけますと幸いです。
よろしくお願いいたします。

P.S. 拡散の元になっている診断そのものは、こちらから2分〜3分でご体験いただけます：
https://lovecharacter64.jp/quiz`
  },
  {
    target: '採用/求人/人材・採用難業界',
    subject: '広告費ゼロで累計8,000万回 — 診断で若手エントリーを増やすご提案',
    body: `ご担当者様

はじめてご連絡いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田です。

私たちの診断は、広告費をかけずに累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。
利用者の中心は、まさに就職・転職を考える10代後半〜20代です。

この"シェアされて自然に広がる診断"の仕組みを、
採用向けの「社風・職種マッチ診断」に転用しています。
ナビ媒体頼みでエントリー単価が高い／説明会に人が集まらない／内定辞退が多い
こうした課題に、診断→結果別ページ→エントリー・LINEの導線をまるごと設計・制作でお応えします。

御社の採用課題に合わせた診断のラフ案を1つお持ちし、
15分でご説明させていただけないでしょうか。

ぜひ、ご都合のよい候補日をいただけますと幸いです。
よろしくお願いいたします。

P.S. 拡散の元になっている診断そのものは、こちらから2分〜3分でご体験いただけます：
https://lovecharacter64.jp/quiz`
  },
  {
    target: 'ゲーム・アプリ・エンタメサービス運営',
    subject: 'ABEMA公式番組コラボで13日100万PV — 診断で御社タイトルの話題化を作るご提案',
    body: `ご担当者様

はじめてご連絡いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田です。

私たちがABEMA公式番組と共同開発した診断は、
放送開始からわずか13日で100万PVを突破し、番組への新規流入にもつながりました。
自社の恋愛診断も広告費をかけず累計8,000万回以上利用されています。

この"シェアされて自然に広がる診断"の仕組みを、
ゲーム・アプリ・エンタメサービスの「キャラ診断・タイプ診断キャンペーン」として提供しています。
CPI高騰／話題化施策が単発で終わる／休眠復帰の打ち手がない
こうした課題に、診断→シェア→DL/復帰→LINE・プッシュの導線をまるごと設計・制作でお応えします。

御社のタイトルに合わせた診断キャンペーンのラフ案を1つお持ちし、
15分でご説明させていただけないでしょうか。

ぜひ、ご都合のよい候補日をいただけますと幸いです。
よろしくお願いいたします。

P.S. 拡散の元になっている診断そのものは、こちらから2分〜3分でご体験いただけます：
https://lovecharacter64.jp/quiz`
  },
  {
    target: '推し活・IP・ファンビジネス',
    subject: 'ABEMA公式番組コラボで13日100万PV — 御社IPのファン拡大に"診断"を',
    body: `ご担当者様

はじめてご連絡いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田です。

私たちがABEMA公式番組と共同開発した診断は、
放送開始からわずか13日で100万PVを突破し、番組への新規流入にもつながりました。
自社で64タイプの恋愛診断IPを運営し、累計8,000万回以上、広告費ゼロで利用されています。

同じIP・ファンビジネスを自社でやっているからこそ、
「推しタイプ診断」「キャラマッチ診断」のようなコラボ診断で、
ファンがシェアしたくなるUGCの波と、新規ファンの流入導線を設計できます。
診断→シェア→ファンクラブ・LINE→グッズ・イベントまで一括で制作します。

御社のIP・タレントに合わせたコラボ診断のラフ案を1つお持ちし、
15分でご説明させていただけないでしょうか。

ぜひ、ご都合のよい候補日をいただけますと幸いです。
よろしくお願いいたします。

P.S. 拡散の元になっている診断そのものは、こちらから2分〜3分でご体験いただけます：
https://lovecharacter64.jp/quiz`
  },
  {
    target: '音楽・ライブ・フェス',
    subject: 'ABEMA公式番組コラボで13日100万PV — 診断で御社の公演・フェスに新規層を',
    body: `ご担当者様

はじめてご連絡いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田です。

私たちがABEMA公式番組と共同開発した診断は、
放送開始からわずか13日で100万PVを突破し、番組への新規流入にもつながりました。
自社の恋愛診断も広告費をかけず累計8,000万回以上利用されています。

この"シェアされて自然に広がる診断"の仕組みを、
音楽・ライブ・フェス向けの「アーティスト診断」「フェスタイプ診断」として提供しています。
既存ファン以外に届かない／SNSの話題化が一瞬で終わる／ライト層がチケット購入まで進まない
こうした課題に、診断→シェア→チケット・配信・LINEの導線をまるごと設計・制作でお応えします。

御社の公演・フェスに合わせた診断企画のラフ案を1つお持ちし、
15分でご説明させていただけないでしょうか。

ぜひ、ご都合のよい候補日をいただけますと幸いです。
よろしくお願いいたします。

P.S. 拡散の元になっている診断そのものは、こちらから2分〜3分でご体験いただけます：
https://lovecharacter64.jp/quiz`
  },
  {
    target: '商業施設・小売施設',
    subject: '広告費ゼロで累計8,000万回 — 診断イベントで御施設に若年客の来館を',
    body: `ご担当者様

はじめてご連絡いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田です。

私たちの診断は、広告費をかけずに累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。
利用者の中心は10代〜20代の若年層です。

この"シェアされて自然に広がる診断"の仕組みを、
商業施設向けの「来館・回遊型の診断イベント」として提供しています。
若年層の来館減／イベントがテナント送客につながらない／アプリ・LINE会員の伸び悩み
こうした課題に、診断→結果別の店舗案内→来館・回遊→会員化の導線をまるごと設計・制作でお応えします。

御施設に合わせた診断企画のラフ案を1つお持ちし、
15分でご説明させていただけないでしょうか。

ぜひ、ご都合のよい候補日をいただけますと幸いです。
よろしくお願いいたします。

P.S. 拡散の元になっている診断そのものは、こちらから2分〜3分でご体験いただけます：
https://lovecharacter64.jp/quiz`
  },
  {
    target: 'フィットネス・パーソナルジム',
    subject: '広告費ゼロで累計8,000万回 — 診断で御社ジムの体験予約を増やすご提案',
    body: `ご担当者様

はじめてご連絡いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田です。

私たちの診断は、広告費をかけずに累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。

この"シェアされて自然に広がる診断"の仕組みを、
フィットネス向けの「トレーニングタイプ診断」に転用しています。
広告CPAの高騰／「自分に続けられるか不安」な層の離脱／入会後の継続率
こうした課題に、診断→結果別ページ→体験予約→LINEの導線をまるごと設計・制作でお応えします。
結果タイプ別のフォロー配信で、入会後の継続支援にも使えます。

御社のプログラムに合わせた診断のラフ案を1つお持ちし、
15分でご説明させていただけないでしょうか。

ぜひ、ご都合のよい候補日をいただけますと幸いです。
よろしくお願いいたします。

P.S. 拡散の元になっている診断そのものは、こちらから2分〜3分でご体験いただけます：
https://lovecharacter64.jp/quiz`
  },
  {
    target: '美容クリニック・歯科・小児科・動物病院',
    subject: '広告費ゼロで累計8,000万回 — 診断で貴院の予約導線を変えるご提案',
    body: `ご担当者様

はじめてご連絡いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田です。

私たちの診断は、広告費をかけずに累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。

この"数問で自分ごと化する診断"の仕組みを、
クリニック・医院向けの「お悩みタイプ診断」として提供しています。
広告単価の高騰／予約手前での離脱／来院前の不安・疑問に応える接点がない
こうした課題に、診断→結果別の案内→予約→LINEの導線をまるごと設計・制作でお応えします。
医療広告ガイドライン・薬機法に配慮した表現設計で制作いたします。

貴院の診療内容に合わせた診断のラフ案を1つお持ちし、
15分でご説明させていただけないでしょうか。

ぜひ、ご都合のよい候補日をいただけますと幸いです。
よろしくお願いいたします。

P.S. 拡散の元になっている診断そのものは、こちらから2分〜3分でご体験いただけます：
https://lovecharacter64.jp/quiz`
  },
  {
    target: 'スポーツブランド・スポーツチーム',
    subject: 'ABEMA公式番組コラボで13日100万PV — 診断で御チームに新規ファンを',
    body: `ご担当者様

はじめてご連絡いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田です。

私たちがABEMA公式番組と共同開発した診断は、
放送開始からわずか13日で100万PVを突破し、番組への新規流入にもつながりました。
自社の恋愛診断も広告費をかけず累計8,000万回以上利用されています。

この"シェアされて自然に広がる診断"の仕組みを、
スポーツ向けの「観戦タイプ診断」「推し選手診断」「ギアマッチ診断」として提供しています。
ライト層が観戦・購入まで進まない／話題が試合日で終わる／グッズ・ECが既存ファン頼み
こうした課題に、診断→シェア→チケット・EC・ファンクラブ→LINEの導線をまるごと設計・制作でお応えします。

御社・御チームに合わせた診断企画のラフ案を1つお持ちし、
15分でご説明させていただけないでしょうか。

ぜひ、ご都合のよい候補日をいただけますと幸いです。
よろしくお願いいたします。

P.S. 拡散の元になっている診断そのものは、こちらから2分〜3分でご体験いただけます：
https://lovecharacter64.jp/quiz`
  },
  {
    target: '結婚相談所・ブライダル',
    subject: '累計8,000万回の恋愛診断IP — 御社の婚活集客にそのまま使えます',
    body: `ご担当者様

はじめてご連絡いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田です。

私たちの恋愛診断は、広告費をかけずに累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。
診断のテーマは恋愛タイプ・相性——まさに御社の事業と同じ文脈です。

この診断IPと制作ノウハウを、婚活・ブライダル向けに提供しています。
入会・相談前の心理的ハードル／広告獲得単価の高騰／若年層との接点不足
こうした課題に、「恋愛タイプ診断」を気軽な入口として、
診断→結果別ページ→無料相談・来店予約→LINEの導線をまるごと設計・制作でお応えします。

御社のサービスに合わせた活用ラフ案を1つお持ちし、
15分でご説明させていただけないでしょうか。

ぜひ、ご都合のよい候補日をいただけますと幸いです。
よろしくお願いいたします。

P.S. 診断そのものは、こちらから2分〜3分でご体験いただけます：
https://lovecharacter64.jp/quiz`
  },
  {
    target: '住宅・リフォーム・不動産',
    subject: '広告費ゼロで累計8,000万回 — 診断で御社の来場予約を増やすご提案',
    body: `ご担当者様

はじめてご連絡いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田です。

私たちの診断は、広告費をかけずに累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。

この"数問で自分ごと化する診断"の仕組みを、
住宅・不動産向けの「理想の暮らしタイプ診断」に転用しています。
来場・資料請求の獲得単価が高い／検討初期の層と接点が作れない／追客のネタがない
こうした課題に、診断→結果別ページ→来場予約→LINEの導線をまるごと設計・制作でお応えします。
診断結果のタイプ別に追客コンテンツを出し分けることで、長期検討のナーチャリングにも使えます。

御社の商品・物件に合わせた診断のラフ案を1つお持ちし、
15分でご説明させていただけないでしょうか。

ぜひ、ご都合のよい候補日をいただけますと幸いです。
よろしくお願いいたします。

P.S. 拡散の元になっている診断そのものは、こちらから2分〜3分でご体験いただけます：
https://lovecharacter64.jp/quiz`
  },
  {
    target: '通信・金融・生活インフラ',
    subject: '広告費ゼロで累計8,000万回 — 診断で御社サービスとZ世代の接点を作るご提案',
    body: `ご担当者様

はじめてご連絡いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田です。

私たちの診断は、広告費をかけずに累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。
利用者の中心はZ世代です。

この"数問で自分ごと化する診断"の仕組みを、
通信・金融・インフラ向けの「あなたに合うプラン診断」「タイプ別マネー診断」として提供しています。
プランの複雑さによる離脱／比較サイト経由の価格競争／Z世代との接点不足
こうした課題に、診断→結果別の案内→申込・相談→LINEの導線をまるごと設計・制作でお応えします。
業界の広告表現ルールに配慮した設計で制作いたします。

御社のサービスに合わせた診断のラフ案を1つお持ちし、
15分でご説明させていただけないでしょうか。

ぜひ、ご都合のよい候補日をいただけますと幸いです。
よろしくお願いいたします。

P.S. 拡散の元になっている診断そのものは、こちらから2分〜3分でご体験いただけます：
https://lovecharacter64.jp/quiz`
  },
  {
    target: 'メーカー（家電・文具・自動車・バイク）',
    subject: '広告費ゼロで累計8,000万回 — 診断で御社商品の「選ばれ方」を変えるご提案',
    body: `ご担当者様

はじめてご連絡いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田です。

私たちの診断は、広告費をかけずに累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。

この"数問で自分ごと化する診断"の仕組みを、
メーカー向けの「商品マッチ診断」に転用しています。
ラインナップが多くて選べない／スペック比較のまま離脱される／若年層に魅力が届かない
こうした課題に、診断→結果別の商品ページ→EC・店頭送客→LINEの導線をまるごと設計・制作でお応えします。
新商品キャンペーンや店頭施策との連動も可能です。

御社の商品ラインに合わせた診断のラフ案を1つお持ちし、
15分でご説明させていただけないでしょうか。

ぜひ、ご都合のよい候補日をいただけますと幸いです。
よろしくお願いいたします。

P.S. 拡散の元になっている診断そのものは、こちらから2分〜3分でご体験いただけます：
https://lovecharacter64.jp/quiz`
  },
  {
    target: '教育・スクール',
    subject: '広告費ゼロで累計8,000万回 — 診断で御社スクールの体験申込を増やすご提案',
    body: `ご担当者様

はじめてご連絡いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田です。

私たちの診断は、広告費をかけずに累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。
利用者の中心は10代——まさに御社の対象層です。

この"数問で自分ごと化する診断"の仕組みを、
教育・スクール向けの「学び方タイプ診断」に転用しています。
体験申込が伸びない／「合うか分からない」不安での離脱／保護者への訴求が難しい
こうした課題に、診断→結果別ページ→体験・見学申込→LINEの導線をまるごと設計・制作でお応えします。

御社のコースに合わせた診断のラフ案を1つお持ちし、
15分でご説明させていただけないでしょうか。

ぜひ、ご都合のよい候補日をいただけますと幸いです。
よろしくお願いいたします。

P.S. 拡散の元になっている診断そのものは、こちらから2分〜3分でご体験いただけます：
https://lovecharacter64.jp/quiz`
  },
  {
    target: '保育園・幼稚園・こども園',
    subject: '広告費ゼロで累計8,000万回 — 診断で貴園の採用・園児募集を支援するご提案',
    body: `ご担当者様

はじめてご連絡いたします。
恋愛診断IP「ラブキャラ」を運営する株式会社ラブキャラの奥田です。

私たちの診断は、広告費をかけずに累計8,000万回以上利用され、
ABEMA公式番組と共同開発をした診断では放送開始からわずか13日で100万PVを突破しました。
利用者の中心は10代〜20代の女性層——保育士志望者や若い保護者と重なります。

この"数問で自分ごと化する診断"の仕組みを、
保育園向けに「あなたに合う園診断（保育士採用）」「園選びタイプ診断（園児募集）」として提供しています。
求人媒体で応募が集まらない／園の雰囲気が伝わらない／見学の一歩が重い
こうした課題に、診断→結果別の園紹介→見学・応募→LINEの導線をまるごと設計・制作でお応えします。

貴園に合わせた診断のラフ案を1つお持ちし、
15分でご説明させていただけないでしょうか。

ぜひ、ご都合のよい候補日をいただけますと幸いです。
よろしくお願いいたします。

P.S. 拡散の元になっている診断そのものは、こちらから2分〜3分でご体験いただけます：
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
  let eligibleStatusCount = 0;
  let targetCount = 0;

  values.forEach(row => {
    const approach = normalizeText(row[COL_APPROACH - 1]);
    const status = normalizeText(row[COL_STATUS - 1]);

    if (approach === APPROACH_EMAIL_CANDIDATE) {
      mailCandidateCount++;
    }

    if (isEligibleDraftStatus(status)) {
      eligibleStatusCount++;
    }

    if (approach === APPROACH_EMAIL_CANDIDATE && isEligibleDraftStatus(status)) {
      targetCount++;
    }
  });

  Logger.log(`${sheet.getName()}: メール候補 ${mailCandidateCount}件 / 対象ステータス（未対応・エラー・空欄） ${eligibleStatusCount}件 / 今回対象 ${targetCount}件 / 上限 ${DAILY_DRAFT_LIMIT}件`);
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

/**
 * 下書き作成対象となるステータスか判定する。
 * L列が「メール候補」であることは呼び出し元で別途判定しているため、
 * ここでは空欄・未対応・エラーを対象とする。
 */
function isEligibleDraftStatus(status) {
  return (
    !status ||
    status === STATUS_UNTOUCHED ||
    status === STATUS_ERROR
  );
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
