const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

async function run(platform, sourceRoot) {
  const source = fs.readFileSync(path.join(sourceRoot, platform === "tv"
    ? "app/src/full/java/com/nuvio/tv/core/plugin/PluginRuntime.kt"
    : "composeApp/src/fullCommonMain/kotlin/com/nuvio/app/features/plugins/runtime/js/JsBindings.kt"), "utf8");
  const marker = platform === "tv" ? "private fun getStaticCallCode()" : "val staticCallCode:";
  const body = source.slice(source.indexOf(marker)).split('"""')[1];
  assert.ok(body.includes("resolveTorrent"));
  async function execute(args, exports) {
    let captured;
    const sandbox = {module: {exports}, __get_call_args: () => JSON.stringify(args),
      __capture_result: (value) => { captured = JSON.parse(value); }, console: {log() {}, error() {}}};
    await vm.runInNewContext(body, sandbox);
    return captured;
  }
  let searches = 0;
  let resolutions = 0;
  const provider = {
    getStreams: async () => { searches++; return [{title: "Example", torrent: {resolveId: "42"}}]; },
    resolveTorrent: async (id) => { resolutions++; assert.equal(id, "42"); return {dataBase64: "ZGU=", fileIdx: 2}; }
  };
  const listed = await execute({tmdbId: "123", mediaType: "movie"}, provider);
  assert.equal(listed[0].torrent.resolveId, "42");
  assert.equal(resolutions, 0);
  const resolved = await execute({torrentResolveId: "42"}, provider);
  assert.equal(resolved.fileIdx, 2);
  assert.equal(resolved.dataBase64, "ZGU=");
  assert.equal(searches, 1);
  assert.equal(resolutions, 1);
  const failure = await execute({torrentResolveId: "42"}, {
    resolveTorrent: async () => { throw new Error("https://tracker.invalid/secret-passkey"); }
  });
  assert.equal(failure.error, "TORRENT_RESOLUTION_FAILED");
  assert.ok(!JSON.stringify(failure).includes("secret"));
  const missing = await execute({torrentResolveId: "42"}, {});
  assert.equal(missing.error, "TORRENT_RESOLUTION_FAILED");
  return {platform, passed: 4};
}

module.exports = {run};
if (require.main === module) run(process.argv[2], process.argv[3]).then(console.log).catch((error) => {
  console.error(error); process.exitCode = 1;
});
