import Link from "next/link";

export const metadata = { title: "Not found" };

export default function NotFound() {
  return (
    <main
      id="content"
      className="mx-auto flex min-h-svh w-full max-w-[520px] flex-col items-center justify-center px-5 py-16 text-center sm:px-8"
    >
      <p className="eyebrow">404</p>
      <h1 className="display mt-3 text-balance">
        That page isn&apos;t here.
      </h1>
      <p className="caption mx-auto mt-4 max-w-[42ch]">
        It may have moved, or the link may be wrong. Nothing you were working on
        has been lost.
      </p>
      <div className="mt-8">
        <Link
          href="/"
          className="press inline-block rounded-full px-5 py-2.5 text-[15px] font-medium"
          style={{ background: "var(--ink)", color: "var(--bg)" }}
        >
          Start a new cut
        </Link>
      </div>
    </main>
  );
}
