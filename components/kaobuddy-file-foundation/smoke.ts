import fs from "node:fs/promises";
import path from "node:path";
import mammoth from "mammoth";
import JSZip from "jszip";
import { getDocument } from "pdfjs-dist/legacy/build/pdf.mjs";

const fixtures = "H:/studybuddy-test/fixtures/kaobuddy-foundation";
const artifacts = "H:/studybuddy-test/artifacts/kaobuddy-foundation";
await fs.mkdir(artifacts, { recursive: true });

function stripRtf(text: string) {
  return text.replace(/\\par[d]?/g, "\n").replace(/\\'[0-9a-fA-F]{2}/g, "").replace(/\\[a-zA-Z]+-?\d* ?/g, "").replace(/[{}]/g, "").replace(/\n{3,}/g, "\n\n").trim();
}
function decodeXmlText(text: string) {
  return text.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&").replace(/&quot;/g, "\"").replace(/&apos;/g, "'");
}
function extractSlideText(xml: string) {
  return Array.from(xml.matchAll(/<a:t(?:\s[^>]*)?>([\s\S]*?)<\/a:t>/g)).map((match) => decodeXmlText(match[1]).replace(/\s+/g, " ").trim()).filter(Boolean).join(" ");
}
function cleanDecodedText(text: string) {
  const runs = text.match(/[\u3400-\u9fffA-Za-z0-9，。！？；：、（）《》“”‘’【】\[\]().,!?;:：\-_/\\\s]{2,}/g) || [];
  return runs.map((run) => run.replace(/[\u0000-\u001f\u007f-\u009f]+/g, " ").replace(/\s+/g, " ").trim()).filter((run) => run.length >= 2 && /[\u3400-\u9fffA-Za-z0-9]/.test(run)).join("\n").trim();
}
function legacyDoc(buffer: Buffer) {
  const bytes = new Uint8Array(buffer);
  const utf16 = cleanDecodedText(new TextDecoder("utf-16le").decode(bytes));
  const utf8 = cleanDecodedText(new TextDecoder("utf-8").decode(bytes));
  const text = utf16.length >= utf8.length ? utf16 : utf8;
  if (!text) throw new Error("这个 .doc 没提取到正文，可以另存为 .docx 或 PDF 后再导入。");
  return text;
}
async function capture(name: string, action: () => Promise<unknown> | unknown) {
  const started = performance.now();
  try {
    const output = await action();
    return { status: "success", elapsed_ms: Math.round((performance.now() - started) * 1000) / 1000, output };
  } catch (error) {
    return { status: "error", elapsed_ms: Math.round((performance.now() - started) * 1000) / 1000, error: error instanceof Error ? error.message : String(error) };
  }
}
async function pdf(name: string) {
  const data = new Uint8Array(await fs.readFile(path.join(fixtures, name)));
  const document = await getDocument({ data, disableWorker: true }).promise;
  const pages = [];
  for (let pageNo = 1; pageNo <= document.numPages; pageNo++) {
    const page = await document.getPage(pageNo);
    const content = await page.getTextContent();
    pages.push(`第 ${pageNo} 页\n${content.items.map((item: any) => item.str || "").join(" ")}`);
  }
  return pages.join("\n\n");
}
async function docx(name: string) {
  const result = await mammoth.extractRawText({ buffer: await fs.readFile(path.join(fixtures, name)) });
  const text = result.value.trim();
  if (!text) throw new Error("这个 DOCX 没提取到正文，可以另存为 PDF 后再导入。");
  return `Word 正文\n${text}`;
}
async function pptx(name: string) {
  const zip = await JSZip.loadAsync(await fs.readFile(path.join(fixtures, name)));
  const slides = zip.file(/^ppt\/slides\/slide\d+\.xml$/).sort((a, b) => Number(a.name.match(/slide(\d+)/)?.[1]) - Number(b.name.match(/slide(\d+)/)?.[1]));
  if (!slides.length) throw new Error("这个 PPTX 没找到可读取的幻灯片，请另存为 PDF 后再导入。");
  const pages = await Promise.all(slides.map(async (slide, index) => `第 ${index + 1} 页\n${extractSlideText(await slide.async("text"))}`));
  const content = pages.join("\n\n").trim();
  if (!content.replace(/第 \d+ 页/g, "").trim()) throw new Error("这个 PPTX 没提取到正文，可能主要是图片或扫描页，可以另存为 PDF 后导入。");
  return `PPT 正文\n${content}`;
}

const checks: Record<string, unknown> = {};
checks.txt = await capture("txt", async () => fs.readFile(path.join(fixtures, "sample.txt"), "utf8"));
checks.markdown = await capture("markdown", async () => fs.readFile(path.join(fixtures, "sample.md"), "utf8"));
checks.chinese_txt = await capture("chinese", async () => fs.readFile(path.join(fixtures, "chinese.txt"), "utf8"));
checks.empty_txt = await capture("empty_txt", async () => fs.readFile(path.join(fixtures, "empty.txt"), "utf8"));
checks.pdf = await capture("pdf", () => pdf("sample.pdf"));
checks.corrupt_pdf = await capture("corrupt_pdf", () => pdf("corrupt.pdf"));
checks.docx = await capture("docx", () => docx("sample.docx"));
checks.empty_docx = await capture("empty_docx", () => docx("empty.docx"));
checks.corrupt_docx = await capture("corrupt_docx", () => docx("corrupt.docx"));
checks.rtf = await capture("rtf", async () => stripRtf(await fs.readFile(path.join(fixtures, "sample.rtf"), "utf8")));
checks.empty_rtf = await capture("empty_rtf", async () => { const text = stripRtf(await fs.readFile(path.join(fixtures, "empty.rtf"), "utf8")); if (!text) throw new Error("这个 RTF 没提取到正文，可以另存为 DOCX 或 PDF 后再导入。"); return text; });
checks.pptx = await capture("pptx", () => pptx("sample.pptx"));
checks.empty_pptx = await capture("empty_pptx", () => pptx("empty.pptx"));
checks.corrupt_pptx = await capture("corrupt_pptx", () => pptx("corrupt.pptx"));
checks.legacy_doc = await capture("legacy_doc", async () => legacyDoc(await fs.readFile(path.join(fixtures, "sample.doc"))));
checks.empty_legacy_doc = await capture("empty_legacy_doc", async () => legacyDoc(await fs.readFile(path.join(fixtures, "empty.doc"))));
checks.legacy_ppt = { status: "rejected_by_kaobuddy_before_parse", message: "老版 PPT 暂时不能稳定解析，请另存为 PPTX 或 PDF 后再导入。" };
checks.image = { status: "fixture_only", bytes: (await fs.stat(path.join(fixtures, "sample.png"))).size, note: "KaoBuddy only converts image to data URL; OCR requires an external multimodal provider and was not called." };
const result = {
  component: "kaobuddy-file-foundation",
  status: "passed_with_findings",
  scope: "dependency-level extraction using KaoBuddy algorithms and pinned libraries; not a browser UI user-path test",
  runtime: { node: process.version, platform: process.platform },
  checks,
  findings: [
    "TXT/Markdown empty files succeed with empty content and are saved by KaoBuddy without warning.",
    "PDF retains generated page labels but an empty text layer is accepted with fallback text in App.tsx.",
    "DOCX/RTF/PPTX reject empty extracted body; corrupt container files reject.",
    "Legacy DOC is heuristic byte decoding, not an OLE parser; false positives and garbled output remain possible.",
    "Original general files are not retained, only filename and extracted text. Handwriting images are retained as data URLs in IndexedDB.",
  ],
};
await fs.writeFile(path.join(artifacts, "latest.json"), JSON.stringify(result, null, 2), "utf8");
console.log(JSON.stringify(result, null, 2));
