import React from 'react';

export default function AgentTypingIndicator() {
  return (
    <div className="flex justify-start animate-fade-in-up">
      <div className="w-7 h-7 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mr-2 mt-0.5">
        <div className="w-2 h-2 rounded-full bg-primary-light animate-pulse" />
      </div>
      <div className="glass rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-text-secondary border border-primary/15">
        <div className="flex items-center gap-2">
          <span className="text-text-main font-medium">Agent 正在回复</span>
          <span className="inline-flex gap-1 items-center" aria-hidden>
            <span className="w-1.5 h-1.5 rounded-full bg-primary-light animate-bounce [animation-delay:0ms]" />
            <span className="w-1.5 h-1.5 rounded-full bg-primary-light animate-bounce [animation-delay:150ms]" />
            <span className="w-1.5 h-1.5 rounded-full bg-primary-light animate-bounce [animation-delay:300ms]" />
          </span>
        </div>
        <p className="text-xs text-text-muted mt-1">正在理解你的修改意图并生成方案…</p>
      </div>
    </div>
  );
}
