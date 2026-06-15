import React from 'react';
import { Link } from 'react-router-dom';
import { Zap, Film, Sparkles } from 'lucide-react';
import { useProjectStore } from '../../store/projectStore';

export default function AppHeader() {
  return (
    <header className="flex items-center justify-between px-6 py-3 glass border-b border-white/5">
      <Link to="/" className="flex items-center gap-3 group">
        <div className="w-9 h-9 rounded-lg bg-btn-gradient flex items-center justify-center shadow-glow group-hover:scale-105 transition-transform">
          <Zap className="w-5 h-5 text-white" />
        </div>
        <span className="text-xl font-bold tracking-tight">
          <span className="gradient-text">帧造</span>
          <span className="text-text-main font-extrabold"> Agent</span>
        </span>
      </Link>

      <div className="flex items-center gap-3">
        <Link
          to="/studio"
          className="gradient-btn px-5 py-2 rounded-lg text-sm font-semibold flex items-center gap-2"
        >
          <Film className="w-4 h-4" />
          进入工作台
        </Link>
      </div>
    </header>
  );
}
