import React from 'react';
import GlassCard from '../ui/GlassCard';

interface FeatureCardProps {
  title: string;
  description: string;
  icon: React.ReactNode;
  gradient: string;
}

export default function FeatureCard({ title, description, icon, gradient }: FeatureCardProps) {
  return (
    <GlassCard hover className="p-6 flex flex-col gap-4">
      <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${gradient}`}>
        {icon}
      </div>
      <div>
        <h3 className="text-base font-bold text-text-main mb-2">{title}</h3>
        <p className="text-sm text-text-secondary leading-relaxed">{description}</p>
      </div>
    </GlassCard>
  );
}
