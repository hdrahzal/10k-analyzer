"use client";

import { useState } from "react";
import { UploadDropzone } from "@/components/upload-dropzone";
import { ChatInterface } from "@/components/chat-interface";

type AppState = "upload" | "chat";

export default function Home() {
  const [appState, setAppState] = useState<AppState>("upload");
  const [documentContext, setDocumentContext] = useState<string>("");
  const [fileName, setFileName] = useState<string>("");

  const handleFileProcessed = (context: string, name: string) => {
    setDocumentContext(context);
    setFileName(name);
    setAppState("chat");
  };

  const handleReset = () => {
    setDocumentContext("");
    setFileName("");
    setAppState("upload");
  };

  return (
    <div className="flex h-screen flex-col bg-background">
      {appState === "upload" ? (
        <main className="flex flex-1 items-center justify-center p-6">
          <UploadDropzone onFileProcessed={handleFileProcessed} />
        </main>
      ) : (
        <ChatInterface
          documentContext={documentContext}
          fileName={fileName}
          onReset={handleReset}
        />
      )}
    </div>
  );
}
