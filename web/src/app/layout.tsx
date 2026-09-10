import type { Metadata, Viewport } from "next";
import { Toaster } from "sonner";
import "./globals.css";

const title = "Reel Editor";
const description =
  "Cut your footage like the reel you admire. Borrow an edit's grammar and reapply it to your own clips, on your own music.";

export const metadata: Metadata = {
  title: { default: title, template: "%s · Reel Editor" },
  description,
  applicationName: title,
  openGraph: {
    title,
    description,
    type: "website",
    siteName: title,
  },
  twitter: { card: "summary_large_image", title, description },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fbfbfd" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0a0b" },
  ],
  // No maximum-scale — capping zoom breaks pinch-to-zoom for anyone who needs it.
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full">
        {/* Keyboard users shouldn't have to tab through the whole page. */}
        <a href="#content" className="skip-link">
          Skip to content
        </a>
        {children}
        <Toaster
          position="bottom-center"
          offset={16}
          toastOptions={{
            style: {
              background: "var(--ink)",
              color: "var(--bg)",
              border: "none",
              borderRadius: "10px",
            },
          }}
        />
      </body>
    </html>
  );
}
