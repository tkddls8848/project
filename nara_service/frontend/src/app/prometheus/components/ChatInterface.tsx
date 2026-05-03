import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Loader2, Send } from 'lucide-react';
import { getTypeIcon, getTypeDisplayName } from '../utils';
import { APIDoc } from '../types';

interface ChatInterfaceProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  groupId: string | null;
  groupDocs: APIDoc[];
  chatResponse: string;
  isGenerating: boolean;
  chatMessage: string;
  setChatMessage: (msg: string) => void;
  handleChatSubmit: () => void;
  modalResponseEndRef: React.Ref<HTMLDivElement>;
}

export const ChatInterface = ({
  open,
  onOpenChange,
  groupId,
  groupDocs,
  chatResponse,
  isGenerating,
  chatMessage,
  setChatMessage,
  handleChatSubmit,
  modalResponseEndRef,
}: ChatInterfaceProps) => {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl h-[80vh] flex flex-col p-0 gap-0">
        <DialogHeader className="px-6 py-4 border-b">
          <DialogTitle>Chat with {groupId}</DialogTitle>
          <DialogDescription>
            Context specific to this group.
          </DialogDescription>
        </DialogHeader>
        
        <div className="flex flex-1 overflow-hidden">
           {/* Left Sidebar: Group Docs */}
           <div className="w-72 border-r bg-muted/10 flex flex-col">
              <div className="p-3 border-b text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                 Included Documents
              </div>
              <div className="flex-1 overflow-y-auto p-3 space-y-2">
                 {groupDocs.map((doc: APIDoc) => {
                     const TypeIcon = getTypeIcon(doc.category);
                     return (
                         <div key={doc.id} className="flex items-start gap-2 p-2 rounded-lg bg-card border hover:border-primary/50 transition-colors">
                             <div className="rounded bg-muted p-1 shrink-0 mt-0.5">
                                 <TypeIcon className="h-3 w-3 text-muted-foreground" />
                             </div>
                             <div className="min-w-0">
                                 <div className="text-xs font-medium truncate" title={doc.title}>{doc.title}</div>
                                 <div className="text-[10px] text-muted-foreground truncate">{getTypeDisplayName(doc.category)}</div>
                             </div>
                         </div>
                     );
                 })}
                 {groupDocs.length === 0 && (
                     <div className="text-xs text-muted-foreground text-center py-4">
                         No documents in this group.
                     </div>
                 )}
              </div>
           </div>

           {/* Right: Chat Interface */}
           <div className="flex-1 flex flex-col min-w-0">
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                  {chatResponse && open ? (
                  <div className="flex gap-3 max-w-3xl mx-auto">
                      <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                      🤖
                      </div>
                      <div className="space-y-1">
                      <p className="text-sm font-medium">Assistant</p>
                      <div className="text-sm leading-relaxed whitespace-pre-wrap">
                          {chatResponse}
                      </div>
                      </div>
                  </div>
                  ) : (
                  !isGenerating && (
                      <div className="h-full flex items-center justify-center text-muted-foreground text-sm">
                      Ask a question about {groupId}.
                      </div>
                  )
                  )}
                  <div ref={modalResponseEndRef} /> 
              </div>

              <div className="p-4 border-t bg-background/50 backdrop-blur-sm">
                  <div className="max-w-3xl mx-auto flex gap-2">
                  <Input 
                      placeholder={`Ask about ${groupId}...`}
                      value={chatMessage}
                      onChange={(e) => setChatMessage(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && !isGenerating && handleChatSubmit()}
                      disabled={isGenerating}
                      className="flex-1"
                  />
                  <Button onClick={handleChatSubmit} disabled={isGenerating || !chatMessage.trim()}>
                      {isGenerating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                      <span className="sr-only">Send</span>
                  </Button>
                  </div>
              </div>
           </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};