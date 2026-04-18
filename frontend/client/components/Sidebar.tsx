import { useState, useEffect, useCallback } from "react";
import { cn } from "@/lib/utils";
import { Plus, MessageCircle, ShieldAlert, BookOpen, HelpCircle, Trash2, Loader2 } from "lucide-react";
import { Button } from "./ui/button";
import { Link, useLocation, useNavigate } from "react-router-dom";

interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

interface SidebarProps {
  isOpen?: boolean;
  activeSessionId?: string | null;
  onSessionSelect?: (sessionId: string) => void;
}

export function Sidebar({ isOpen = true, activeSessionId, onSessionSelect }: SidebarProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [creatingSession, setCreatingSession] = useState(false);

  const navItems = [
    { label: "Văn bản Pháp Luật", icon: BookOpen, path: "/legislation", active: false },
    { label: "Rà soát hợp đồng", icon: ShieldAlert, path: "/review-contract", active: location.pathname === "/review-contract" },
  ];

  // Fetch real sessions from API
  const fetchSessions = useCallback(async () => {
    setLoadingSessions(true);
    try {
      const res = await fetch("http://127.0.0.1:8000/sessions");
      if (res.ok) {
        const data = await res.json();
        setSessions(data);
      }
    } catch (err) {
      console.error("Failed to load sessions:", err);
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  // Create new session
  const handleNewSession = async () => {
    setCreatingSession(true);
    try {
      const res = await fetch("http://127.0.0.1:8000/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "Cuộc hội thoại mới" }),
      });
      if (res.ok) {
        const session = await res.json();
        setSessions((prev) => [session, ...prev]);
        navigate(`/chat/${session.id}`);
        onSessionSelect?.(session.id);
      }
    } catch (err) {
      console.error("Failed to create session:", err);
    } finally {
      setCreatingSession(false);
    }
  };

  // Delete session
  const handleDeleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    e.preventDefault();
    try {
      const res = await fetch(`http://127.0.0.1:8000/sessions/${sessionId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setSessions((prev) => prev.filter((s) => s.id !== sessionId));
        if (activeSessionId === sessionId) {
          navigate("/");
        }
      }
    } catch (err) {
      console.error("Failed to delete session:", err);
    }
  };

  return (
    <div
      className={cn(
        "fixed left-0 top-0 h-screen w-72 bg-white border-r border-slate-100 flex flex-col transition-all duration-300 z-50 md:relative md:translate-x-0 md:z-auto",
        isOpen ? "translate-x-0" : "-translate-x-full"
      )}
    >
      {/* Header */}
      <div className="p-6">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 bg-indigo-600 rounded-2xl flex items-center justify-center flex-shrink-0 shadow-lg shadow-indigo-200">
            <span className="text-white text-xl font-bold">L</span>
          </div>
          <div>
            <span className="block text-base font-black text-slate-900 tracking-tight leading-none">TRA CỨU</span>
            <span className="block text-base font-black text-indigo-600 tracking-tight leading-none">LUẬT</span>
          </div>
        </div>

        <Button
          className="w-full bg-slate-50 hover:bg-slate-100 text-slate-700 border border-slate-100 gap-2 rounded-xl h-11 justify-start px-4 transition-all"
          variant="outline"
          onClick={handleNewSession}
          disabled={creatingSession}
        >
          {creatingSession ? (
            <Loader2 size={18} className="text-slate-400 animate-spin" />
          ) : (
            <Plus size={18} className="text-slate-400" />
          )}
          <span className="font-semibold">Cuộc trò chuyện mới</span>
        </Button>
      </div>

      {/* Navigation section */}
      <div className="px-4 mb-4">
        <div className="space-y-1">
          {navItems.map((item, idx) => (
            <Link
              key={idx}
              to={item.path}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-all group",
                item.active
                  ? "bg-indigo-50 text-indigo-700 shadow-sm"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              )}
            >
              <item.icon
                size={20}
                className={cn(
                  "flex-shrink-0 transition-colors",
                  item.active ? "text-indigo-600" : "text-slate-400 group-hover:text-slate-600"
                )}
              />
              <span>{item.label}</span>
              {item.active && <div className="ml-auto w-1.5 h-1.5 rounded-full bg-indigo-600" />}
            </Link>
          ))}
        </div>
      </div>

      <div className="w-full px-6 py-2">
        <div className="h-px bg-slate-50 w-full" />
      </div>

      {/* Main Content (History) */}
      <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
        <div className="mb-8">
          <div className="px-3 mb-4 flex items-center justify-between">
            <p className="text-[11px] font-black text-slate-400 uppercase tracking-[0.1em]">
              Lịch sử trò chuyện
            </p>
            {loadingSessions && <Loader2 size={12} className="text-slate-300 animate-spin" />}
          </div>

          <div className="space-y-1">
            {sessions.length === 0 && !loadingSessions && (
              <p className="px-3 text-xs text-slate-400 italic">Chưa có cuộc hội thoại nào.</p>
            )}
            {sessions.map((session) => (
              <Link
                key={session.id}
                to={`/chat/${session.id}`}
                onClick={() => onSessionSelect?.(session.id)}
                className={cn(
                  "w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm transition-all truncate group",
                  activeSessionId === session.id
                    ? "bg-indigo-50 text-indigo-700 font-semibold"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                )}
              >
                <MessageCircle
                  size={16}
                  className={cn(
                    "flex-shrink-0",
                    activeSessionId === session.id
                      ? "text-indigo-400"
                      : "text-slate-300 group-hover:text-indigo-400"
                  )}
                />
                <span className="truncate flex-1">{session.title}</span>
                <button
                  onClick={(e) => handleDeleteSession(e, session.id)}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-50 rounded-lg transition-all flex-shrink-0"
                >
                  <Trash2 size={14} className="text-slate-400 hover:text-red-500" />
                </button>
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="p-4 space-y-2">
        <button className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-slate-50 transition-all border border-transparent hover:border-slate-100 group">
          <HelpCircle size={20} className="text-slate-400 group-hover:text-amber-500" />
          <span className="text-sm font-semibold text-slate-600">Hỗ trợ & Hướng dẫn</span>
        </button>
        <div className="p-4 bg-slate-900 rounded-[1.5rem] relative overflow-hidden group cursor-pointer hover:shadow-lg transition-all duration-500">
          <div className="absolute top-0 right-0 p-2 opacity-20 transition-transform group-hover:rotate-12">
            <ShieldAlert size={40} className="text-blue-400" />
          </div>
          <p className="text-[10px] font-bold text-blue-400 uppercase tracking-widest mb-1 relative z-10">Gói Premium</p>
          <p className="text-xs text-white font-bold relative z-10">Mở khóa trí tuệ đầy đủ</p>
          <p className="text-[10px] text-slate-400 mt-2 hover:text-white transition-colors">Nâng cấp ngay →</p>
        </div>
      </div>
    </div>
  );
}
