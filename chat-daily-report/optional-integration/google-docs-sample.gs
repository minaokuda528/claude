/**
 * google-docs-sample.gs — 業務日報を Google ドキュメントとして保存する GAS サンプル
 *
 * 【重要な前提】
 * - これは「参考用のサンプル」です。必要な企業が自社で導入・調整してください。
 * - Claude から直接このスクリプトを実行する設計ではありません。
 *   人が日報の内容を確認したうえで、手動またはフォームなどから呼び出す運用を推奨します。
 * - APIキーや認証情報をこのコードに直接書かないでください。
 *   Google の認証は GAS の実行ユーザー権限で行われます。
 * - 本番利用の前に、必ずテスト用フォルダで動作を確認してください。
 *
 * 【設定】下の CONFIG だけを自社に合わせて変更してください。
 */

// ===== 設定欄(ここだけ編集してください) =====
var CONFIG = {
  // 保存先の Google ドライブ フォルダ ID(フォルダURLの /folders/ の後ろの文字列)
  // 例: https://drive.google.com/drive/folders/XXXXXXXX → "XXXXXXXX"
  FOLDER_ID: 'ここに保存先フォルダのIDを入力',

  // ファイル名の先頭に付ける接頭辞
  FILE_NAME_PREFIX: '業務日報',

  // ログを記録するかどうか(true / false)
  ENABLE_LOG: true
};
// ===========================================

/**
 * 業務日報を Google ドキュメントとして保存するメイン関数。
 *
 * @param {string} reportText 日報の本文(Markdownまたはプレーンテキスト)
 * @param {string} authorName 担当者名(ファイル名に使用)
 * @param {string} reportDate 日付文字列 "YYYY-MM-DD"(省略時は実行日)
 * @return {string} 作成した Google ドキュメントの URL
 */
function saveDailyReport(reportText, authorName, reportDate) {
  try {
    // --- 入力チェック ---
    if (!reportText || reportText.trim() === '') {
      throw new Error('日報本文(reportText)が空です。');
    }
    if (CONFIG.FOLDER_ID === 'ここに保存先フォルダのIDを入力') {
      throw new Error('CONFIG.FOLDER_ID が未設定です。設定欄を編集してください。');
    }

    // --- 日付・ファイル名の準備 ---
    var dateStr = reportDate && reportDate.trim() !== ''
      ? reportDate
      : Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd');
    var author = authorName && authorName.trim() !== '' ? authorName : '担当者不明';
    var fileName = dateStr + '_' + CONFIG.FILE_NAME_PREFIX + '_' + author;

    // --- 保存先フォルダの取得 ---
    var folder = DriveApp.getFolderById(CONFIG.FOLDER_ID);

    // --- ドキュメント作成 ---
    var doc = DocumentApp.create(fileName);
    doc.getBody().setText(reportText);
    doc.saveAndClose();

    // --- 指定フォルダへ移動 ---
    var file = DriveApp.getFileById(doc.getId());
    folder.addFile(file);
    DriveApp.getRootFolder().removeFile(file); // マイドライブ直下から除去

    var url = doc.getUrl();
    writeLog('成功: ' + fileName + ' / ' + url);
    return url;

  } catch (e) {
    writeLog('エラー: ' + e.message);
    throw e; // 呼び出し元へエラーを伝える
  }
}

/**
 * ログを記録する(CONFIG.ENABLE_LOG が true の場合のみ)。
 * GAS の実行ログ(Logger)へ出力します。必要に応じてスプレッドシート等へ変更してください。
 */
function writeLog(message) {
  if (!CONFIG.ENABLE_LOG) return;
  var timestamp = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss');
  Logger.log('[' + timestamp + '] ' + message);
}

/**
 * 動作確認用のテスト関数。
 * GAS エディタでこの関数を実行し、テスト用フォルダに日報が作成されるか確認してください。
 */
function testSaveDailyReport() {
  var sampleText = '業務日報\n\n基本情報\n- 日付:2026-07-13\n- 担当者:テスト太郎\n\n本日の主な業務\n1. 動作テスト';
  var url = saveDailyReport(sampleText, 'テスト太郎', '2026-07-13');
  Logger.log('作成したドキュメント: ' + url);
}
