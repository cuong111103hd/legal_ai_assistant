import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Sidebar } from "@/components/Sidebar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  ArrowLeft, 
  BookOpen, 
  FileText, 
  Hash, 
  Shield, 
  Loader2, 
  Download, 
  Printer, 
  Share2 
} from "lucide-react";
import { cn } from "@/lib/utils";

interface LegalDoc {
  id: string;
  title: string;
  clean_text: string;
  content_html?: string;
  doc_type: string;
  document_number: string;
  validity_status: string;
  issuing_body: string;
}

export default function DocumentDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [doc, setDoc] = useState<LegalDoc | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;

    const fetchDoc = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`http://127.0.0.1:8000/documents/${id}`);
        if (!res.ok) {
          throw new Error("Không tìm thấy văn bản pháp luật này.");
        }
        const data = await res.json();
        setDoc(data);
      } catch (err: any) {
        setError(err.message || "Lỗi tải dữ liệu văn bản.");
      } finally {
        setLoading(false);
      }
    };

    fetchDoc();
  }, [id]);

  return (
    <div className="flex h-screen bg-[#F8FAFC] overflow-hidden">
      <Sidebar isOpen={sidebarOpen} />

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="bg-white border-b border-border px-8 py-4 flex items-center justify-between z-10 shadow-sm relative">
          <div className="flex items-center gap-4">
            <Button 
                variant="ghost" 
                size="icon" 
                onClick={() => navigate("/legislation")}
                className="rounded-xl hover:bg-slate-100"
            >
              <ArrowLeft className="w-5 h-5 text-slate-600" />
            </Button>
            <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
              <FileText className="text-primary w-6 h-6" />
              Chi tiết Văn bản
            </h1>
          </div>

          <div className="flex items-center gap-2">
             <Button variant="outline" size="sm" className="rounded-xl gap-2 text-slate-600 border-slate-200">
                <Printer className="w-4 h-4" />
                In
             </Button>
             <Button variant="outline" size="sm" className="rounded-xl gap-2 text-slate-600 border-slate-200">
                <Download className="w-4 h-4" />
                Tải về
             </Button>
             <Button variant="outline" size="sm" className="rounded-xl gap-2 text-slate-600 border-slate-200">
                <Share2 className="w-4 h-4" />
                Chia sẻ
             </Button>
          </div>
        </div>

        {/* Main Content Area */}
        <main className="flex-1 min-h-0 overflow-y-auto bg-[#F8FAFC]">
          <div className="p-4 md:p-8 flex justify-center">
            <div className="max-w-4xl w-full bg-white rounded-[2.5rem] border border-slate-100 shadow-sm flex flex-col mb-10 overflow-visible">
            {loading ? (
               <div className="flex flex-col items-center justify-center py-40 gap-4">
                  <Loader2 className="w-12 h-12 text-indigo-500 animate-spin" />
                  <p className="text-slate-500">Đang chuẩn bị nội dung văn bản...</p>
               </div>
            ) : error ? (
               <div className="flex flex-col items-center justify-center py-40 px-10 text-center gap-6">
                  <div className="w-20 h-20 bg-red-50 rounded-3xl flex items-center justify-center">
                     <Shield className="w-10 h-10 text-red-500" />
                  </div>
                  <div className="space-y-2">
                     <h2 className="text-2xl font-bold text-slate-900">Rất tiếc!</h2>
                     <p className="text-slate-500 max-w-sm">{error}</p>
                  </div>
                  <Button onClick={() => navigate("/legislation")} variant="outline" className="rounded-xl">
                     Quay lại thư viện
                  </Button>
               </div>
            ) : doc && (
               <>
                  {/* Document Header Panel */}
                  <div className="p-8 md:p-12 bg-gradient-to-br from-slate-50 to-white border-b border-slate-100 italic">
                     <div className="space-y-6">
                        <div className="flex flex-wrap gap-2">
                           <Badge className="bg-indigo-600 text-white border-none py-1">VĂN BẢN GỐC</Badge>
                           {doc.doc_type && (
                              <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200 gap-1 px-3">
                                 <BookOpen className="w-3 h-3" />
                                 {doc.doc_type}
                              </Badge>
                           )}
                           <Badge 
                              variant="outline" 
                              className={cn(
                                 "gap-1 px-3",
                                 doc.validity_status?.includes("Còn hiệu lực") 
                                    ? "bg-green-50 text-green-700 border-green-200" 
                                    : "bg-amber-50 text-amber-700 border-amber-200"
                              )}
                           >
                              <Shield className="w-3 h-3" />
                              {doc.validity_status}
                           </Badge>
                        </div>

                        <h2 className="text-2xl md:text-3xl font-black text-slate-900 leading-tight">
                           {doc.title}
                        </h2>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-slate-100">
                           <div className="flex items-center gap-3">
                              <div className="w-10 h-10 bg-white rounded-xl flex items-center justify-center border border-slate-100 shadow-sm">
                                 <Hash className="w-5 h-5 text-slate-400" />
                              </div>
                              <div>
                                 <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Số hiệu văn bản</p>
                                 <p className="text-sm font-bold text-slate-700">{doc.document_number || "Đang cập nhật"}</p>
                              </div>
                           </div>
                           <div className="flex items-center gap-3">
                              <div className="w-10 h-10 bg-white rounded-xl flex items-center justify-center border border-slate-100 shadow-sm">
                                 <BookOpen className="w-5 h-5 text-slate-400" />
                              </div>
                              <div>
                                 <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Cơ quan ban hành</p>
                                 <p className="text-sm font-bold text-slate-700">{doc.issuing_body || "Quốc Hội / Chính Phủ"}</p>
                              </div>
                           </div>
                        </div>
                     </div>
                  </div>

                  {/* Document Body */}
                  <div className="p-8 md:p-12 lg:p-16">
                     <article className="prose prose-indigo max-w-none">
                        <div className="bg-slate-50/50 p-8 md:p-12 rounded-[2rem] border border-slate-100 shadow-inner">
                           {doc.content_html ? (
                             <div 
                               className="whitespace-pre-wrap font-sans text-base text-slate-800 leading-[1.8] tracking-normal doc-html-content"
                               dangerouslySetInnerHTML={{ __html: doc.content_html }}
                             />
                           ) : (
                             <pre className="whitespace-pre-wrap font-sans text-base text-slate-800 leading-[1.8] tracking-normal">
                                {doc.clean_text || "Nội dung đang được cập nhật..."}
                             </pre>
                           )}
                        </div>
                     </article>
                     
                     <div className="mt-12 pt-8 border-t border-slate-100 text-center">
                        <p className="text-xs text-slate-400 italic">
                           Dữ liệu được cung cấp bởi Hệ thống AI Pháp Luật. Thông tin chỉ mang tính chất tham khảo.
                        </p>
                     </div>
                  </div>
               </>
            )}
          </div>
        </div>
      </main>
    </div>
  </div>
  );
}
