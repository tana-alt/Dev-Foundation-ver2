#!/usr/bin/env node

const fs = require("node:fs");
const path = require("node:path");
const { createRequire } = require("node:module");

const repoRoot = path.resolve(__dirname, "../../../..");

function parseArgs(argv) {
  const args = {
    url: null,
    outDir: null,
    timeoutMs: 30000,
    help: false,
  };

  for (let i = 2; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--help" || arg === "-h") {
      args.help = true;
    } else if (arg === "--out-dir") {
      args.outDir = argv[++i];
    } else if (arg === "--timeout-ms") {
      args.timeoutMs = Number(argv[++i]);
    } else if (!args.url) {
      args.url = arg;
    } else {
      throw new Error(`Unexpected argument: ${arg}`);
    }
  }

  if (!Number.isFinite(args.timeoutMs) || args.timeoutMs <= 0) {
    throw new Error("--timeout-ms must be a positive number");
  }

  return args;
}

function usage() {
  return [
    "Usage:",
    "  node .codex/skills/3dtask-quality-gate/scripts/run-3dtask-quality-gate.cjs <url> [--out-dir <dir>] [--timeout-ms <ms>]",
  ].join("\n");
}

function loadPlaywright() {
  const attempted = [];
  const localPackage = path.join(repoRoot, "apps/web/package.json");

  try {
    attempted.push(path.join(repoRoot, "apps/web/node_modules/playwright"));
    return createRequire(localPackage)("playwright");
  } catch (error) {
    attempted.push("playwright");
    try {
      return require("playwright");
    } catch (fallbackError) {
      const err = new Error(
        `Playwright is unavailable. Tried: ${attempted.join(", ")}. ` +
          "Install or expose repo-local Playwright before running this gate."
      );
      err.cause = fallbackError;
      throw err;
    }
  }
}

function makeRunId() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function normalizeOutDir(outDir) {
  if (outDir) return path.resolve(process.cwd(), outDir);
  return path.join(
    repoRoot,
    "projects/project_app_3dtask/artifacts/quality/screenshots",
    makeRunId()
  );
}

async function collectButtonSignals(page, viewportName) {
  return page.evaluate((name) => {
    const viewport = { width: window.innerWidth, height: window.innerHeight };
    const seen = new Set();
    const selector =
      'button, [role="button"], a[href], input[type="button"], input[type="submit"], input[type="reset"], [tabindex]';
    const candidates = Array.from(document.querySelectorAll(selector)).filter((el) => {
      if (seen.has(el)) return false;
      seen.add(el);
      const style = getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      const label = [
        el.getAttribute("aria-label"),
        el.getAttribute("title"),
        el.textContent,
        el.id,
        el.className,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      const buttonish =
        el.tagName === "BUTTON" ||
        el.getAttribute("role") === "button" ||
        el.tagName === "A" ||
        label.includes("button") ||
        label.includes("btn");

      return (
        buttonish &&
        style.display !== "none" &&
        style.visibility !== "hidden" &&
        Number(style.opacity) !== 0 &&
        rect.width > 0 &&
        rect.height > 0 &&
        rect.bottom >= 0 &&
        rect.right >= 0 &&
        rect.top <= viewport.height &&
        rect.left <= viewport.width
      );
    });

    const buttons = candidates.map((el, index) => {
      const rect = el.getBoundingClientRect();
      return {
        index,
        tag: el.tagName.toLowerCase(),
        role: el.getAttribute("role") || null,
        text: (el.textContent || el.getAttribute("aria-label") || "").trim().slice(0, 80),
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      };
    });

    const warnings = [];
    for (const button of buttons) {
      const clipped =
        button.x < -2 ||
        button.y < -2 ||
        button.x + button.width > viewport.width + 2 ||
        button.y + button.height > viewport.height + 2;
      if (clipped) {
        warnings.push({
          type: "button-clipped",
          viewport: name,
          button,
          message: "Visible control extends outside viewport bounds.",
        });
      }

      if (name === "mobile" && (button.width < 44 || button.height < 44)) {
        warnings.push({
          type: "small-mobile-target",
          viewport: name,
          button,
          message: "Mobile control is below the 44px tap target heuristic.",
        });
      }
    }

    for (let i = 0; i < buttons.length; i += 1) {
      for (let j = i + 1; j < buttons.length; j += 1) {
        const a = buttons[i];
        const b = buttons[j];
        const x = Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x));
        const y = Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));
        const area = x * y;
        const smallerArea = Math.max(1, Math.min(a.width * a.height, b.width * b.height));
        if (area > 64 && area / smallerArea > 0.18) {
          warnings.push({
            type: "button-overlap",
            viewport: name,
            a,
            b,
            overlapAreaPx: Math.round(area),
            overlapRatioOfSmaller: Number((area / smallerArea).toFixed(3)),
            message: "Two visible controls overlap enough to risk mis-clicks.",
          });
        }
      }
    }

    return { count: buttons.length, buttons, warnings };
  }, viewportName);
}

async function collectCanvasSignals(page) {
  return page.evaluate(() => {
    function sample2d(canvas, width, height) {
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      if (!ctx) return null;
      const data = ctx.getImageData(0, 0, width, height).data;
      return summarizePixels(data);
    }

    function sampleWebgl(canvas, width, height) {
      const gl =
        canvas.getContext("webgl2", { preserveDrawingBuffer: true }) ||
        canvas.getContext("webgl", { preserveDrawingBuffer: true }) ||
        canvas.getContext("experimental-webgl", { preserveDrawingBuffer: true });
      if (!gl) return null;
      const bufferWidth = Math.max(1, gl.drawingBufferWidth || width);
      const bufferHeight = Math.max(1, gl.drawingBufferHeight || height);
      const sampleWidth = Math.min(128, bufferWidth);
      const sampleHeight = Math.min(128, bufferHeight);
      const sampleX = Math.max(0, Math.floor((bufferWidth - sampleWidth) / 2));
      const sampleY = Math.max(0, Math.floor((bufferHeight - sampleHeight) / 2));
      const pixels = new Uint8Array(sampleWidth * sampleHeight * 4);
      gl.readPixels(sampleX, sampleY, sampleWidth, sampleHeight, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
      return summarizePixels(pixels);
    }

    function summarizePixels(data) {
      let nonTransparent = 0;
      let colorSum = 0;
      let unique = new Set();
      const step = Math.max(4, Math.floor(data.length / 4096 / 4) * 4);
      for (let i = 0; i < data.length; i += step) {
        const r = data[i] || 0;
        const g = data[i + 1] || 0;
        const b = data[i + 2] || 0;
        const a = data[i + 3] || 0;
        if (a > 8) nonTransparent += 1;
        colorSum += r + g + b;
        unique.add(`${r >> 4},${g >> 4},${b >> 4},${a >> 4}`);
        if (unique.size > 12 && nonTransparent > 20) break;
      }
      const samples = Math.ceil(data.length / step);
      return {
        samples,
        nonTransparent,
        averageRgb: Number((colorSum / Math.max(1, samples) / 3).toFixed(2)),
        coarseColorBuckets: unique.size,
        nonblankish: nonTransparent > 20 && unique.size > 1,
      };
    }

    return Array.from(document.querySelectorAll("canvas")).map((canvas, index) => {
      const rect = canvas.getBoundingClientRect();
      const visible =
        rect.width > 0 &&
        rect.height > 0 &&
        rect.bottom >= 0 &&
        rect.right >= 0 &&
        rect.top <= window.innerHeight &&
        rect.left <= window.innerWidth;
      const width = Math.max(1, Math.floor(canvas.width || rect.width));
      const height = Math.max(1, Math.floor(canvas.height || rect.height));
      let sample = null;
      let method = "unavailable";
      let error = null;

      try {
        sample = sampleWebgl(canvas, width, height);
        if (sample) method = "webgl-readPixels";
      } catch (err) {
        error = err.message;
      }

      if (!sample) {
        try {
          sample = sample2d(canvas, width, height);
          if (sample) method = "2d-getImageData";
        } catch (err) {
          error = err.message;
        }
      }

      return {
        index,
        visible,
        rect: {
          x: Math.round(rect.x),
          y: Math.round(rect.y),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
        },
        backingSize: { width, height },
        method,
        sample,
        nonblankish: Boolean(sample && sample.nonblankish),
        error,
      };
    });
  });
}

async function collectAxisSignals(page) {
  return page.evaluate(() => {
    const textSources = [];
    const elements = Array.from(document.querySelectorAll("body *"));
    const axisRegex =
      /(\b\d{1,2}:\d{2}\b|\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b|\b\d{1,2}\/\d{1,2}\b|\b(mon|tue|wed|thu|fri|sat|sun)\b|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b|timeline|axis|date|time|week|month|year|日|月|年|時|分|週|タイムライン|期限)/i;

    for (const el of elements) {
      const rect = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      if (
        rect.width <= 0 ||
        rect.height <= 0 ||
        style.display === "none" ||
        style.visibility === "hidden"
      ) {
        continue;
      }
      const text = [
        el.textContent,
        el.getAttribute("aria-label"),
        el.getAttribute("title"),
        el.getAttribute("data-testid"),
      ]
        .filter(Boolean)
        .join(" ")
        .trim();
      if (text && axisRegex.test(text)) {
        textSources.push(text.replace(/\s+/g, " ").slice(0, 120));
      }
      if (textSources.length >= 12) break;
    }

    const unique = Array.from(new Set(textSources));
    return {
      present: unique.length > 0,
      readableCandidateCount: unique.length,
      readableCandidates: unique,
      heuristic: "DOM text, aria-label, title, and data-testid date/time/timeline matching.",
    };
  });
}

async function visibleDialogCount(page) {
  return page.evaluate(() => {
    return Array.from(document.querySelectorAll('dialog, [role="dialog"], [aria-modal="true"]')).filter((el) => {
      const rect = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      return (
        rect.width > 8 &&
        rect.height > 8 &&
        rect.bottom >= 0 &&
        rect.right >= 0 &&
        rect.top <= window.innerHeight &&
        rect.left <= window.innerWidth &&
        style.display !== "none" &&
        style.visibility !== "hidden"
      );
    }).length;
  });
}

async function collectNodeReturnSignals(page) {
  const selector =
    '[data-testid*="node" i], [data-testid*="task" i], [aria-label*="node" i], [aria-label*="task" i], [class*="node" i], [class*="task" i]';
  const candidateCount = await page.locator(selector).count().catch(() => 0);

  if (candidateCount === 0) {
    return {
      attempted: false,
      candidateCount,
      status: "skipped-no-obvious-node-selector",
      note:
        "No obvious node-like selectors were found. Add app-specific selectors when stable test IDs exist.",
    };
  }

  const beforeUrl = page.url();
  const beforeDialogs = await visibleDialogCount(page).catch(() => null);
  const first = page.locator(selector).first();
  const result = {
    attempted: true,
    candidateCount,
    beforeUrl,
    afterClickUrl: null,
    afterReturnUrl: null,
    beforeDialogs,
    afterClickDialogs: null,
    afterEscapeDialogs: null,
    returnedToStartingUrl: null,
    dismissedDialog: null,
    status: "unknown",
    errors: [],
  };

  try {
    await first.click({ timeout: 2500 });
    await page.waitForTimeout(350);
    result.afterClickUrl = page.url();
    result.afterClickDialogs = await visibleDialogCount(page).catch(() => null);

    await page.keyboard.press("Escape").catch(() => {});
    await page.waitForTimeout(200);
    result.afterEscapeDialogs = await visibleDialogCount(page).catch(() => null);
    result.dismissedDialog =
      result.afterClickDialogs !== null &&
      result.afterEscapeDialogs !== null &&
      result.afterClickDialogs > result.afterEscapeDialogs;

    if (result.afterClickUrl && result.afterClickUrl !== beforeUrl) {
      await page.goBack({ waitUntil: "domcontentloaded", timeout: 3000 }).catch((error) => {
        result.errors.push(`goBack: ${error.message}`);
      });
      await page.waitForTimeout(200);
      result.afterReturnUrl = page.url();
      result.returnedToStartingUrl = result.afterReturnUrl === beforeUrl;
      result.status = result.returnedToStartingUrl ? "passed-url-return" : "warning-url-did-not-return";
    } else if (result.dismissedDialog) {
      result.afterReturnUrl = page.url();
      result.returnedToStartingUrl = true;
      result.status = "passed-dialog-dismiss";
    } else {
      result.afterReturnUrl = page.url();
      result.status = "clicked-no-obvious-return-signal";
      result.note =
        "The candidate click did not change URL or open a detectable dialog. Add app-specific selectors for stronger node return checks.";
    }
  } catch (error) {
    result.status = "error";
    result.errors.push(error.message);
  }

  return result;
}

async function runViewport(browser, targetUrl, viewport, outDir, timeoutMs) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    deviceScaleFactor: viewport.name === "mobile" ? 2 : 1,
    isMobile: viewport.name === "mobile",
  });
  const page = await context.newPage();
  const errors = [];
  const consoleErrors = [];
  const pageLoadStartedAt = Date.now();

  page.on("pageerror", (error) => errors.push(`pageerror: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  let responseStatus = null;
  let pageLoadLatencyMs = null;
  let performanceNavigationMs = null;
  try {
    const response = await page.goto(targetUrl, {
      waitUntil: "domcontentloaded",
      timeout: timeoutMs,
    });
    responseStatus = response ? response.status() : null;
    await page.waitForLoadState("networkidle", { timeout: Math.min(timeoutMs, 10000) }).catch(() => {});
    pageLoadLatencyMs = Date.now() - pageLoadStartedAt;
    performanceNavigationMs = await page.evaluate(() => {
      const nav = performance.getEntriesByType("navigation")[0];
      return nav ? Math.round(nav.duration) : null;
    });
  } catch (error) {
    errors.push(`navigation: ${error.message}`);
  }

  const screenshotPath = path.join(outDir, `${viewport.name}-${viewport.width}x${viewport.height}.png`);
  await page.screenshot({ path: screenshotPath, fullPage: true }).catch((error) => {
    errors.push(`screenshot: ${error.message}`);
  });

  let buttonSignals = { count: 0, buttons: [], warnings: [] };
  let canvasChecks = [];
  let axisLabelPresence = { present: false, readableCandidateCount: 0, readableCandidates: [] };
  let nodeReturnChecks = { attempted: false, candidateCount: 0, status: "not-run" };

  try {
    buttonSignals = await collectButtonSignals(page, viewport.name);
  } catch (error) {
    errors.push(`button-check: ${error.message}`);
  }

  try {
    canvasChecks = await collectCanvasSignals(page);
  } catch (error) {
    errors.push(`canvas-check: ${error.message}`);
  }

  try {
    axisLabelPresence = await collectAxisSignals(page);
  } catch (error) {
    errors.push(`axis-check: ${error.message}`);
  }

  try {
    nodeReturnChecks = await collectNodeReturnSignals(page);
  } catch (error) {
    errors.push(`node-return-check: ${error.message}`);
  }

  await context.close();

  return {
    name: viewport.name,
    size: { width: viewport.width, height: viewport.height },
    responseStatus,
    pageLoadLatencyMs,
    performanceNavigationMs,
    visibleButtonCount: buttonSignals.count,
    overlapWarnings: buttonSignals.warnings,
    canvasChecks,
    axisLabelPresence,
    nodeReturnChecks,
    screenshotPath,
    consoleErrors,
    errors,
  };
}

async function main() {
  let args;
  try {
    args = parseArgs(process.argv);
  } catch (error) {
    console.error(JSON.stringify({ errors: [error.message], usage: usage() }, null, 2));
    process.exitCode = 2;
    return;
  }

  if (args.help || !args.url) {
    const payload = args.help
      ? { usage: usage() }
      : { errors: ["Missing required URL argument."], usage: usage() };
    console.log(JSON.stringify(payload, null, 2));
    process.exitCode = args.help ? 0 : 2;
    return;
  }

  const outDir = normalizeOutDir(args.outDir);
  fs.mkdirSync(outDir, { recursive: true });

  const result = {
    targetUrl: args.url,
    generatedAt: new Date().toISOString(),
    outDir,
    viewports: [],
    pageLoadLatency: {},
    visibleButtonCount: {},
    overlapWarnings: [],
    canvasChecks: {},
    axisLabelPresence: {},
    nodeReturnChecks: {},
    screenshotPaths: {},
    errors: [],
  };

  let chromium;
  try {
    ({ chromium } = loadPlaywright());
  } catch (error) {
    result.errors.push(error.message);
    console.log(JSON.stringify(result, null, 2));
    process.exitCode = 1;
    return;
  }

  const browser = await chromium.launch({ headless: true });
  const viewports = [
    { name: "desktop", width: 1440, height: 900 },
    { name: "mobile", width: 390, height: 844 },
  ];

  try {
    for (const viewport of viewports) {
      const viewportResult = await runViewport(browser, args.url, viewport, outDir, args.timeoutMs);
      result.viewports.push(viewportResult);
      result.pageLoadLatency[viewport.name] = viewportResult.pageLoadLatencyMs;
      result.visibleButtonCount[viewport.name] = viewportResult.visibleButtonCount;
      result.overlapWarnings.push(...viewportResult.overlapWarnings);
      result.canvasChecks[viewport.name] = viewportResult.canvasChecks;
      result.axisLabelPresence[viewport.name] = viewportResult.axisLabelPresence;
      result.nodeReturnChecks[viewport.name] = viewportResult.nodeReturnChecks;
      result.screenshotPaths[viewport.name] = viewportResult.screenshotPath;
      result.errors.push(...viewportResult.errors.map((message) => `${viewport.name}: ${message}`));
    }
  } finally {
    await browser.close();
  }

  console.log(JSON.stringify(result, null, 2));
  if (result.errors.length > 0) process.exitCode = 1;
}

main().catch((error) => {
  console.error(
    JSON.stringify(
      {
        errors: [`fatal: ${error.message}`],
        stack: error.stack,
      },
      null,
      2
    )
  );
  process.exitCode = 1;
});
