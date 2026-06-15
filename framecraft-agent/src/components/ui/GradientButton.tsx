import React from 'react';

interface GradientButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
}

export default function GradientButton({
  children,
  onClick,
  className = '',
  size = 'md',
  disabled = false,
}: GradientButtonProps) {
  const sizeClasses = {
    sm: 'px-3 py-1.5 text-xs rounded-md',
    md: 'px-5 py-2.5 text-sm rounded-lg',
    lg: 'px-8 py-3.5 text-base rounded-xl',
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`gradient-btn ${sizeClasses[size]} font-semibold tracking-wide inline-flex items-center gap-2 ${disabled ? 'opacity-40 cursor-not-allowed' : ''} ${className}`}
    >
      {children}
    </button>
  );
}
