import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'TeacherLens · Your way forward', description: 'An evidence-grounded mathematics strategy partner. Local synthetic demo.' };
export default function Layout({ children }: Readonly<{children: React.ReactNode}>) {
  return <html lang="en"><body>{children}</body></html>;
}
