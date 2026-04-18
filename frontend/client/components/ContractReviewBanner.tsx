import { ShieldCheck, ArrowRight } from "lucide-react";
import { Button } from "./ui/button";
import { Link } from "react-router-dom";

export function ContractReviewBanner() {
  return (
    <div className="relative overflow-hidden rounded-[2.5rem] bg-gradient-to-r from-blue-600 to-indigo-700 p-8 md:p-12 text-white shadow-xl group">
      {/* Background patterns */}
      <div className="absolute top-0 right-0 -mr-20 -mt-20 w-96 h-96 bg-white/10 rounded-full blur-3xl transition-transform group-hover:scale-110 duration-700" />
      <div className="absolute bottom-0 left-0 -ml-20 -mb-20 w-64 h-64 bg-indigo-500/20 rounded-full blur-2xl" />
      
      <div className="relative z-10 flex flex-col md:flex-row items-center gap-8">
        <div className="flex-1 space-y-4">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/20 backdrop-blur-md border border-white/10 text-xs font-bold uppercase tracking-wider">
             <ShieldCheck size={14} className="text-blue-200" />
             Tính năng mới
          </div>
          <h2 className="text-3xl md:text-5xl font-extrabold leading-tight">
            Rà soát Hợp đồng <br/>
            <span className="text-blue-200">Thông minh với AI</span>
          </h2>
          <p className="text-blue-100/80 text-lg max-w-xl leading-relaxed">
            Phát hiện rủi ro, đối chiếu pháp luật và nhận khuyến nghị chỉnh sửa chuyên sâu cho mọi loại hợp đồng chỉ trong vài giây.
          </p>
          <div className="pt-4">
            <Button size="lg" className="bg-white text-blue-700 hover:bg-white/90 rounded-2xl px-8 h-14 font-bold text-lg shadow-lg group/btn" asChild>
               <Link to="/review-contract">
                Bắt đầu rà soát
                <ArrowRight className="ml-2 w-5 h-5 transition-transform group-hover/btn:translate-x-1" />
               </Link>
            </Button>
          </div>
        </div>
        
        <div className="hidden md:flex flex-shrink-0 animate-in fade-in zoom-in duration-1000">
           <div className="relative">
              <div className="absolute inset-0 bg-blue-400 blur-3xl opacity-20 animate-pulse" />
              <div className="bg-white/10 backdrop-blur-xl border border-white/20 p-6 rounded-3xl shadow-2xl skew-y-3 -rotate-6">
                 <div className="w-64 space-y-3">
                    <div className="h-2 w-20 bg-blue-300/40 rounded" />
                    <div className="h-4 w-full bg-blue-300/20 rounded-lg" />
                    <div className="h-4 w-4/5 bg-blue-300/20 rounded-lg" />
                    <div className="h-20 w-full bg-red-400/20 rounded-xl border border-red-400/30 p-3">
                       <div className="h-2 w-10 bg-red-400/40 rounded mb-2" />
                       <div className="h-2 w-full bg-red-400/30 rounded" />
                       <div className="h-2 w-3/4 bg-red-400/30 rounded mt-1" />
                    </div>
                 </div>
              </div>
           </div>
        </div>
      </div>
    </div>
  );
}
