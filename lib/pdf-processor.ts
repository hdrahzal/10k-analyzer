import pdf from "pdf-parse";

export interface TextChunk {
  text: string;
  pageNumber: number;
  chunkIndex: number;
}

export interface ProcessedDocument {
  totalPages: number;
  chunks: TextChunk[];
  fileName: string;
}

const CHUNK_SIZE = 1500; // characters per chunk
const CHUNK_OVERLAP = 200; // overlap between chunks for context continuity

export async function processPDF(
  buffer: Buffer,
  fileName: string
): Promise<ProcessedDocument> {
  const data = await pdf(buffer);

  const pageTexts: { text: string; pageNumber: number }[] = [];

  // pdf-parse provides all text, but we can split by form feeds or estimate pages
  // For accurate page numbers, we'll use the numpages and split text proportionally
  const fullText = data.text;
  const numPages = data.numpages;

  // Split text by common page break indicators or divide evenly
  const roughPageLength = Math.ceil(fullText.length / numPages);

  for (let i = 0; i < numPages; i++) {
    const start = i * roughPageLength;
    const end = Math.min((i + 1) * roughPageLength, fullText.length);
    const pageText = fullText.slice(start, end).trim();

    if (pageText) {
      pageTexts.push({
        text: pageText,
        pageNumber: i + 1,
      });
    }
  }

  // Now chunk the text while preserving page number associations
  const chunks: TextChunk[] = [];
  let chunkIndex = 0;

  for (const page of pageTexts) {
    let position = 0;
    const text = page.text;

    while (position < text.length) {
      const chunkEnd = Math.min(position + CHUNK_SIZE, text.length);
      let chunkText = text.slice(position, chunkEnd);

      // Try to end at a sentence boundary
      if (chunkEnd < text.length) {
        const lastPeriod = chunkText.lastIndexOf(". ");
        const lastNewline = chunkText.lastIndexOf("\n");
        const breakPoint = Math.max(lastPeriod, lastNewline);

        if (breakPoint > CHUNK_SIZE * 0.5) {
          chunkText = chunkText.slice(0, breakPoint + 1);
        }
      }

      chunks.push({
        text: chunkText.trim(),
        pageNumber: page.pageNumber,
        chunkIndex: chunkIndex++,
      });

      // Move position with overlap
      position += chunkText.length - CHUNK_OVERLAP;
      if (position < 0) position = chunkText.length;
    }
  }

  return {
    totalPages: numPages,
    chunks,
    fileName,
  };
}

export function formatChunksForContext(chunks: TextChunk[]): string {
  return chunks
    .map(
      (chunk) =>
        `[Page ${chunk.pageNumber}]\n${chunk.text}`
    )
    .join("\n\n---\n\n");
}
