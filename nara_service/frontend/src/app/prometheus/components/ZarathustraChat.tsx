"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Bot, X, Send } from "lucide-react";
import { cn } from "@/lib/utils";

interface Message {
  id: string;
  role: "user" | "bot";
  text: string;
}

export function ZarathustraChat() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    { id: "1", role: "bot", text: "나는 자라투스트라다. 무엇을 알고 싶은가?" }
  ]);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isOpen]);

  const handleSend = () => {
    if (!input.trim()) return;
    
    const userMsg: Message = { id: Date.now().toString(), role: "user", text: input };
    setMessages(prev => [...prev, userMsg]);
    setInput("");

    setTimeout(() => {
      const botMsg: Message = { 
        id: (Date.now() + 1).toString(), 
        role: "bot", 
        text: "신은 죽었다. 하지만 너의 질문은 살아있구나. (아직은 더미 응답입니다)" 
      };
      setMessages(prev => [...prev, botMsg]);
    }, 1000);
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
      {isOpen && (
        <Card className="w-[350px] h-[500px] mb-4 shadow-2xl border-primary/20 animate-in fade-in slide-in-from-bottom-10 flex flex-col bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
          <CardHeader className="p-4 border-b flex flex-row items-center justify-between space-y-0 bg-primary/5">
            <div className="flex items-center gap-2">
              <Bot className="h-5 w-5 text-primary" />
              <CardTitle className="text-sm font-bold">Zarathustra</CardTitle>
            </div>
            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setIsOpen(false)}>
              <X className="h-4 w-4" />
            </Button>
          </CardHeader>
          <CardContent className="p-0 flex-1 overflow-hidden">
            <ScrollArea className="h-full p-4">
              <div className="flex flex-col gap-4">
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={cn(
                      "flex w-max max-w-[80%] flex-col gap-2 rounded-lg px-3 py-2 text-sm",
                      msg.role === "user"
                        ? "ml-auto bg-primary text-primary-foreground"
                        : "bg-muted"
                    )}
                  >
                    {msg.text}
                  </div>
                ))}
                <div ref={scrollRef} />
              </div>
            </ScrollArea>
          </CardContent>
          <CardFooter className="p-3 border-t">
            <form
              className="flex w-full items-center gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
            >
              <Input
                placeholder="Message Zarathustra..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                className="flex-1 h-9"
              />
              <Button type="submit" size="icon" className="h-9 w-9" disabled={!input.trim()}>
                <Send className="h-4 w-4" />
              </Button>
            </form>
          </CardFooter>
        </Card>
      )}

      <Button
        size="lg"
        className={cn(
          "h-14 w-14 rounded-full shadow-lg transition-all duration-300 hover:scale-110",
          isOpen ? "bg-muted text-muted-foreground hover:bg-muted" : "bg-primary text-primary-foreground"
        )}
        onClick={() => setIsOpen(!isOpen)}
      >
        {isOpen ? <X className="h-6 w-6" /> : <ZarathustraIcon className="h-8 w-8" />}
      </Button>
    </div>
  );
}

function ZarathustraIcon({ className }: { className?: string }) {
  return (
    <svg 
      viewBox="0 0 100 100" 
      xmlns="http://www.w3.org/2000/svg" 
      className={className}
    >
      <g transform="translate(30, 30)">
        <circle cx="0" cy="0" r="14" fill="#FFE082" stroke="#333333" strokeWidth="1.5" />
        <g stroke="#333333" strokeWidth="1.5">
          <line x1="0" y1="-22" x2="0" y2="-18" />
          <line x1="15.5" y1="-15.5" x2="12.7" y2="-12.7" />
          <line x1="22" y1="0" x2="18" y2="0" />
          <line x1="15.5" y1="15.5" x2="12.7" y2="12.7" />
          <line x1="-15.5" y1="15.5" x2="-12.7" y2="12.7" />
          <line x1="-22" y1="0" x2="-18" y2="0" />
          <line x1="-15.5" y1="-15.5" x2="-12.7" y2="-12.7" />
        </g>
      </g>
      <path 
        d="M 25 90 Q 25 80 35 75 L 35 60 Q 30 60 30 50 L 30 40 Q 30 25 50 25 Q 70 25 70 40 L 70 50 Q 70 60 65 60 L 65 75 Q 75 80 75 90" 
        fill="#FFFFFF" 
        stroke="#333333" 
        strokeWidth="2" 
        strokeLinecap="round" 
        strokeLinejoin="round" 
      />
      <path 
        d="M 30 40 Q 50 30 70 40" 
        fill="none" 
        stroke="#333333" 
        strokeWidth="2" 
        strokeLinecap="round" 
        strokeLinejoin="round" 
      />
      <path 
        d="M 42 45 L 42 55 L 50 55" 
        fill="none" 
        stroke="#333333" 
        strokeWidth="2" 
        strokeLinecap="round" 
        strokeLinejoin="round" 
      />
      <path 
        d="M 35 60 Q 50 75 65 60" 
        fill="none" 
        stroke="#333333" 
        strokeWidth="2" 
        strokeLinecap="round" 
        strokeLinejoin="round" 
      />
      <path 
        d="M 35 75 L 25 90 M 65 75 L 75 90" 
        fill="none" 
        stroke="#333333" 
        strokeWidth="2" 
        strokeLinecap="round" 
        strokeLinejoin="round" 
      />
    </svg>
  );
}