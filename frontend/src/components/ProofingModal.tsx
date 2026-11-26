'use client';

import React, { useState } from 'react';
import { X, Copy, ExternalLink, Check, Smartphone } from 'lucide-react';
import { createProofingSession } from '@/lib/apiClient';

interface ProofingModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
}

export const ProofingModal: React.FC<ProofingModalProps> = ({ isOpen, onClose, projectId }) => {
  const [clientName, setClientName] = useState('Khách hàng TMĐT');
  const [title, setTitle] = useState('Duyệt ảnh sản phẩm KROMA');
  const [createdUrl, setCreatedUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  if (!isOpen) return null;

  const handleGenerate = async () => {
    setIsGenerating(true);
    const session = await createProofingSession(projectId, title, clientName, true);
    if (session) {
      const url = `${window.location.origin}/proof/${session.id}`;
      setCreatedUrl(url);
    }
    setIsGenerating(false);
  };

  const handleCopy = () => {
    if (createdUrl) {
      navigator.clipboard.writeText(createdUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
      <div className="w-full max-w-md rounded-lg bg-surface-light border border-surface-border shadow-2xl overflow-hidden select-none">
        {/* Header */}
        <div className="p-4 border-b border-surface-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Smartphone className="w-5 h-5 text-kroma-600" />
            <h3 className="text-sm font-bold text-slate-900">Tạo Link Duyệt Ảnh Cho Khách</h3>
          </div>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-600 rounded">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-4 space-y-4 text-xs">
          <div>
            <label className="font-semibold text-slate-700 block mb-1">Tên khách hàng / Nhãn hàng:</label>
            <input
              type="text"
              value={clientName}
              onChange={(e) => setClientName(e.target.value)}
              className="w-full px-3 py-1.5 rounded border border-slate-300 focus:border-kroma-600 focus:outline-none"
              placeholder="VD: Brand Thời trang XYZ"
            />
          </div>

          <div>
            <label className="font-semibold text-slate-700 block mb-1">Tiêu đề đợt duyệt:</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-3 py-1.5 rounded border border-slate-300 focus:border-kroma-600 focus:outline-none"
              placeholder="VD: Duyệt bộ ảnh Shopee Tháng 11"
            />
          </div>

          {createdUrl ? (
            <div className="p-3 bg-emerald-50 rounded border border-emerald-200 space-y-2">
              <span className="text-emerald-800 font-semibold block">Link xét duyệt đã sẵn sàng:</span>
              <div className="flex items-center gap-1.5">
                <input
                  type="text"
                  readOnly
                  value={createdUrl}
                  className="flex-1 px-2.5 py-1 text-slate-700 bg-white border border-slate-300 rounded font-mono text-[11px]"
                />
                <button
                  onClick={handleCopy}
                  className="px-3 py-1 text-xs font-semibold rounded bg-emerald-600 hover:bg-emerald-700 text-white flex items-center gap-1"
                >
                  {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied ? 'Đã chép' : 'Sao chép'}</span>
                </button>
              </div>
              <a
                href={createdUrl}
                target="_blank"
                rel="noreferrer"
                className="text-[11px] text-emerald-700 hover:underline inline-flex items-center gap-1 font-medium mt-1"
              >
                <span>Xem trước giao diện khách</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          ) : (
            <div className="pt-2">
              <button
                onClick={handleGenerate}
                disabled={isGenerating}
                className="w-full py-2 px-3 text-xs font-semibold text-white bg-kroma-600 hover:bg-kroma-700 rounded shadow-xs transition-colors flex items-center justify-center gap-1.5"
              >
                <span>{isGenerating ? 'Đang tạo link...' : 'Khởi tạo link proofing'}</span>
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-surface-border bg-surface-subtle flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-200 rounded border border-slate-300 transition-colors"
          >
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
};
