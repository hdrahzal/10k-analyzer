"use client";

import { useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/TextLayer.css";
import "react-pdf/dist/Page/AnnotationLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;

interface PdfViewerProps {
  docId: string;
  page: number;
  anchorText: string;
  onClose: () => void;
}

export function PdfViewer({ docId, page, anchorText, onClose }: PdfViewerProps) {
  const pdfUrl = `/api/pdf/${docId}`;
  const [numPages, setNumPages] = useState(0);
  const [currentPage, setCurrentPage] = useState(page);

  const anchorLower = anchorText.toLowerCase();
  const anchorPrefix = anchorLower.slice(0, 15);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="flex max-h-[92vh] w-[820px] flex-col rounded-xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b px-5 py-3">
          <div>
            <span className="text-sm font-semibold">Page {currentPage}{numPages ? ` of ${numPages}` : ""}</span>
            {anchorText && (
              <p className="mt-0.5 max-w-[680px] truncate text-xs text-muted-foreground">
                &quot;{anchorText}&quot;
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              className="text-sm text-gray-500 hover:text-gray-800"
              disabled={currentPage <= 1}
              aria-label="Previous page"
            >
              ‹ Prev
            </button>
            <button
              onClick={() => setCurrentPage((p) => Math.min(numPages || p + 1, p + 1))}
              className="text-sm text-gray-500 hover:text-gray-800"
              disabled={!!numPages && currentPage >= numPages}
              aria-label="Next page"
            >
              Next ›
            </button>
            <button
              onClick={onClose}
              className="ml-2 text-xl leading-none text-gray-400 hover:text-gray-600"
              aria-label="Close"
            >
              ✕
            </button>
          </div>
        </div>
        <div className="flex flex-1 justify-center overflow-auto py-4">
          <Document
            file={pdfUrl}
            onLoadSuccess={({ numPages }) => setNumPages(numPages)}
          >
            <Page
              pageNumber={currentPage}
              width={760}
              customTextRenderer={({ str }) => {
                if (anchorPrefix && str.toLowerCase().includes(anchorPrefix)) {
                  return `<mark style="background:#fef08a;border-radius:2px">${str}</mark>`;
                }
                return str;
              }}
            />
          </Document>
        </div>
      </div>
    </div>
  );
}
