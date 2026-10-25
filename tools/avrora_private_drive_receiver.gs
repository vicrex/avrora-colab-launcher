/**
 * AVRORA: free Google Apps Script receiver for private historical research.
 *
 * Deploy as WEB APP -> Execute as Me -> Access: Anyone (including anonymous).
 * Security is a 256-bit HMAC shared secret, not a publicly writable folder.
 * This script runs with the OWNER's DriveApp permission; NEVER use without HMAC.
 * There are NO clocks, no Bybit credentials, no trading and no holdout access.
 * Install separately from the current avroraHourlyTick dispatch script; do not
 * replace that script or install another scheduled trigger.
 */
var AVRORA_FOLDER_ID = "1MXTBe21rTm1fVYzjUQ6NNf8cJzOQ0NKX";
var AVRORA_KEY_PROPERTY = "AVRORA_GAS_REPORT_HMAC_KEY";

function avroraHex_(bytes) {
  return bytes.map(function(x) {
    return ("0" + ((x & 255).toString(16))).slice(-2);
  }).join("");
}
function avroraSafeEqual_(a, b) {
  if (typeof a !== "string" || typeof b !== "string") return false;
  var diff = a.length ^ b.length;
  var m = Math.max(a.length, b.length);
  for (var k = 0; k < m; k++) {
    diff |= ((a.charCodeAt(k) || 0) ^ (b.charCodeAt(k) || 0));
  }
  return diff === 0;
}
function avroraReply_(payload) {
  return ContentService.createTextOutput(JSON.stringify(payload))
      .setMimeType(ContentService.MimeType.JSON);
}
// Run MANUALLY exactly once in your own Apps Script editor. The key appears
// in the editor execution log, not in any public URL or GitHub source.
// Copy it ONLY to the encrypted GitHub Actions secret
// AVRORA_GAS_REPORT_HMAC_KEY. Do not paste in ChatGPT or a public issue.
function avroraCreateSharedSecretOnce() {
  var props = PropertiesService.getScriptProperties();
  if (props.getProperty(AVRORA_KEY_PROPERTY)) {
    throw new Error("SHARED_KEY_ALREADY_EXISTS_NO_OVERWRITE");
  }
  var secret = (Utilities.getUuid() + Utilities.getUuid()).replace(/-/g, "");
  if (!/^[0-9a-f]{64}$/.test(secret)) {
    throw new Error("UNSAFE_KEY_FORMAT");
  }
  props.setProperty(AVRORA_KEY_PROPERTY, secret);
  console.log("COPY_TO_GITHUB_SECRET_AVRORA_GAS_REPORT_HMAC_KEY=" + secret);
}
function doGet() {
  return avroraReply_({status: "AVRORA_GAS_PRIVATE_RECEIVER_READY_NO_GET_DATA"});
}
function doPost(e) {
  var lock = null;
  try {
    if (!e || !e.postData || typeof e.postData.contents !== "string"
        || e.postData.contents.length > 5600000) {
      throw new Error("BLOCKED_REQUEST_SIZE");
    }
    var env = JSON.parse(e.postData.contents);
    if (env.schema !== "AVRORA_PRIVATE_GAS_DELIVERY_V1"
        || !/^[0-9]{1,24}$/.test(env.run_id)
        || !/^[a-f0-9]{64}$/.test(env.sha256)
        || !/^[a-f0-9]{64}$/.test(env.signature)
        || typeof env.body_base64 !== "string"
        || env.body_base64.length > 5400000
        || !/^[A-Za-z0-9+/]*={0,2}$/.test(env.body_base64)) {
      throw new Error("BLOCKED_INVALID_ENVELOPE");
    }
    var secret = PropertiesService.getScriptProperties().getProperty(AVRORA_KEY_PROPERTY);
    if (!secret || !/^[a-f0-9]{64}$/.test(secret)) {
      throw new Error("BLOCKED_HMAC_NOT_CONFIGURED");
    }
    var msg = env.run_id + "\n" + env.sha256 + "\n" + env.body_base64;
    var expected = avroraHex_(Utilities.computeHmacSha256Signature(msg, secret));
    if (!avroraSafeEqual_(expected, env.signature)) {
      throw new Error("BLOCKED_INVALID_HMAC");
    }
    var bytes = Utilities.base64Decode(env.body_base64);
    if (bytes.length > 4000000 || bytes.length === 0
        || avroraHex_(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, bytes))
           !== env.sha256) {
      throw new Error("BLOCKED_BYTES_DIGEST");
    }
    var report = JSON.parse(Utilities.newBlob(bytes).getDataAsString("UTF-8"));
    if (report.schema !== "AVRORA_MULTIFAMILY_SHADOW_SWEEP_V1"
        || report.real !== "OFF" || report.holdout !== "SEALED"
        || report.oos_proven !== false || report.fill_proven !== false
        || report.count !== 64 || !Array.isArray(report.models)
        || report.models.length !== 64 || !Array.isArray(report.candidate_ids)
        || report.candidate_ids.length !== 64) {
      throw new Error("BLOCKED_UNSAFE_REPORT");
    }
    lock = LockService.getScriptLock();
    if (!lock.tryLock(20000)) throw new Error("BLOCKED_CONCURRENT_WRITE");
    var folder = DriveApp.getFolderById(AVRORA_FOLDER_ID);
    var name = "AVRORA_PRIVATE_MULTIFAMILY_" + env.run_id + ".json";
    var iterator = folder.getFilesByName(name);
    var entry;
    if (iterator.hasNext()) {
      entry = iterator.next();
      if (iterator.hasNext()) throw new Error("BLOCKED_DUPLICATE_REPORT");
    } else {
      entry = folder.createFile(Utilities.newBlob(bytes, "application/json", name));
    }
    var back = entry.getBlob().getBytes();
    var backSha = avroraHex_(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, back));
    if (back.length !== bytes.length || backSha !== env.sha256) {
      throw new Error("BLOCKED_DRIVE_READBACK_MISMATCH");
    }
    return avroraReply_({status: "PASS_PRIVATE_DRIVE_READBACK",
                         run_id: env.run_id, sha256: backSha, bytes: back.length});
  } catch (err) {
    // Deliberately never log input payloads, key, Drive ID or failure stack.
    // A non-PASS status means GitHub must fail the job closed.
    return avroraReply_({status: "BLOCKED_PRIVATE_DRIVE_DELIVERY"});
  } finally {
    if (lock) {
      try { lock.releaseLock(); } catch (_) {}
    }
  }
}
