import React from 'react';

interface GlassCardProps {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
}

export default function GlassCard({ children, className = '', hover = false }: GlassCardProps) {
  return (
    <div
      className={`glass-card rounded-lg ${hover ? 'hover:border-primary/30 transition-all duration-300 cursor-pointer' : ''} ${className}`}
    >
      {children}
    </div>
  );
}
