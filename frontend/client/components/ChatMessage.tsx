import { Scale, User, CheckCircle, AlertTriangle, BookOpen, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "./ui/badge";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

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

const headerMap: Record<string, { label: string; icon: any; colorClass: string; borderClass: string }> = {
  "[TRẢ LỜI]": { 
    label: "CÂU TRẢ LỜI", 
    icon: CheckCircle, 
    colorClass: "text-emerald-700 bg-emerald-50", 
    borderClass: "border-emerald-100" 
  },
  "[PHÂN TÍCH RỦI RO]": { 
    label: "PHÂN TÍCH RỦI RO", 
    icon: AlertTriangle, 
    colorClass: "text-amber-700 bg-amber-50", 
    borderClass: "border-amber-100" 
  },
  "[NGUỒN TRÍCH DẪN]": { 
    label: "TÀI LIỆU TRÍCH DẪN", 
    icon: BookOpen, 
    colorClass: "text-indigo-700 bg-indigo-50", 
    borderClass: "border-indigo-100" 
  },
};

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
        "flex w-full gap-4 p-6 rounded-2xl transition-all duration-300",
        isUser 
          ? "bg-slate-50/80 border border-slate-100 flex-row-reverse" 
          : "bg-white border border-slate-100 shadow-sm hover:shadow-md"
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "w-10 h-10 rounded-2xl flex items-center justify-center flex-shrink-0 mt-1 shadow-sm",
          isUser ? "bg-indigo-600 text-white" : "bg-white border border-slate-100 text-indigo-600"
        )}
      >
        {isUser ? <User size={20} /> : <Scale size={20} />}
      </div>

      {/* Message Content */}
      <div className={cn("flex-1", isUser ? "text-right" : "text-left")}>
        <div className={cn(
          "prose prose-slate max-w-none prose-sm md:prose-base",
          isUser ? "text-slate-700" : "text-slate-800"
        )}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              h3: ({ node, children, ...props }) => {
                const text = String(children);
                const match = Object.keys(headerMap).find(key => text.includes(key));
                
                if (match) {
                  const { label, icon: Icon, colorClass, borderClass } = headerMap[match];
                  return (
                    <div className={cn(
                      "flex items-center gap-2 px-4 py-2 rounded-xl border mb-4 mt-6 first:mt-0 w-fit",
                      colorClass,
                      borderClass
                    )}>
                      <Icon size={16} />
                      <span className="text-xs font-black tracking-widest uppercase">{label}</span>
                    </div>
                  );
                }
                return <h3 className="text-lg font-bold text-slate-900 mt-6 mb-3" {...props}>{children}</h3>;
              },
              p: ({ children }) => (
                <p className="leading-relaxed mb-4 last:mb-0 text-inherit font-medium opacity-90">
                  {children}
                </p>
              ),
              ul: ({ children }) => (
                <ul className="space-y-2 mb-4 list-none p-0">
                  {children}
                </ul>
              ),
              li: ({ children }) => (
                <li className="flex items-start gap-2 text-sm text-slate-600 italic">
                  <ChevronRight size={14} className="mt-1 flex-shrink-0 text-indigo-400" />
                  <span>{children}</span>
                </li>
              ),
            }}
          >
            {content}
          </ReactMarkdown>
          {isStreaming && (
            <span className="inline-block w-2 h-5 ml-1 bg-indigo-600 animate-pulse rounded-full align-middle" />
          )}
        </div>

        {/* Citations — clickable badges */}
        {!isUser && citations && citations.length > 0 && (
          <div className="mt-8 pt-6 border-t border-slate-100 animate-in fade-in slide-in-from-bottom-2">
            <h4 className="text-[11px] font-black text-slate-400 uppercase tracking-widest mb-4 flex items-center gap-2">
              <Scale className="w-4 h-4 text-indigo-400" />
              Căn cứ pháp lý áp dụng
            </h4>
            <div className="flex flex-wrap gap-2">
              {citations.map((cite, idx) => (
                <Badge
                  key={idx}
                  variant="outline"
                  className={cn(
                    "bg-white text-indigo-700 border-slate-200 text-xs py-1.5 px-4 rounded-xl shadow-sm",
                    cite.document_id
                      ? "cursor-pointer hover:bg-indigo-50 hover:border-indigo-200 hover:text-indigo-800 transition-all font-semibold"
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
