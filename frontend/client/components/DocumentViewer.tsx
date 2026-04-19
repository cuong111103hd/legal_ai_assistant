import { useState, useEffect } from "react";
import { X, FileText, Loader2, BookOpen, Hash, Shield } from "lucide-react";
import { Badge } from "./ui/badge";
import { cn } from "@/lib/utils";

interface LegalDocument {
  id: string;
  title: string;
  clean_text: string;
  content_html?: string;
  doc_type: string;
  document_number: string;
  validity_status: string;
}

interface DocumentViewerProps {
  documentId: string | null;
  onClose: () => void;
}

export function DocumentViewer({ documentId, onClose }: DocumentViewerProps) {
  const [doc, setDoc] = useState<LegalDocument | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!documentId) {
      setDoc(null);
      return;
    }

    const fetchDoc = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`http://127.0.0.1:8000/documents/${documentId}`);
        if (!res.ok) {
          throw new Error(res.status === 404 ? "Văn bản không tìm thấy trong cơ sở dữ liệu." : "Lỗi tải văn bản.");
        }
        const data = await res.json();
        setDoc(data);
      } catch (err: any) {
        setError(err.message || "Không thể tải văn bản.");
      } finally {
        setLoading(false);
      }
    };

    fetchDoc();
  }, [documentId]);

  if (!documentId) return null;

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
              <h2 className="text-sm font-bold text-slate-900">Văn bản Pháp luật</h2>
              <p className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">Toàn văn trích dẫn</p>
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
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          {loading && (
            <div className="flex flex-col items-center justify-center h-64 gap-3">
              <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
              <p className="text-sm text-slate-500">Đang tải văn bản…</p>
            </div>
          )}

          {error && (
            <div className="m-6 p-4 bg-red-50 border border-red-200 rounded-xl">
              <p className="text-sm text-red-700 font-medium">{error}</p>
            </div>
          )}

          {doc && !loading && (
            <div className="p-6 space-y-5">
              {/* Document Title */}
              <div className="space-y-3">
                <h3 className="text-lg font-bold text-slate-900 leading-snug">
                  {doc.title || "Không có tiêu đề"}
                </h3>

                <div className="flex flex-wrap gap-2">
                  {doc.doc_type && (
                    <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200 text-xs gap-1">
                      <FileText className="w-3 h-3" />
                      {doc.doc_type}
                    </Badge>
                  )}
                  {doc.document_number && (
                    <Badge variant="outline" className="bg-slate-50 text-slate-600 border-slate-200 text-xs gap-1">
                      <Hash className="w-3 h-3" />
                      {doc.document_number}
                    </Badge>
                  )}
                  {doc.validity_status && (
                    <Badge
                      variant="outline"
                      className={cn(
                        "text-xs gap-1",
                        doc.validity_status.includes("Còn hiệu lực")
                          ? "bg-green-50 text-green-700 border-green-200"
                          : "bg-amber-50 text-amber-700 border-amber-200"
                      )}
                    >
                      <Shield className="w-3 h-3" />
                      {doc.validity_status}
                    </Badge>
                  )}
                </div>
              </div>

              {/* Divider */}
              <div className="h-px bg-slate-100" />

              {/* Full Text */}
              <div className="prose prose-slate max-w-none w-full">
                {doc.content_html ? (
                  <div 
                    className="whitespace-pre-wrap font-sans text-base text-slate-800 leading-[1.8] tracking-normal bg-slate-50/50 p-4 rounded-xl border border-slate-100"
                    dangerouslySetInnerHTML={{ __html: doc.content_html }}
                  />
                ) : (
                  <pre className="whitespace-pre-wrap font-sans text-sm text-slate-700 leading-relaxed bg-slate-50/50 p-4 rounded-xl border border-slate-100">
                    {doc.clean_text || "Không có nội dung."}
                  </pre>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
