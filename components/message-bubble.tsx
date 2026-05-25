"use client";

import ReactMarkdown from "react-markdown";
import { FileText, User, ThumbsUp, ThumbsDown } from "lucide-react";

export interface Citation {
  page: number;
  section: string;
  anchor_text: string;
  doc_id: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  traceId?: string;
}

interface MessageBubbleProps {
  message: ChatMessage;
  onPageClick?: (citation: Citation) => void;
  onFeedback?: (traceId: string, rating: "up" | "down") => void;
}

function CitationLink({
  page,
  citation,
  onPageClick,
}: {
  page: number;
  citation: Citation;
  onPageClick: (c: Citation) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onPageClick(citation)}
      className="mx-0.5 inline font-bold text-primary underline underline-offset-2 hover:opacity-75"
    >
      [Page {page}]
    </button>
  );
}

function renderAssistantContent(
  content: string,
  citations: Citation[],
  onPageClick?: (c: Citation) => void
) {
  const citationMap = Object.fromEntries(citations.map((c) => [c.page, c]));
  const parts = content.split(/(\*\*\[Page \d+\]\*\*)/g);

  return (
    <div className="prose prose-sm max-w-none">
      {parts.map((part, i) => {
        const match = part.match(/\*\*\[Page (\d+)\]\*\*/);
        if (match) {
          const page = parseInt(match[1], 10);
          const citation = citationMap[page];
          if (citation && onPageClick) {
            return (
              <CitationLink key={i} page={page} citation={citation} onPageClick={onPageClick} />
            );
          }
          return <strong key={i}>[Page {page}]</strong>;
        }
        return (
          <ReactMarkdown
            key={i}
            components={{
              p: ({ children }) => <span>{children}</span>,
              strong: ({ children }) => (
                <strong className="font-bold text-primary">{children}</strong>
              ),
            }}
          >
            {part}
          </ReactMarkdown>
        );
      })}
    </div>
  );
}

export function MessageBubble({ message, onPageClick, onFeedback }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
          isUser ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
        }`}
      >
        {isUser ? <User className="h-4 w-4" /> : <FileText className="h-4 w-4" />}
      </div>

      <div className="flex max-w-[80%] flex-col gap-1">
        <div
          className={`rounded-2xl px-4 py-3 ${
            isUser ? "bg-primary text-primary-foreground" : "bg-muted text-foreground"
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap text-sm">{message.content}</p>
          ) : (
            renderAssistantContent(message.content, message.citations || [], onPageClick)
          )}
        </div>

        {!isUser && message.traceId && onFeedback && (
          <div className="flex gap-2 pl-1">
            <button
              type="button"
              onClick={() => onFeedback(message.traceId!, "up")}
              className="text-muted-foreground transition-colors hover:text-green-600"
              aria-label="Helpful"
            >
              <ThumbsUp className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => onFeedback(message.traceId!, "down")}
              className="text-muted-foreground transition-colors hover:text-red-500"
              aria-label="Not helpful"
            >
              <ThumbsDown className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
