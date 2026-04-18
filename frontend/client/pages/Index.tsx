import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { Sidebar } from "@/components/Sidebar";
import { ChatMessage } from "@/components/ChatMessage";
import { ChatInput } from "@/components/ChatInput";
import { ContractReviewBanner } from "@/components/ContractReviewBanner";
import { DocumentViewer } from "@/components/DocumentViewer";
import { BookOpen, Scale, FileText, ChevronRight } from "lucide-react";

interface Citation {
  article: string;
  clause?: string;
  law_name: string;
  document_number?: string;
  document_id?: string;
  excerpt?: string;
}

interface Message {
  id: string;
  role: "user" | "ai";
  content: string;
  citations?: Citation[];
  isStreaming?: boolean;
}

export default function Index() {
  const { sessionId } = useParams<{ sessionId?: string }>();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(sessionId || null);
  const [viewingDocId, setViewingDocId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      role: "ai",
      content: "Xin chào! Tôi là Trợ lý AI Pháp Luật. Tôi có thể giúp bạn giải đáp các vấn đề liên quan đến pháp luật Việt Nam. Bạn có câu hỏi nào không?",
    },
  ]);

  // Sync sessionId from URL param
  useEffect(() => {
    if (sessionId) {
      setActiveSessionId(sessionId);
    }
  }, [sessionId]);

  // Load chat history when session changes
  useEffect(() => {
    if (!activeSessionId) return;

    const loadHistory = async () => {
      try {
        const res = await fetch(`http://127.0.0.1:8000/sessions/${activeSessionId}/messages?limit=50`);
        if (res.ok) {
          const data = await res.json();
          if (data.length > 0) {
            const loadedMsgs: Message[] = data.map((msg: any) => ({
              id: msg.id?.toString() || Date.now().toString(),
              role: msg.role === "human" ? "user" : "ai",
              content: msg.content,
              citations: msg.citations || [],
            }));
            setMessages(loadedMsgs);
          } else {
            // New session with no messages
            setMessages([
              {
                id: "1",
                role: "ai",
                content: "Xin chào! Tôi là Trợ lý AI Pháp Luật. Bạn có câu hỏi gì không?",
              },
            ]);
          }
        }
      } catch (err) {
        console.error("Failed to load session messages:", err);
      }
    };

    loadHistory();
  }, [activeSessionId]);

  const handleSendMessage = async (text: string) => {
    // Add user message
    const userMsg: Message = { id: Date.now().toString(), role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);

    // Create placeholder AI message
    const aiMsgId = (Date.now() + 1).toString();
    const aiMsg: Message = { id: aiMsgId, role: "ai", content: "", isStreaming: true };
    setMessages((prev) => [...prev, aiMsg]);

    try {
      const response = await fetch("http://127.0.0.1:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: text,
          top_k: 10,
          session_id: activeSessionId || undefined,
        }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let streamBuffer = "";

      if (reader) {
        let isDone = false;
        while (!isDone) {
          const { value, done } = await reader.read();
          if (done) {
            isDone = true;
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === aiMsgId ? { ...msg, isStreaming: false } : msg
              )
            );
            break;
          }

          streamBuffer += decoder.decode(value, { stream: true });

          const parts = streamBuffer.split(/\r?\n\r?\n/);
          streamBuffer = parts.pop() || "";

          for (const part of parts) {
            const lines = part.split(/\r?\n/);
            let eventType = "message";
            let data = "";
            for (const line of lines) {
              if (line.startsWith("event: ")) eventType = line.substring(7).trim();
              if (line.startsWith("data: ")) {
                data += data ? "\n" + line.substring(6) : line.substring(6);
              }
            }

            if (eventType === "token") {
              const parsedToken = data.replace(/\\n/g, '\n');
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === aiMsgId ? { ...msg, content: msg.content + parsedToken } : msg
                )
              );
            } else if (eventType === "done") {
              try {
                const parsedData = JSON.parse(data);
                const citations = parsedData.answer?.citations || [];
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === aiMsgId ? { ...msg, citations: citations, isStreaming: false } : msg
                  )
                );
              } catch (e) {
                console.error("Failed to parse done event JSON", e);
              }
            } else if (eventType === "error") {
              console.error("Stream error event:", data);
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === aiMsgId ? { ...msg, content: msg.content + "\n\n[Lỗi kết nối hoặc xử lý]", isStreaming: false } : msg
                )
              );
            }
          }
        }
      }
    } catch (err) {
      console.error("Chat Error:", err);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === aiMsgId ? { ...msg, content: msg.content + "\n\n[Có lỗi xảy ra khi kết nối máy chủ]", isStreaming: false } : msg
        )
      );
    }
  };

  const handleCitationClick = (docId: string) => {
    setViewingDocId(docId);
  };

  return (
    <div className="flex h-screen bg-secondary overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        isOpen={sidebarOpen}
        activeSessionId={activeSessionId}
        onSessionSelect={(id) => setActiveSessionId(id)}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="bg-white border-b border-border px-4 md:px-6 py-4 flex items-center gap-4 flex-shrink-0 z-10 shadow-sm relative">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="md:hidden p-2 hover:bg-secondary rounded-lg transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-semibold text-foreground truncate">AI Pháp Luật</h1>
            <p className="text-xs text-muted-foreground truncate">
              Trợ lý giải đáp, phân tích rủi ro và tra cứu pháp luật Việt Nam
            </p>
          </div>

          <button className="p-2 hover:bg-secondary rounded-lg transition-colors flex-shrink-0">
            <svg className="w-5 h-5 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
          </button>
        </div>

        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto p-4 md:p-8 flex flex-col scroll-smooth bg-slate-50/50">
          <div className="max-w-5xl mx-auto w-full space-y-8 mb-auto">
            {messages.length <= 1 && !activeSessionId ? (
              <div className="py-8 space-y-12 animate-in fade-in slide-in-from-bottom-4 duration-1000">
                {/* Dashboard Header */}
                <div className="text-center space-y-4">
                  <div className="inline-flex items-center gap-2 px-3 py-1 bg-indigo-50 rounded-full border border-indigo-100 mb-2">
                    <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
                    <span className="text-[10px] font-bold text-indigo-600 uppercase tracking-widest">Hệ thống AI Pháp Luật v2.0</span>
                  </div>
                  <h1 className="text-4xl md:text-6xl font-black text-slate-900 tracking-tight">
                    Bạn cần trợ giúp <br />
                    <span className="text-indigo-600">pháp lý gì hôm nay?</span>
                  </h1>
                  <p className="text-slate-500 max-w-2xl mx-auto text-lg">
                    Tra cứu văn bản, phân tích rủi ro hợp đồng và giải đáp mọi thắc mắc pháp luật Việt Nam với dữ liệu cập nhật mới nhất.
                  </p>
                </div>

                {/* Banners */}
                <div className="grid grid-cols-1 gap-6">
                  <ContractReviewBanner />
                </div>

                {/* Quick Actions */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="p-6 bg-white rounded-[2rem] border border-slate-100 shadow-sm hover:shadow-md transition-all group cursor-pointer">
                    <div className="w-12 h-12 bg-blue-50 rounded-2xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                      <BookOpen className="text-blue-600 w-6 h-6" />
                    </div>
                    <h3 className="font-bold text-slate-900 mb-2">Tra cứu Văn bản</h3>
                    <p className="text-sm text-slate-500 mb-4">Tìm kiếm hơn 350.000 văn bản quy phạm pháp luật mới nhất.</p>
                    <div className="flex items-center text-blue-600 text-xs font-bold group-hover:gap-2 transition-all">
                      KHÁM PHÁ <ChevronRight size={14} />
                    </div>
                  </div>

                  <div className="p-6 bg-white rounded-[2rem] border border-slate-100 shadow-sm hover:shadow-md transition-all group cursor-pointer">
                    <div className="w-12 h-12 bg-amber-50 rounded-2xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                      <Scale className="text-amber-600 w-6 h-6" />
                    </div>
                    <h3 className="font-bold text-slate-900 mb-2">Thủ tục Hành chính</h3>
                    <p className="text-sm text-slate-500 mb-4">Hướng dẫn chi tiết quy trình thực hiện các thủ tục tại cơ quan nhà nước.</p>
                    <div className="flex items-center text-amber-600 text-xs font-bold group-hover:gap-2 transition-all">
                      TÌM HIỂU <ChevronRight size={14} />
                    </div>
                  </div>

                  <div className="p-6 bg-white rounded-[2rem] border border-slate-100 shadow-sm hover:shadow-md transition-all group cursor-pointer">
                    <div className="w-12 h-12 bg-emerald-50 rounded-2xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                      <FileText className="text-emerald-600 w-6 h-6" />
                    </div>
                    <h3 className="font-bold text-slate-900 mb-2">Biểu mẫu chuẩn</h3>
                    <p className="text-sm text-slate-500 mb-4">Thư viện hàng nghìn mẫu hợp đơn, đơn từ được luật sư biên soạn.</p>
                    <div className="flex items-center text-emerald-600 text-xs font-bold group-hover:gap-2 transition-all">
                      TẢI VỀ <ChevronRight size={14} />
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              messages.map((msg) => (
                <ChatMessage
                  key={msg.id}
                  role={msg.role}
                  content={msg.content}
                  citations={msg.citations}
                  isStreaming={msg.isStreaming}
                  onCitationClick={handleCitationClick}
                />
              ))
            )}
          </div>
        </div>

        {/* Chat Input */}
        <div className="bg-white border-t border-border p-4 md:p-6 flex-shrink-0">
          <div className="max-w-4xl mx-auto w-full">
            <ChatInput onSend={handleSendMessage} />
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
