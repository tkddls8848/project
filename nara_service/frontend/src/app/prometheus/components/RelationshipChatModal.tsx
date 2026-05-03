'use client';

/**
 * Relationship Chat Modal - Google NotebookLM Style
 * Chat with LLM based on multiple documents (N documents support).
 */

import React, { useState, useRef, useEffect } from 'react';
import { FileText, Send, Loader2, Sparkles, X } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import type { GraphNodeData } from '../types';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface RelationshipChatModalProps {
  selectedNodes: GraphNodeData[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const DOCUMENT_COLORS = [
  { bg: 'bg-blue-50 dark:bg-blue-950/30', border: 'border-blue-200 dark:border-blue-800', icon: 'text-blue-600 dark:text-blue-400', title: 'text-blue-900 dark:text-blue-100', label: 'text-blue-700 dark:text-blue-400' },
  { bg: 'bg-green-50 dark:bg-green-950/30', border: 'border-green-200 dark:border-green-800', icon: 'text-green-600 dark:text-green-400', title: 'text-green-900 dark:text-green-100', label: 'text-green-700 dark:text-green-400' },
  { bg: 'bg-purple-50 dark:bg-purple-950/30', border: 'border-purple-200 dark:border-purple-800', icon: 'text-purple-600 dark:text-purple-400', title: 'text-purple-900 dark:text-purple-100', label: 'text-purple-700 dark:text-purple-400' },
  { bg: 'bg-orange-50 dark:bg-orange-950/30', border: 'border-orange-200 dark:border-orange-800', icon: 'text-orange-600 dark:text-orange-400', title: 'text-orange-900 dark:text-orange-100', label: 'text-orange-700 dark:text-orange-400' },
  { bg: 'bg-pink-50 dark:bg-pink-950/30', border: 'border-pink-200 dark:border-pink-800', icon: 'text-pink-600 dark:text-pink-400', title: 'text-pink-900 dark:text-pink-100', label: 'text-pink-700 dark:text-pink-400' },
  { bg: 'bg-indigo-50 dark:bg-indigo-950/30', border: 'border-indigo-200 dark:border-indigo-800', icon: 'text-indigo-600 dark:text-indigo-400', title: 'text-indigo-900 dark:text-indigo-100', label: 'text-indigo-700 dark:text-indigo-400' },
];

export const RelationshipChatModal: React.FC<RelationshipChatModalProps> = ({
  selectedNodes,
  open,
  onOpenChange,
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Add initial welcome message when modal opens
  useEffect(() => {
    if (open && selectedNodes.length >= 2 && messages.length === 0) {
      const docList = selectedNodes.map((node, idx) => `• ${node.label}`).join('\n');
      const welcomeMessage: Message = {
        id: 'welcome',
        role: 'assistant',
        content: `안녕하세요! ${selectedNodes.length}개 문서 간의 관계와 인사이트를 탐색할 준비가 되었습니다.\n\n**선택된 문서:**\n${docList}\n\n이 문서들에 대해 무엇이든 물어보세요. 관계, 공통점, 차이점, 연관성, 통합 활용 방안 등을 분석해드리겠습니다.`,
        timestamp: new Date(),
      };
      setMessages([welcomeMessage]);
    }
  }, [open, selectedNodes, messages.length]);

  // Scroll to bottom on new message
  useEffect(() => {
    if (scrollRef.current) {
      setTimeout(() => {
        if (scrollRef.current) {
            const scrollContainer = scrollRef.current.querySelector('[data-radix-scroll-area-viewport]');
            if (scrollContainer) {
                scrollContainer.scrollTop = scrollContainer.scrollHeight;
            }
        }
      }, 100);
    }
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || selectedNodes.length < 2) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    const currentQuery = input;
    setInput('');
    setIsLoading(true);

    try {
      const chatHistory = messages
        .filter((msg) => msg.id !== 'welcome')
        .map((msg) => ({
          role: msg.role,
          content: msg.content,
        }));

      // Call Backend API with multiple documents
      const response = await fetch('/api/backend/relationship/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          documents: selectedNodes.map(node => ({
            id: node.id,
            label: node.label,
            type: node.type,
            properties: node.properties,
          })),
          messages: chatHistory,
          query: currentQuery,
        }),
      });

      if (!response.ok) {
        if (response.status === 404) {
           console.warn("Backend endpoint not found, using dummy response.");
           await new Promise(resolve => setTimeout(resolve, 1500));
           const dummyResponse: Message = {
             id: `assistant-${Date.now()}`,
             role: 'assistant',
             content: `(데모 응답) "${currentQuery}"에 대한 분석입니다.\n\n선택하신 ${selectedNodes.length}개의 문서는 서로 밀접한 관련이 있습니다. 각 문서는 서로 다른 관점에서 주제를 다루고 있으며, 통합적으로 활용하면 더 깊은 인사이트를 얻을 수 있습니다.\n\n추가적으로 궁금한 점이 있으신가요?`,
             timestamp: new Date(),
           };
           setMessages((prev) => [...prev, dummyResponse]);
           return;
        }

        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(errorData.error || 'Failed to get response');
      }

      const data = await response.json();

      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: data.response,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Failed to get LLM response:', error);

      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: `죄송합니다. 응답을 생성하는 중 오류가 발생했습니다.\n\n오류: ${error instanceof Error ? error.message : '알 수 없는 오류'}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl h-[80vh] flex flex-col p-0 gap-0">
        {/* Header */}
        <DialogHeader className="px-6 py-4 border-b shrink-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              <DialogTitle>관계 인사이트 탐색</DialogTitle>
            </div>
          </div>
          <DialogDescription>
            선택된 {selectedNodes.length}개 문서의 관계와 인사이트를 AI와 함께 탐색하세요
          </DialogDescription>
        </DialogHeader>

        {/* Documents Info */}
        <div className="px-6 py-3 bg-muted/30 border-b shrink-0">
          <div className={`grid gap-3 ${selectedNodes.length === 2 ? 'grid-cols-2' : selectedNodes.length === 3 ? 'grid-cols-3' : 'grid-cols-2'}`}>
            {selectedNodes.map((node, idx) => {
              const color = DOCUMENT_COLORS[idx % DOCUMENT_COLORS.length];
              return (
                <div key={node.id} className={`flex items-start gap-3 p-3 ${color.bg} border ${color.border} rounded-lg`}>
                  <FileText className={`h-5 w-5 ${color.icon} mt-0.5 shrink-0`} />
                  <div className="flex-1 min-w-0">
                    <div className={`text-xs ${color.label} font-medium mb-1`}>
                      문서 {idx + 1}
                    </div>
                    <div className={`text-sm font-semibold ${color.title} line-clamp-2`}>
                      {node.label || '(선택되지 않음)'}
                    </div>
                    {node.properties.description && (
                      <div className="text-xs text-muted-foreground mt-1 line-clamp-2">
                        {node.properties.description as string}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Chat Messages */}
        <ScrollArea className="flex-1 px-6" ref={scrollRef}>
          <div className="py-4 space-y-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-3 ${message.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted'}`}
                >
                  <div className="text-sm whitespace-pre-wrap">{message.content}</div>
                  <div
                    className={`text-[10px] mt-1 ${message.role === 'user' ? 'text-primary-foreground/70' : 'text-muted-foreground'}`}
                  >
                    {message.timestamp.toLocaleTimeString('ko-KR', {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </div>
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-muted rounded-lg px-4 py-3">
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                </div>
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Input Area */}
        <div className="px-6 py-4 border-t bg-background shrink-0">
          <div className="flex gap-2">
            <Input
              placeholder={`${selectedNodes.length}개 문서의 관계나 인사이트에 대해 질문하세요...`}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyPress}
              disabled={isLoading}
              className="flex-1"
            />
            <Button
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              size="icon"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            💡 예시: &quot;문서들의 공통점은?&quot;, &quot;어떤 관계가 있나요?&quot;, &quot;통합해서 활용하려면?&quot;
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
};
