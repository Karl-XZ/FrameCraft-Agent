import React, { useState } from 'react';
import { Send, Bot } from 'lucide-react';
import ChatMessageBubble from './ChatMessageBubble';
import AgentTypingIndicator from './AgentTypingIndicator';
import PatchConfirmCard from './PatchConfirmCard';
import QuickActionChips from './QuickActionChips';
import { useProjectStore } from '../../store/projectStore';
import { useStudioWorkflow } from '../../hooks/useStudioWorkflow';

const DEFAULT_PROMPT = `你好！我是你的 AI 视频助手，可以帮你：

• 根据口播内容调整剪辑节奏
• 修改字幕风格或文案
• 替换或增删 B-roll 镜头
• 调整背景音乐
• 一键导出剪映草稿

用自然语言描述你想做的修改，我来帮你完成 ✨`;

export default function AgentChatPanel() {
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const { chatMessages, pendingPatch, versions, currentVersionId } = useProjectStore();
  const { sendChat, acceptPatch, discardPatch, revertToPreviousVersion } = useStudioWorkflow();

  const canRevert = versions.length > 1 && versions.findIndex((v) => v.id === currentVersionId) < versions.length - 1;

  const handleSend = async () => {
    const text = input.trim();
    if (!text || sending) return;
    setInput('');
    setSending(true);
    try {
      await sendChat(text);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/8">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-primary-light" />
          <span className="text-sm font-semibold text-text-main">Agent 对话</span>
          {sending && (
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-primary/15 text-primary-light border border-primary/25 animate-pulse">
              回复中
            </span>
          )}
        </div>
        {canRevert && (
          <button
            type="button"
            onClick={() => void revertToPreviousVersion()}
            className="text-xs text-text-muted hover:text-text-main transition-colors px-2 py-1 rounded-lg border border-white/10 hover:bg-white/[0.06]"
          >
            撤销到上一版本
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {chatMessages.length === 0 && !sending ? (
          <div className="h-full flex items-center justify-center">
            <p className="text-xs text-text-muted leading-relaxed whitespace-pre-line max-w-[200px] text-center">
              {DEFAULT_PROMPT}
            </p>
          </div>
        ) : (
          <>
            {chatMessages.map((msg) => (
              <ChatMessageBubble key={msg.id} role={msg.role} text={msg.text} />
            ))}
            {sending && <AgentTypingIndicator />}
          </>
        )}
        {pendingPatch && (
          <PatchConfirmCard
            patch={pendingPatch}
            onAccept={() => void acceptPatch()}
            onDiscard={() => discardPatch()}
          />
        )}
      </div>

      <div className="px-4 py-3 border-t border-white/8">
        <QuickActionChips onSelect={(text) => !sending && setInput(text)} />
      </div>

      <div className="px-4 py-3 border-t border-white/8">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !sending && void handleSend()}
            placeholder={sending ? 'Agent 思考中…' : '描述你想做的修改...'}
            disabled={sending}
            className="flex-1 px-3 py-2 rounded-lg bg-white/5 border border-white/8 text-sm text-text-main placeholder:text-text-muted focus:outline-none focus:border-primary/40 disabled:opacity-60"
          />
          <button
            type="button"
            onClick={() => void handleSend()}
            disabled={sending}
            className="gradient-btn px-3 py-2 rounded-lg flex items-center gap-1.5 disabled:opacity-60"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
