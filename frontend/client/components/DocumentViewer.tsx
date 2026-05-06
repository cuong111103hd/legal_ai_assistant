import { X, FileText, BookOpen, Hash, Shield } from "lucide-react";
import { Badge } from "./ui/badge";
import { cn } from "@/lib/utils";

export interface Citation {
  article: string;
  clause?: string;
  law_name: string;
  document_number?: string;
  document_id?: string;
  excerpt?: string;
  chunk_content?: string;
}

interface DocumentViewerProps {
  citation: Citation | null;
  onClose: () => void;
}

export function DocumentViewer({ citation, onClose }: DocumentViewerProps) {
  if (!citation) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40 transition-opacity duration-300"
        onClick={onClose}
      />

      {/* Slide-over Panel */}
      <div
        className={cn(
          "fixed top-0 right-0 h-full w-full sm:w-[420px] md:w-[480px] bg-white shadow-2xl z-50",
          "flex flex-col",
          "animate-in slide-in-from-right duration-300"
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-gradient-to-r from-indigo-50 to-white flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-indigo-100 rounded-xl flex items-center justify-center">
              <BookOpen className="w-5 h-5 text-indigo-600" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">Chi tiết Trích dẫn</h2>
              <p className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">Nội dung điều khoản</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-100 rounded-xl transition-colors"
          >
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5 custom-scrollbar">
          {/* Document Title */}
          <div className="space-y-3">
            <h3 className="text-lg font-bold text-slate-900 leading-snug">
              {citation.article} {citation.clause ? `- ${citation.clause}` : ""}
            </h3>

            <div className="flex flex-wrap gap-2">
              <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200 text-xs gap-1">
                <FileText className="w-3 h-3" />
                {citation.law_name}
              </Badge>
              {citation.document_number && (
                <Badge variant="outline" className="bg-slate-50 text-slate-600 border-slate-200 text-xs gap-1">
                  <Hash className="w-3 h-3" />
                  {citation.document_number}
                </Badge>
              )}
            </div>
          </div>

          {/* Divider */}
          <div className="h-px bg-slate-100" />

          {/* Full Text */}
          <div className="prose prose-slate max-w-none w-full">
            <pre className="whitespace-pre-wrap font-sans text-base text-slate-800 leading-[1.8] tracking-normal bg-slate-50/50 p-4 rounded-xl border border-slate-100">
              {citation.chunk_content || citation.excerpt || "Không có nội dung chi tiết cho trích dẫn này."}
            </pre>
          </div>
        </div>
      </div>
    </>
  );
}
