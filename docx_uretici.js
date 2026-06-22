/**
 * docx_uretici.js — Akreditif Analiz Sistemi v9.0
 *
 * KURAL: Bu script hiçbir analiz yapmaz.
 * Tek görevi: stdin'den gelen final_report string'ini
 * biçimlendirilmiş DOCX'e dönüştürmek.
 *
 * Çağrı:
 *   node docx_uretici.js <input_txt> <output_docx>
 *
 * input_txt: markdown_raporu() çıktısının kaydedildiği geçici dosya
 * output_docx: hedef .docx yolu
 */

"use strict";

const fs   = require("fs");
const path = require("path");

const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
  LevelFormat, VerticalAlign,
} = require("docx");

// ── Argümanlar ───────────────────────────────────────────────────────────────
const inputFile  = process.argv[2];
const outputFile = process.argv[3];

if (!inputFile || !outputFile) {
  console.error("Kullanım: node docx_uretici.js <input_txt> <output_docx>");
  process.exit(1);
}

const reportText = fs.readFileSync(inputFile, "utf8");

// ── Stil sabitleri ────────────────────────────────────────────────────────────
const BORDER = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const ALL_BORDERS = { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER };
const PAGE_W   = 11906; // A4 DXA
const MARGIN   = 1000;
const CONTENT_W = PAGE_W - MARGIN * 2; // 9906
const COL_WIDTHS = {
  2: [4953, 4953],
  3: [3000, 4000, 2906],
  4: [2000, 3500, 1500, 2906],
  5: [1500, 1500, 2000, 2000, 2906],
  6: [1400, 900,  900,  1500, 2000, 2706],
};

// ── Yardımcılar ──────────────────────────────────────────────────────────────
function cellWidths(colCount) {
  const w = COL_WIDTHS[colCount];
  if (w) return w;
  const each = Math.floor(CONTENT_W / colCount);
  return Array(colCount).fill(each);
}

function headerCell(text, width) {
  return new TableCell({
    borders: ALL_BORDERS,
    width: { size: width, type: WidthType.DXA },
    shading: { fill: "2E75B6", type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({
      children: [new TextRun({ text, bold: true, color: "FFFFFF", size: 18, font: "Arial" })],
    })],
  });
}

function dataCell(text, width, isStatus) {
  // Durum kolonları için renklendirme
  let color = "000000";
  if (isStatus) {
    const t = text.toUpperCase();
    if (t.includes("UYUMLU") || t.includes("TAMAM") || t.includes("OK"))
      color = "276749";
    else if (t.includes("REZERV") || t.includes("MAJOR") || t.includes("EKSİK"))
      color = "C53030";
    else if (t.includes("UYARI") || t.includes("MANUEL") || t.includes("MEDIUM"))
      color = "B7791F";
  }
  const runs = parseInline(text, color);
  return new TableCell({
    borders: ALL_BORDERS,
    width: { size: width || 1000, type: WidthType.DXA },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({ children: runs })],
  });
}

/** Satır içi **bold** ve `code` işler */
function parseInline(text, baseColor) {
  const runs = [];
  // **bold** ve `code` dönüşümü
  const re = /(\*\*(.+?)\*\*|`(.+?)`)/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last)
      runs.push(new TextRun({ text: text.slice(last, m.index), size: 18, font: "Arial", color: baseColor || "000000" }));
    if (m[2] !== undefined)
      runs.push(new TextRun({ text: m[2], bold: true, size: 18, font: "Arial", color: baseColor || "000000" }));
    else
      runs.push(new TextRun({ text: m[3], font: "Courier New", size: 18, color: baseColor || "000000" }));
    last = m.index + m[0].length;
  }
  if (last < text.length)
    runs.push(new TextRun({ text: text.slice(last), size: 18, font: "Arial", color: baseColor || "000000" }));
  return runs.length ? runs : [new TextRun({ text, size: 18, font: "Arial", color: baseColor || "000000" })];
}

function buildTable(lines) {
  // lines[0] = başlık satırı, lines[1] = ayraç (|:---|), lines[2..] = veri
  if (lines.length < 2) return null;

  const parseRow = line =>
    line.replace(/^\|/, "").replace(/\|$/, "").split("|").map(c => c.trim());

  const headers = parseRow(lines[0]);
  const colCount = headers.length;
  const widths   = cellWidths(colCount);
  const statusColIdx = colCount - 1; // son kolon genellikle Durum

  const headerRow = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) => headerCell(h, widths[i])),
  });

  const dataRows = lines.slice(2).map((line, ri) => {
    const cells = parseRow(line);
    return new TableRow({
      children: cells.map((c, i) =>
        dataCell(c, widths[i], i === statusColIdx)
      ),
    });
  });

  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: widths,
    rows: [headerRow, ...dataRows],
  });
}

// ── Markdown → DOCX AST dönüşümü ────────────────────────────────────────────
function buildChildren(reportText) {
  const children = [];
  const lines = reportText.split("\n");
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // H1
    if (line.startsWith("# ")) {
      children.push(new Paragraph({
        heading: HeadingLevel.HEADING_1,
        children: [new TextRun({ text: line.slice(2).trim(), size: 32, bold: true, font: "Arial", color: "1A365D" })],
        spacing: { before: 240, after: 120 },
      }));
      i++; continue;
    }

    // H2
    if (line.startsWith("## ")) {
      children.push(new Paragraph({
        heading: HeadingLevel.HEADING_2,
        children: [new TextRun({ text: line.slice(3).trim(), size: 26, bold: true, font: "Arial", color: "2B6CB0" })],
        spacing: { before: 200, after: 80 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "3182CE", space: 1 } },
      }));
      i++; continue;
    }

    // H3
    if (line.startsWith("### ")) {
      children.push(new Paragraph({
        heading: HeadingLevel.HEADING_3,
        children: [new TextRun({ text: line.slice(4).trim(), size: 22, bold: true, font: "Arial", color: "2C5282" })],
        spacing: { before: 160, after: 60 },
      }));
      i++; continue;
    }

    // Yatay çizgi
    if (line.trim() === "---") {
      children.push(new Paragraph({
        children: [],
        border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "CCCCCC", space: 1 } },
        spacing: { before: 80, after: 80 },
      }));
      i++; continue;
    }

    // Tablo bloğu
    if (line.startsWith("|")) {
      const tableLines = [];
      while (i < lines.length && lines[i].startsWith("|")) {
        tableLines.push(lines[i]);
        i++;
      }
      const tbl = buildTable(tableLines);
      if (tbl) children.push(tbl);
      children.push(new Paragraph({ children: [], spacing: { after: 80 } }));
      continue;
    }

    // Kod bloğu (``` ... ```)
    if (line.startsWith("```")) {
      i++;
      const codeLines = [];
      while (i < lines.length && !lines[i].startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // kapanış ```
      for (const cl of codeLines) {
        children.push(new Paragraph({
          children: [new TextRun({ text: cl || " ", font: "Courier New", size: 18, color: "1A202C" })],
          spacing: { before: 0, after: 0 },
          indent: { left: 360 },
          shading: { fill: "F7FAFC", type: ShadingType.CLEAR },
        }));
      }
      children.push(new Paragraph({ children: [], spacing: { after: 80 } }));
      continue;
    }

    // Bullet madde işareti (*)
    if (line.startsWith("* ") || line.startsWith("- ")) {
      const content = line.slice(2).trim();
      let color = "000000";
      const cu = content.toUpperCase();
      if (cu.startsWith("REZERV") || cu.includes("[REZERV]") || cu.includes("MAJOR"))
        color = "C53030";
      else if (cu.includes("[TAMAM]") || cu.startsWith("UYUMLU"))
        color = "276749";
      children.push(new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: parseInline(content, color),
        spacing: { before: 20, after: 20 },
      }));
      i++; continue;
    }

    // Kalın meta satırı (**Tarih:** ...)
    if (line.startsWith("**")) {
      children.push(new Paragraph({
        children: parseInline(line, "4A5568"),
        spacing: { before: 40, after: 40 },
      }));
      i++; continue;
    }

    // Boş satır
    if (line.trim() === "") {
      children.push(new Paragraph({ children: [], spacing: { after: 60 } }));
      i++; continue;
    }

    // Normal paragraf
    children.push(new Paragraph({
      children: parseInline(line, "2D3748"),
      spacing: { before: 40, after: 40 },
    }));
    i++;
  }

  return children;
}

// ── Belge oluştur ────────────────────────────────────────────────────────────
const children = buildChildren(reportText);

const doc = new Document({
  numbering: {
    config: [{
      reference: "bullets",
      levels: [{
        level: 0,
        format: LevelFormat.BULLET,
        text: "•",
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } },
      }],
    }],
  },
  styles: {
    default: {
      document: { run: { font: "Arial", size: 20 } },
    },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run:       { size: 32, bold: true, font: "Arial", color: "1A365D" },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run:       { size: 26, bold: true, font: "Arial", color: "2B6CB0" },
        paragraph: { spacing: { before: 200, after: 80  }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run:       { size: 22, bold: true, font: "Arial", color: "2C5282" },
        paragraph: { spacing: { before: 160, after: 60  }, outlineLevel: 2 } },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: PAGE_W, height: 16838 },
        margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
      },
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outputFile, buffer);
  console.log("[+] DOCX oluşturuldu:", outputFile);
}).catch(err => {
  console.error("[ERROR] DOCX üretim hatası:", err);
  process.exit(1);
});
