import { Heart, Send } from "lucide-react";
import { useRef, useState } from "react";

interface ChatInputProps {
  onSend?: (message: string) => void;
}

export function ChatInput({ onSend }: ChatInputProps) {
  const [message, setMessage] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSend = () => {
    if (message.trim()) {
      onSend?.(message);
      setMessage("");
      inputRef.current?.focus();
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="bg-white p-4">
      <div className="flex items-center gap-3 bg-secondary rounded-lg px-4 py-3 border border-border/50">
        <button className="text-primary hover:text-primary/80 transition-colors flex-shrink-0">
          <Heart size={20} className="fill-current" />
        </button>

        <input
          ref={inputRef}
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Bạn cần tư vấn vấn đề pháp lý gì?"
          className="flex-1 bg-transparent outline-none text-sm text-foreground placeholder-muted-foreground"
        />

        <button
          onClick={handleSend}
          className="text-primary hover:text-primary/80 transition-colors p-1 flex-shrink-0"
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  );
}
