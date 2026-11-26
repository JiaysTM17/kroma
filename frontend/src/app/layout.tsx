import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'KROMA — Intelligent Image Studio',
  description: 'Chuyên biệt xử lý ảnh thương mại điện tử: Shopee, TikTok Shop, Lazada, Amazon.',
  icons: {
    icon: '/assets/logo/kroma-icon.svg',
    shortcut: '/assets/logo/kroma-icon.svg',
    apple: '/assets/logo/kroma-app-icon.svg',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <body className="antialiased min-h-screen flex flex-col bg-slate-50 text-slate-900">
        {children}
      </body>
    </html>
  );
}
