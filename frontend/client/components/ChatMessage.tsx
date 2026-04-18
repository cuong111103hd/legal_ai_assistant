import { Scale, User } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "./ui/badge";

interface Citation {
  article: string;
  clause?: string;
  law_name: string;
  document_number?: string;
  document_id?: string;
  excerpt?: string;
}

interface ChatMessageProps {
  role: "user" | "ai";
  content: string;
  citations?: Citation[];
  isStreaming?: boolean;
  onCitationClick?: (documentId: string) => void;
}

export function ChatMessage({
  role,
  content,
  citations = [],
  isStreaming = false,
  onCitationClick,
}: ChatMessageProps) {
  const isUser = role === "user";

  return (
    <div
      className={cn(
        "flex w-full gap-4 p-6 rounded-xl",
        isUser ? "bg-primary/5 flex-row-reverse" : "bg-white border border-border/50 shadow-sm"
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 mt-1",
          isUser ? "bg-primary text-primary-foreground" : "bg-blue-100 text-blue-600"
        )}
      >
        {isUser ? <User size={20} /> : <Scale size={20} />}
      </div>

      {/* Message Content */}
      <div className={cn("flex-1 space-y-4", isUser ? "text-right" : "text-left")}>
        <div className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
          {content}
          {isStreaming && <span className="inline-block w-1.5 h-4 ml-1 bg-primary animate-pulse" />}
        </div>

        {/* Citations — clickable badges */}
        {!isUser && citations && citations.length > 0 && (
          <div className="mt-6 pt-4 border-t border-border">
            <h4 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
              <Scale className="w-4 h-4 text-primary" />
              Cơ sở pháp lý
            </h4>
            <div className="flex flex-wrap gap-2">
              {citations.slice(0, 3).map((cite, idx) => (
                <Badge
                  key={idx}
                  variant="outline"
                  className={cn(
                    "bg-blue-50 text-blue-700 border-blue-200 text-xs py-1 px-3",
                    cite.document_id
                      ? "cursor-pointer hover:bg-blue-100 hover:border-blue-300 hover:shadow-sm transition-all"
                      : ""
                  )}
                  onClick={() => {
                    if (cite.document_id && onCitationClick) {
                      onCitationClick(cite.document_id);
                    }
                  }}
                >
                  {cite.article} - {cite.law_name}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
