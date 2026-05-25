"use client";

import { useCallback, useState } from "react";
import { FileText, Upload } from "lucide-react";
import { Spinner } from "@/components/ui/spinner";

interface UploadDropzoneProps {
  onFileProcessed: (docId: string, fileName: string) => void;
}

export function UploadDropzone({ onFileProcessed }: UploadDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = useCallback(
    async (file: File) => {
      if (file.type !== "application/pdf") {
        setError("Please upload a PDF file");
        return;
      }

      setIsProcessing(true);
      setError(null);

      try {
        const formData = new FormData();
        formData.append("file", file);

        const response = await fetch("/api/upload", {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          const data = await response.json();
          throw new Error(data.detail || data.error || "Failed to process PDF");
        }

        const data = await response.json();
        // data: { doc_id, filename, total_chunks, filing_type, already_processed }
        onFileProcessed(data.doc_id, data.filename);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to process PDF");
      } finally {
        setIsProcessing(false);
      }
    },
    [onFileProcessed]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);

      const file = e.dataTransfer.files[0];
      if (file) {
        handleFile(file);
      }
    },
    [handleFile]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        handleFile(file);
      }
    },
    [handleFile]
  );

  if (isProcessing) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 p-12">
        <Spinner className="h-8 w-8 text-primary" />
        <div className="text-center">
          <p className="text-lg font-medium text-foreground">
            Processing your 10-K...
          </p>
          <p className="text-sm text-muted-foreground">
            Extracting and analyzing document content
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-6">
      <div className="text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">
          10-K/Q Analyzer
        </h1>
        <p className="mt-2 max-w-md text-muted-foreground">
          Upload a 10-K/Q filing to start analyzing. You can then ask our dedicated chatbot about the filing you&apos;ve uploaded.
        </p>
      </div>

      <label
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={`
          flex w-full max-w-lg cursor-pointer flex-col items-center justify-center gap-4 
          rounded-xl border-2 border-dashed p-12 transition-all
          ${
            isDragging
              ? "border-primary bg-primary/5"
              : "border-border hover:border-primary/50 hover:bg-muted/50"
          }
        `}
      >
        <input
          type="file"
          accept=".pdf"
          onChange={handleInputChange}
          className="hidden"
        />

        <div
          className={`rounded-full p-4 transition-colors ${
            isDragging ? "bg-primary/10" : "bg-muted"
          }`}
        >
          {isDragging ? (
            <FileText className="h-8 w-8 text-primary" />
          ) : (
            <Upload className="h-8 w-8 text-muted-foreground" />
          )}
        </div>

        <div className="text-center">
          <p className="font-medium text-foreground">
            {isDragging ? "Drop your PDF here" : "Drag & drop your 10-K PDF"}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            or click to browse files
          </p>
        </div>
      </label>

      {error && (
        <p className="text-sm text-destructive">{error}</p>
      )}
    </div>
  );
}
