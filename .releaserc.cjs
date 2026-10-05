// Release pipeline = the shared local-first base (~/.claude/tools/semrel/release.base.cjs: version from
// conventional commits, body-preserving notes, narrative from docs/release-notes/v<next>.md), plus this
// repo's Python steps: bump pyproject.toml/__version__.py, uv build, uv publish to PyPI.
// Run: npm run release (local only). Write docs/release-notes/v<next>.md first.
const { join } = require("node:path");
const { homedir } = require("node:os");

const base = require(join(homedir(), ".claude/tools/semrel/release.base.cjs"));
const VERSION_FILES = ["pyproject.toml", "src/binance_futures_availability/__version__.py"];

const python = [
  "@semantic-release/exec",
  {
    // biome-ignore lint/suspicious/noTemplateCurlyInString: semantic-release lodash template
    prepareCmd: [
      "sed -i.bak 's/^version = \".*\"/version = \"${nextRelease.version}\"/' pyproject.toml && rm pyproject.toml.bak",
      "echo '__version__ = \"${nextRelease.version}\"' > src/binance_futures_availability/__version__.py",
      "uv lock",
      "rm -rf dist && uv build",
    ].join(" && "),
    publishCmd:
      "UV_PUBLISH_TOKEN=$(doppler secrets get PYPI_TOKEN --project claude-config --config prd --plain) uv publish",
  },
];

// The daily workflow commits `chore(symbols): auto-update from S3 discovery` (~300 per release);
// hide them from the notes. A `types` entry with a scope must precede the generic `chore` entry.
const hideBotCommits = ([name, options]) => [
  name,
  {
    ...options,
    presetConfig: {
      ...options.presetConfig,
      types: [{ type: "chore", scope: "symbols", hidden: true }, ...options.presetConfig.types],
    },
  },
];

const plugins = base.plugins.flatMap((plugin) => {
  const name = Array.isArray(plugin) ? plugin[0] : plugin;
  if (name === "@semantic-release/release-notes-generator") return [hideBotCommits(plugin)];
  if (name !== "@semantic-release/git") return [plugin];
  const [, options] = plugin;
  return [python, [name, { ...options, assets: [...options.assets, ...VERSION_FILES, "uv.lock"] }]];
});

module.exports = { ...base, plugins };
