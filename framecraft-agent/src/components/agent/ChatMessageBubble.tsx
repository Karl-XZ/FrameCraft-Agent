import React from 'react';

interface ChatMessageBubbleProps {
  role: 'user' | 'agent';
  text: string;
}

export default function ChatMessageBubble({ role, text }: ChatMessageBubbleProps) {
  const isUser = role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} animate-fade-in-up`}>
      {!isUser && (
        <div className="w-7 h-7 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mr-2 mt-0.5">
          <div className="w-2 h-2 rounded-full bg-primary-light" />
        </div>
      )}
      <div
        className={`max-w-[85%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
          isUser
            ? 'bg-primary/20 text-text-main rounded-tr-sm border border-primary/20'
            : 'glass rounded-tl-sm text-text-secondary'
        }`}
      >
        {text}
      </div>
      {isUser && (
        <div className="w-7 h-7 rounded-full bg-secondary/20 flex items-center justify-center flex-shrink-0 ml-2 mt-0.5">
          <div className="w-2 h-2 rounded-full bg-secondary" />
        </div>
      )}
    </div>
  );
}
