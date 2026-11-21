#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { loadRegistry, REPO_ROOT } from "./lib/registry.mjs";

const DEFAULT_ASSET_ID = "Risk_Hierarchical_Classification_Benchmark_v6";
const DEFAULT_NAME = "课题三 v6 风险内容分级分类动态评测集";
const DEFAULT_WINDOWS_ROOT =
  "C:\\Users\\admin\\Desktop\\项目资料\\demo 调研\\课题三\\v6数据-baseline与目前算法评测结果\\v6数据-baseline与目前算法评测结果";

const BASELINE_DIR =
  "topic3_risk_evaluation_result_qwen3_5_9b_base_joint_level_multilabel_Risk_Hierarchical_Classification_Benchmark_v6";
const V7_DIR =
  "topic3_risk_evaluation_result_qwen3_5_9b_V7_base_joint_level_multilabel_Risk_Hierarchical_Classification_Benchmark_v6";
const BASELINE_RUN_ID =
  "qwen3_5_9b_base_joint_level_multilabel_Risk_Hierarchical_Classification_Benchmark_v6";
const V7_RUN_ID =
  "qwen3_5_9b_V7_base_joint_level_multilabel_Risk_Hierarchical_Classification_Benchmark_v6";

function parseArgs(argv) {
  const options = {
    assetId: DEFAULT_ASSET_ID,
    name: DEFAULT_NAME,
    root: DEFAULT_WINDOWS_ROOT,
    backendUrl: "",
    pathStyle: "wsl",
    dryRun: false,
    skipAsset: false,
    skipResults: false,
    help: false,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const next = () => {
      index += 1;
      if (index >= argv.length) {
        throw new Error(`${arg} requires a value`);
      }
      return argv[index];
    };
    switch (arg) {
      case "--asset-id":
        options.assetId = next();
        break;
      case "--name":
        options.name = next();
        break;
      case "--root":
        options.root = next();
        break;
      case "--backend-url":
        options.backendUrl = next().replace(/\/$/, "");
        break;
      case "--path-style":
        options.pathStyle = next();
        break;
      case "--dry-run":
        options.dryRun = true;
        break;
      case "--skip-asset":
        options.skipAsset = true;
        break;
      case "--skip-results":
        options.skipResults = true;
        break;
      case "--help":
      case "-h":
        options.help = true;
        break;
      default:
        throw new Error(`Unknown option: ${arg}`);
    }
  }
  if (!["windows", "wsl", "native"].includes(options.pathStyle)) {
    throw new Error("--path-style must be windows, wsl, or native");
  }
  return options;
}

function printHelp() {
  console.log(`Import Topic3 v6 risk benchmark asset and imported_result packages.

Usage:
  node scripts/import-topic3-risk-v6.mjs [options]

Options:
  --root <dir>          Directory containing v6 CSV and result package dirs.
  --asset-id <id>      Asset id. Default: ${DEFAULT_ASSET_ID}
  --name <name>        Display name. Default: ${DEFAULT_NAME}
  --backend-url <url>  Override backend URL. Default comes from ports.registry.yaml
  --path-style <s>     windows | wsl | native. Default: wsl
  --skip-asset         Do not call asset import; useful when asset already exists
  --skip-results       Do not import evaluation result packages
  --dry-run            Print endpoints and payloads without importing
  -h, --help           Show this help

Examples:
  node scripts/import-topic3-risk-v6.mjs --dry-run
  node scripts/import-topic3-risk-v6.mjs --path-style windows
  node scripts/import-topic3-risk-v6.mjs --path-style wsl --root "/mnt/c/Users/admin/Desktop/项目资料/demo 调研/课题三/v6数据-baseline与目前算法评测结果/v6数据-baseline与目前算法评测结果"
`);
}

function toWindowsPath(value) {
  const normalized = value.replaceAll("\\", "/");
  const match = normalized.match(/^\/mnt\/([a-zA-Z])\/(.*)$/);
  if (match) {
    return `${match[1].toUpperCase()}:\\${match[2].replaceAll("/", "\\")}`;
  }
  return value;
}

function toWslPath(value) {
  const normalized = value.replaceAll("\\", "/");
  const match = normalized.match(/^([a-zA-Z]):\/(.*)$/);
  if (match) {
    return `/mnt/${match[1].toLowerCase()}/${match[2]}`;
  }
  return normalized;
}

function payloadPath(nativePath, pathStyle) {
  const absolute = path.resolve(nativePath);
  if (pathStyle === "windows") {
    return toWindowsPath(absolute);
  }
  if (pathStyle === "wsl") {
    return toWslPath(absolute);
  }
  return absolute;
}

function nativeRoot(value) {
  if (process.platform === "win32") {
    return value;
  }
  return toWslPath(value);
}

function sourcePaths(options) {
  const root = nativeRoot(options.root);
  return {
    csv_path: path.join(
      root,
      "Risk_Hierarchical_Classification_Benchmark_v6.csv",
    ),
    baseline_result_dir: path.join(root, BASELINE_DIR),
    v7_result_dir: path.join(root, V7_DIR),
  };
}

function validateNativeSources(paths, options) {
  const missing = [];
  if (!options.skipAsset && !fs.existsSync(paths.csv_path)) {
    missing.push(`csv_path: ${paths.csv_path}`);
  }
  if (!options.skipResults) {
    for (const key of ["baseline_result_dir", "v7_result_dir"]) {
      if (!fs.existsSync(paths[key])) {
        missing.push(`${key}: ${paths[key]}`);
      }
    }
  }
  if (missing.length > 0) {
    throw new Error(
      `Missing source files or directories:\n${missing.join("\n")}`,
    );
  }
}

function buildPayloads(options) {
  const nativePaths = sourcePaths(options);
  validateNativeSources(nativePaths, options);
  return {
    nativePaths,
    assetPayload: {
      csv_path: payloadPath(nativePaths.csv_path, options.pathStyle),
      asset_id: options.assetId,
      name: options.name,
    },
    resultPayloads: [
      {
        label: "baseline",
        runId: BASELINE_RUN_ID,
        body: {
          result_dir: payloadPath(
            nativePaths.baseline_result_dir,
            options.pathStyle,
          ),
        },
      },
      {
        label: "v7",
        runId: V7_RUN_ID,
        body: {
          result_dir: payloadPath(nativePaths.v7_result_dir, options.pathStyle),
        },
      },
    ],
  };
}

function backendUrl(options) {
  if (options.backendUrl) {
    return options.backendUrl;
  }
  const registry = loadRegistry();
  return `http://${registry.host}:${registry.platform.backend_port}`;
}

async function readJsonResponse(response) {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return { raw: text };
  }
}

async function requestJson(url, init) {
  const response = await fetch(url, init);
  const body = await readJsonResponse(response);
  if (!response.ok) {
    const message =
      body?.detail || body?.msg || body?.raw || response.statusText;
    const error = new Error(`${response.status} ${message}`);
    error.status = response.status;
    error.body = body;
    throw error;
  }
  return body;
}

async function getAsset(baseUrl, assetId) {
  try {
    const body = await requestJson(
      `${baseUrl}/api/benchmark/assets/${encodeURIComponent(assetId)}`,
    );
    return body?.data ?? null;
  } catch (error) {
    if (error.status === 404) {
      return null;
    }
    throw error;
  }
}

async function importAsset(baseUrl, payload) {
  const body = await requestJson(
    `${baseUrl}/api/benchmark/assets/topic3-risk/v6/import`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  return body?.data?.asset;
}

async function importResult(baseUrl, assetId, payload) {
  const body = await requestJson(
    `${baseUrl}/api/benchmark/assets/${encodeURIComponent(
      assetId,
    )}/topic3-risk/evaluations/import`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  return body?.data?.summary;
}

async function getSummary(baseUrl, assetId) {
  const body = await requestJson(
    `${baseUrl}/api/benchmark/assets/${encodeURIComponent(
      assetId,
    )}/topic3-risk/evaluations/summary`,
  );
  return body?.data ?? null;
}

function summaryView(summary) {
  return {
    available: summary?.available,
    status: summary?.status,
    eval_mode: summary?.eval_mode,
    result_source: summary?.result_source,
    models: (summary?.results ?? []).map((item) => ({
      model_id: item.model_id,
      role: item.role,
      display_name: item.display_name,
      primary_metrics: item.primary_metrics,
    })),
  };
}

function isAlreadyExistsError(error) {
  return (
    error.status === 422 && String(error.message).includes("already exists")
  );
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    printHelp();
    return;
  }

  const baseUrl = backendUrl(options);
  const { nativePaths, assetPayload, resultPayloads } = buildPayloads(options);
  const assetUrl = `${baseUrl}/api/benchmark/assets/topic3-risk/v6/import`;
  const resultUrl = `${baseUrl}/api/benchmark/assets/${options.assetId}/topic3-risk/evaluations/import`;

  console.log(`Project root: ${REPO_ROOT}`);
  console.log(`Backend URL:  ${baseUrl}`);
  console.log(`Path style:   ${options.pathStyle}`);
  console.log(`Asset ID:     ${options.assetId}`);

  if (options.dryRun) {
    console.log("\nNative source paths:");
    for (const [key, value] of Object.entries(nativePaths)) {
      console.log(`- ${key}: ${value}`);
    }
    if (!options.skipAsset) {
      console.log("\nPOST", assetUrl);
      console.log(JSON.stringify(assetPayload, null, 2));
    }
    if (!options.skipResults) {
      for (const payload of resultPayloads) {
        console.log(`\nPOST ${resultUrl} (${payload.label})`);
        console.log(JSON.stringify(payload.body, null, 2));
      }
    }
    return;
  }

  if (!options.skipAsset) {
    const existing = await getAsset(baseUrl, options.assetId);
    if (existing) {
      console.log("\nAsset already exists; skipping asset import.");
    } else {
      const imported = await importAsset(baseUrl, assetPayload);
      console.log("\nImported Topic3 v6 asset:");
      console.log(
        JSON.stringify(
          {
            asset_id: imported?.asset_id,
            source_mode: imported?.source_mode,
            sample_count: imported?.manifest?.sample_count,
            risk_total: imported?.manifest?.risk_total,
            safe_total: imported?.manifest?.safe_total,
          },
          null,
          2,
        ),
      );
    }
  }

  if (!options.skipResults) {
    const existingSummary = await getSummary(baseUrl, options.assetId);
    const existingRunIds = new Set(
      (existingSummary?.results ?? []).map((item) => item.run_id),
    );

    for (const payload of resultPayloads) {
      if (existingRunIds.has(payload.runId)) {
        console.log(
          `\n${payload.label} evaluation result already exists; skipping.`,
        );
        continue;
      }
      try {
        const summary = await importResult(
          baseUrl,
          options.assetId,
          payload.body,
        );
        console.log(`\nImported ${payload.label} evaluation result.`);
        console.log(JSON.stringify(summaryView(summary), null, 2));
      } catch (error) {
        if (isAlreadyExistsError(error)) {
          console.log(
            `\n${payload.label} evaluation result already exists; skipping.`,
          );
          continue;
        }
        throw error;
      }
    }
  }

  const summary = await getSummary(baseUrl, options.assetId);
  console.log("\nTopic3 v6 evaluation summary:");
  console.log(JSON.stringify(summaryView(summary), null, 2));
}

main().catch((error) => {
  console.error(error.message);
  if (error.body) {
    console.error(JSON.stringify(error.body, null, 2));
  }
  process.exitCode = 1;
});
