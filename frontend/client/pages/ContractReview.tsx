import { useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { DocumentViewer } from "@/components/DocumentViewer";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Upload, ShieldAlert, FileText, CheckCircle2, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

interface RiskItem {
  risk_level: string;
  description: string;
  relevant_law: string;
  recommendation: string;
}

interface Citation {
  article: string;
  law_name: string;
  excerpt: string;
  document_id?: string;
}

interface ReviewedClause {
  title: string;
  content: string;
  analysis: string;
  risks: RiskItem[];
  citations: Citation[];
}

interface ReviewResult {
  summary: string;
  clauses: ReviewedClause[];
  overall_risks: RiskItem[];
  citations: Citation[];
}

export default function ContractReview() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [contractText, setContractText] = useState("");
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [viewingDocId, setViewingDocId] = useState<string | null>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (event) => {
      const text = event.target?.result as string;
      setContractText(text);
      await startReview(text);
    };
    reader.readAsText(file);
  };

  const startReview = async (text: string) => {
    setIsUploading(true);
    setResult(null);
    setErrorMsg(null);

    try {
      const response = await fetch("http://127.0.0.1:8000/review-contract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contract_text: text,
          contract_type: "Hợp đồng lao động",
        }),
      });

      if (!response.ok) {
        let errMsg = "Đã xảy ra lỗi khi rà soát.";
        try {
          const errData = await response.json();
          if (errData.detail) errMsg = errData.detail;
        } catch (e) {}
        throw new Error(errMsg);
      }

      const data = await response.json();
      setResult(data);
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.message || "Máy chủ không hoạt động hoặc có lỗi xử lý.");
    } finally {
      setIsUploading(false);
    }
  };

  // Handle citation click — open DocumentViewer overlay
  const handleCitationClick = (cite: Citation) => {
    if (cite.document_id) {
      setViewingDocId(cite.document_id);
    }
  };

  return (
    <div className="flex h-screen bg-[#F8FAFC] overflow-hidden">
      <Sidebar isOpen={sidebarOpen} />

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="bg-white border-b border-border px-8 py-4 flex items-center justify-between z-10 shadow-sm relative">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="md:hidden p-2 hover:bg-secondary rounded-lg transition-colors"
            >
              <Upload className="w-5 h-5" />
            </button>
            <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
              <ShieldAlert className="text-primary w-6 h-6" />
              Rà soát Hợp đồng AI
            </h1>
          </div>

          <div className="flex items-center gap-3">
            <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
              Chế độ Nâng cao
            </Badge>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-8">
          <div className="max-w-5xl mx-auto space-y-8">
            {/* Upload Area */}
            {!result && !isUploading && (
              <div className="flex flex-col items-center justify-center min-h-[400px] border-2 border-dashed border-slate-200 rounded-3xl bg-white p-12 text-center transition-all hover:border-primary/50 group">
                <div className="w-20 h-20 bg-primary/5 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                  <Upload className="w-10 h-10 text-primary" />
                </div>
                <h2 className="text-2xl font-bold text-slate-900 mb-2">Tải hợp đồng lên để rà soát</h2>
                <p className="text-slate-500 max-w-md mb-8">
                  Hỗ trợ định dạng PDF, DOCX hoặc Text. AI sẽ phân tích từng điều khoản và đối chiếu với luật hiện hành.
                </p>
                {errorMsg && (
                  <div className="w-full max-w-md mb-6 p-4 bg-red-50 border border-red-200 rounded-xl flex items-start gap-3">
                    <ShieldAlert className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                    <div className="text-left">
                      <p className="font-bold text-red-800 text-sm">Lỗi rà soát hợp đồng</p>
                      <p className="text-sm text-red-600 mt-1">{errorMsg}</p>
                    </div>
                  </div>
                )}
                <div className="flex gap-4">
                  <Button size="lg" className="rounded-xl px-8 h-12" asChild>
                    <label className="cursor-pointer">
                      Chọn tệp từ máy tính
                      <input type="file" className="hidden" onChange={handleFileUpload} accept=".txt,.md" />
                    </label>
                  </Button>
                  <Button variant="outline" size="lg" className="rounded-xl px-8 h-12">
                    Dán nội dung văn bản
                  </Button>
                </div>
              </div>
            )}

            {/* Loading State */}
            {isUploading && (
              <div className="flex flex-col items-center justify-center min-h-[400px] space-y-4">
                <div className="relative">
                  <Loader2 className="w-12 h-12 text-primary animate-spin" />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="w-2 h-2 bg-primary rounded-full animate-ping" />
                  </div>
                </div>
                <div className="text-center">
                  <h3 className="text-lg font-bold text-slate-900">AI đang rà soát hợp đồng...</h3>
                  <p className="text-slate-500 text-sm">Quá trình này có thể mất 15-30 giây tùy độ dài của hợp đồng.</p>
                </div>
              </div>
            )}

            {/* Results Display */}
            {result && (
              <div className="animate-in fade-in slide-in-from-bottom-4 duration-700 space-y-8 pb-12">
                {/* Overall Summary Card */}
                <Card className="p-8 border-none shadow-[0_8px_30px_rgb(0,0,0,0.04)] bg-gradient-to-br from-indigo-900 to-slate-900 text-white rounded-[2rem] overflow-hidden relative">
                  <div className="absolute top-0 right-0 p-8 opacity-10">
                    <ShieldAlert size={120} />
                  </div>
                  <div className="relative z-10">
                    <Badge className="bg-white/20 hover:bg-white/30 text-white border-none mb-4">Tổng quan kết quả</Badge>
                    <h2 className="text-3xl font-bold mb-4">Báo cáo Phân tích Rủi ro</h2>
                    <p className="text-indigo-100 text-lg leading-relaxed max-w-3xl">
                      {result.summary}
                    </p>
                  </div>
                </Card>

                {/* Overall Risks Grid */}
                {result.overall_risks.length > 0 && (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {result.overall_risks.slice(0, 3).map((risk, i) => (
                      <div
                        key={i}
                        className={cn(
                          "p-5 rounded-2xl border flex flex-col gap-2",
                          risk.risk_level === "Cao"
                            ? "bg-red-50 border-red-100 text-red-900"
                            : risk.risk_level === "Trung bình"
                            ? "bg-amber-50 border-amber-100 text-amber-900"
                            : "bg-green-50 border-green-100 text-green-900"
                        )}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold uppercase tracking-wider opacity-60">Rủi ro {i + 1}</span>
                          <Badge
                            className={cn(
                              "border-none",
                              risk.risk_level === "Cao"
                                ? "bg-red-200 text-red-700"
                                : risk.risk_level === "Trung bình"
                                ? "bg-amber-200 text-amber-700"
                                : "bg-green-200 text-green-700"
                            )}
                          >
                            {risk.risk_level}
                          </Badge>
                        </div>
                        <p className="font-semibold text-sm line-clamp-2">{risk.description}</p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Clauses Detail Analysis */}
                <div className="space-y-4">
                  <h3 className="text-xl font-bold text-slate-900 flex items-center gap-2 px-2">
                    <FileText className="w-5 h-5 text-indigo-500" />
                    Phân tích chi tiết từng điều khoản
                  </h3>

                  <div className="space-y-4">
                    {result.clauses.map((clause, idx) => (
                      <Card
                        key={idx}
                        className="border-none shadow-sm overflow-hidden rounded-2xl bg-white p-5 border border-slate-100"
                      >
                        <div className="flex flex-col gap-3">
                          <div className="flex items-start justify-between gap-4 border-b border-slate-50 pb-3">
                            <div>
                              <h4 className="font-bold text-slate-900 text-lg flex items-center gap-2">
                                <span className="flex-shrink-0 w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center text-sm">
                                  {idx + 1}
                                </span>
                                {clause.title}
                              </h4>
                            </div>
                            <div className="flex-shrink-0">
                              {clause.risks.length > 0 ? (
                                <Badge className="bg-red-100 text-red-700 hover:bg-red-200 border-none px-3 py-1 text-sm flex items-center gap-1">
                                  <ShieldAlert size={14} /> Có rủi ro / Vi phạm ({clause.risks.length})
                                </Badge>
                              ) : (
                                <Badge className="bg-green-100 text-green-700 hover:bg-green-200 border-none px-3 py-1 text-sm flex items-center gap-1">
                                  <CheckCircle2 size={14} /> Tuân thủ luật
                                </Badge>
                              )}
                            </div>
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-2">
                            <div className="space-y-2">
                              <h5 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Nội dung trích xuất</h5>
                              <p className="text-slate-600 text-sm leading-relaxed italic bg-slate-50 p-3 rounded-xl border border-slate-100">
                                "{clause.content}"
                              </p>
                            </div>

                            <div className="space-y-4">
                              <div className="space-y-2">
                                <h5 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Đánh giá hệ thống</h5>
                                <p className="text-slate-800 text-sm font-medium leading-relaxed">
                                  {clause.analysis}
                                </p>
                              </div>

                              {clause.risks.map((risk, ri) => (
                                <div key={ri} className="p-3 bg-red-50 border border-red-100 rounded-lg">
                                  <p className="text-sm text-red-800 font-bold mb-1">• {risk.description}</p>
                                  <p className="text-xs text-red-600 ml-3">
                                    <span className="font-semibold">Khuyến nghị:</span> {risk.recommendation}
                                  </p>
                                </div>
                              ))}

                              {/* Citations — limited to 3, clickable */}
                              <div className="space-y-2 pt-2 border-t border-slate-50">
                                <h5 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Nguồn luật căn cứ</h5>
                                {clause.citations.length > 0 ? (
                                  <div className="flex flex-wrap gap-2">
                                    {clause.citations.slice(0, 3).map((cite, ci) => (
                                      <Badge
                                        key={ci}
                                        variant="outline"
                                        className={cn(
                                          "bg-blue-50 text-blue-700 border-blue-200 text-xs",
                                          cite.document_id
                                            ? "cursor-pointer hover:bg-blue-100 hover:border-blue-300 hover:shadow-sm transition-all"
                                            : ""
                                        )}
                                        onClick={() => handleCitationClick(cite)}
                                      >
                                        {cite.article} - {cite.law_name}
                                      </Badge>
                                    ))}
                                  </div>
                                ) : (
                                  <p className="text-xs text-slate-500 italic">Không tìm thấy căn cứ cụ thể.</p>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      </Card>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Document Viewer Overlay */}
      <DocumentViewer
        documentId={viewingDocId}
        onClose={() => setViewingDocId(null)}
      />
    </div>
  );
}
