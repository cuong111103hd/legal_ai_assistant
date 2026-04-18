import { useState, useEffect } from "react";
import { Sidebar } from "@/components/Sidebar";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { 
  Search, 
  BookOpen, 
  FileText, 
  ChevronRight, 
  ChevronLeft,
  Hash, 
  Shield, 
  Loader2,
  Filter
} from "lucide-react";
import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";

interface LegalDoc {
  id: string;
  title: string;
  doc_type: string;
  document_number: string;
  validity_status: string;
  created_at: string;
}

export default function Legislation() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [docs, setDocs] = useState<LegalDoc[]>([]);
  const [loading, setLoading] = useState(false);
  
  // Pagination & Filtering State
  const [currentPage, setCurrentPage] = useState(1);
  const [totalDocs, setTotalDocs] = useState(0);
  const [pageSize] = useState(20);
  const [selectedType, setSelectedType] = useState("Tất cả");
  const [availableTypes, setAvailableTypes] = useState<string[]>([]);

  const fetchTypes = async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/legal-documents/types");
      if (res.ok) {
        const data = await res.json();
        setAvailableTypes(["Tất cả", ...data]);
      }
    } catch (err) {
      console.error("Failed to fetch doc types:", err);
    }
  };

  const fetchDocs = async (page: number = 1, query: string = searchQuery, type: string = selectedType) => {
    setLoading(true);
    try {
      let url = `http://127.0.0.1:8000/legal-documents?page=${page}&limit=${pageSize}`;
      if (query) url += `&q=${encodeURIComponent(query)}`;
      if (type && type !== "Tất cả") url += `&doc_type=${encodeURIComponent(type)}`;
      
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setDocs(data.items);
        setTotalDocs(data.total);
      }
    } catch (err) {
      console.error("Failed to fetch legal documents:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTypes();
    fetchDocs(1, searchQuery, selectedType);
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentPage(1);
    fetchDocs(1, searchQuery, selectedType);
  };

  const handleTypeChange = (type: string) => {
    setSelectedType(type);
    setCurrentPage(1);
    fetchDocs(1, searchQuery, type);
  };

  const handlePageChange = (newPage: number) => {
    setCurrentPage(newPage);
    fetchDocs(newPage, searchQuery, selectedType);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const totalPages = Math.ceil(totalDocs / pageSize);

  return (
    <div className="flex h-screen bg-[#F8FAFC] overflow-hidden">
      <Sidebar isOpen={sidebarOpen} />

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="bg-white border-b border-border px-8 py-4 flex items-center justify-between z-10 shadow-sm relative">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
              <BookOpen className="text-primary w-6 h-6" />
              Thư viện Văn bản Pháp luật
            </h1>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 md:p-8">
          <div className="max-w-5xl mx-auto space-y-8">
            
            {/* Search & Filter Section */}
            <div className="bg-white p-6 rounded-[2rem] border border-slate-100 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold text-slate-900">Tìm kiếm văn bản</h2>
                <div className="flex items-center gap-2 text-slate-500 text-sm">
                   <Filter className="w-4 h-4" />
                   <span>Lọc theo loại:</span>
                   <select 
                     className="bg-slate-50 border-none rounded-lg text-sm font-semibold focus:ring-0 cursor-pointer text-indigo-600"
                     value={selectedType}
                     onChange={(e) => handleTypeChange(e.target.value)}
                   >
                     {availableTypes.map(t => (
                       <option key={t} value={t}>{t}</option>
                     ))}
                   </select>
                </div>
              </div>
              <form onSubmit={handleSearch} className="flex gap-3">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
                  <Input 
                    placeholder="Nhập tên văn bản, số hiệu hoặc từ khóa..." 
                    className="pl-10 h-12 rounded-xl border-slate-200 focus:ring-indigo-500"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
                <Button type="submit" size="lg" className="rounded-xl px-8 h-12 bg-indigo-600 hover:bg-indigo-700">
                   Tìm kiếm
                </Button>
              </form>
            </div>

            {/* List Section */}
            <div className="space-y-4">
               <div className="flex items-center justify-between px-2">
                  <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest">
                    {searchQuery ? `Kết quả tìm kiếm cho "${searchQuery}"` : "Danh sách văn bản"}
                  </h3>
                  <span className="text-xs text-slate-400 font-medium">{totalDocs} văn bản</span>
               </div>

               {loading ? (
                 <div className="flex flex-col items-center justify-center py-20 gap-4">
                    <Loader2 className="w-10 h-10 text-indigo-500 animate-spin" />
                    <p className="text-slate-500 text-sm animate-pulse">Đang tải danh sách văn bản...</p>
                 </div>
               ) : (
                 <div className="grid grid-cols-1 gap-3">
                   {docs.length === 0 ? (
                     <div className="text-center py-20 bg-white rounded-3xl border border-dashed border-slate-200">
                        <FileText className="w-12 h-12 text-slate-300 mx-auto mb-4" />
                        <p className="text-slate-500">Không tìm thấy văn bản nào phù hợp.</p>
                     </div>
                   ) : (
                     docs.map((doc) => (
                       <Link key={doc.id} to={`/legislation/${doc.id}`}>
                         <Card className="p-4 hover:shadow-md transition-all border-slate-100 group cursor-pointer rounded-2xl">
                           <div className="flex items-start gap-4">
                              <div className="w-12 h-12 bg-slate-50 rounded-xl flex items-center justify-center flex-shrink-0 group-hover:bg-indigo-50 transition-colors">
                                 <FileText className="w-6 h-6 text-slate-400 group-hover:text-indigo-500" />
                              </div>
                              <div className="flex-1 min-w-0 space-y-2">
                                 <h4 className="font-bold text-slate-900 group-hover:text-indigo-600 transition-colors line-clamp-2">
                                    {doc.title}
                                 </h4>
                                 <div className="flex flex-wrap gap-2">
                                    {doc.doc_type && (
                                       <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200 text-[10px] gap-1 px-2 py-0">
                                          {doc.doc_type}
                                       </Badge>
                                    )}
                                    {doc.document_number && (
                                       <Badge variant="outline" className="bg-slate-50 text-slate-600 border-slate-200 text-[10px] gap-1 px-2 py-0">
                                          <Hash className="w-3 h-3" />
                                          {doc.document_number}
                                       </Badge>
                                    )}
                                    <Badge 
                                       variant="outline" 
                                       className={cn(
                                          "text-[10px] gap-1 px-2 py-0",
                                          doc.validity_status?.includes("Còn hiệu lực") 
                                             ? "bg-green-50 text-green-700 border-green-200" 
                                             : "bg-amber-50 text-amber-700 border-amber-200"
                                       )}
                                    >
                                       <Shield className="w-3 h-3" />
                                       {doc.validity_status || "Không xác định"}
                                    </Badge>
                                 </div>
                              </div>
                              <div className="flex-shrink-0 self-center">
                                 <ChevronRight className="w-5 h-5 text-slate-300 group-hover:text-indigo-400 group-hover:translate-x-1 transition-all" />
                              </div>
                           </div>
                         </Card>
                       </Link>
                     ))
                   )}
                 </div>
               )}

               {/* Pagination Controls */}
               {!loading && totalDocs > pageSize && (
                 <div className="flex items-center justify-center gap-2 py-8">
                    <Button 
                      variant="outline" 
                      size="sm" 
                      className="rounded-lg h-9 w-9 p-0"
                      onClick={() => handlePageChange(currentPage - 1)}
                      disabled={currentPage === 1}
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </Button>
                    
                    <div className="flex items-center gap-1">
                      {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                        // Logic to show a window of pages around current page
                        let pageNum = currentPage;
                        if (currentPage <= 3) {
                          pageNum = i + 1;
                        } else if (currentPage > totalPages - 2) {
                          pageNum = totalPages - 4 + i;
                        } else {
                          pageNum = currentPage - 2 + i;
                        }
                        
                        if (pageNum < 1 || pageNum > totalPages) return null;

                        return (
                          <Button 
                            key={pageNum}
                            variant={currentPage === pageNum ? "default" : "outline"}
                            size="sm"
                            className={cn(
                              "h-9 w-9 p-0 rounded-lg",
                              currentPage === pageNum ? "bg-indigo-600" : ""
                            )}
                            onClick={() => handlePageChange(pageNum)}
                          >
                            {pageNum}
                          </Button>
                        );
                      })}
                    </div>

                    <Button 
                      variant="outline" 
                      size="sm" 
                      className="rounded-lg h-9 w-9 p-0"
                      onClick={() => handlePageChange(currentPage + 1)}
                      disabled={currentPage === totalPages}
                    >
                      <ChevronRight className="w-4 h-4" />
                    </Button>
                    
                    <span className="text-xs text-slate-400 ml-2 font-medium">
                      Trang {currentPage} / {totalPages}
                    </span>
                 </div>
               )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
