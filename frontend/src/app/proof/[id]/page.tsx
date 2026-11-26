'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { CheckCircle2, MessageSquare, ArrowLeft, Send, ShieldCheck, Heart } from 'lucide-react';

interface Comment {
  id: string;
  author: string;
  text: string;
  time: string;
}

export default function ProofingPage() {
  const params = useParams();
  const proofId = (params?.id as string) || 'demo';
  const [status, setStatus] = useState<'pending' | 'approved' | 'changes_requested'>('pending');
  const [comments, setComments] = useState<Comment[]>([
    {
      id: 'c1',
      author: 'Studio Lead',
      text: 'Ảnh đã xử lý nền trắng Amazon chuẩn 85% diện tích và shadow tiếp xúc tự nhiên.',
      time: '10:30 AM',
    },
  ]);
  const [newComment, setNewComment] = useState('');
  const [authorName, setAuthorName] = useState('Khách hàng');

  const handleApprove = () => {
    setStatus('approved');
  };

  const handleRequestChanges = () => {
    setStatus('changes_requested');
  };

  const handleSendComment = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newComment.trim()) return;
    setComments([
      ...comments,
      {
        id: `c_${Date.now()}`,
        author: authorName || 'Khách hàng',
        text: newComment.trim(),
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
    setNewComment('');
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col">
      {/* Top Mobile Proofing Header */}
      <header className="h-14 border-b border-slate-800 bg-slate-950 px-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/" className="text-slate-400 hover:text-white p-1 rounded">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-xs font-bold text-white tracking-wide">KROMA PROOFING PORTAL</h1>
            <p className="text-[10px] text-slate-400">Phiên duyệt: {proofId}</p>
          </div>
        </div>

        {/* Approval Badge */}
        <div>
          {status === 'approved' ? (
            <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>ĐÃ DUYỆT</span>
            </span>
          ) : status === 'changes_requested' ? (
            <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30">
              YÊU CẦU CHỈNH SỬA
            </span>
          ) : (
            <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
              ĐANG CHỜ DUYỆT
            </span>
          )}
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col md:flex-row overflow-hidden">
        {/* Image Presentation Viewer */}
        <div className="flex-1 flex flex-col items-center justify-center p-6 bg-slate-950/60 relative">
          <div className="max-w-md w-full bg-white rounded-lg shadow-2xl p-6 flex flex-col items-center">
            {/* Subject preview */}
            <div className="w-full aspect-square bg-white rounded flex items-center justify-center relative overflow-hidden">
              <img
                src="/assets/logo/kroma-logo-horizontal.svg"
                alt="Product Preview"
                className="max-h-48 object-contain"
              />
            </div>
            <div className="w-full mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
              <span className="font-medium text-slate-700">Bộ ảnh TMĐT Tiêu Chuẩn</span>
              <span className="font-mono">1024 × 1024 px</span>
            </div>
          </div>

          {/* Quick Decision Bar for Client */}
          <div className="mt-6 flex items-center gap-3">
            <button
              onClick={handleRequestChanges}
              className="px-4 py-2 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
            >
              Yêu cầu chỉnh sửa lại
            </button>
            <button
              onClick={handleApprove}
              className="px-6 py-2 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg transition-colors flex items-center gap-1.5"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>Duyệt Ảnh Này</span>
            </button>
          </div>
        </div>

        {/* Feedback & Comments Sidebar */}
        <aside className="w-full md:w-80 border-t md:border-t-0 md:border-l border-slate-800 bg-slate-950 flex flex-col h-80 md:h-auto">
          <div className="p-3 border-b border-slate-800 flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-cyan-400" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">
              Nhận xét phản hồi ({comments.length})
            </h2>
          </div>

          {/* Comment list */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
            {comments.map((c) => (
              <div key={c.id} className="p-2.5 rounded bg-slate-900 border border-slate-800 text-xs">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-slate-300">{c.author}</span>
                  <span className="text-[10px] text-slate-500">{c.time}</span>
                </div>
                <p className="text-slate-400 leading-relaxed">{c.text}</p>
              </div>
            ))}
          </div>

          {/* Input Form */}
          <form onSubmit={handleSendComment} className="p-3 border-t border-slate-800 bg-slate-900/50">
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Để lại nhận xét hoặc yêu cầu sửa..."
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                className="flex-1 px-3 py-1.5 text-xs rounded bg-slate-800 border border-slate-700 text-white focus:outline-none focus:border-cyan-500"
              />
              <button
                type="submit"
                className="px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold"
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </div>
          </form>
        </aside>
      </main>
    </div>
  );
}
