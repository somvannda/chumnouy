import { LifeBuoy } from "lucide-react";
import { Card } from "./ui";

export default function AuthShell({ title, subtitle, children, footer }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-page px-6 py-12">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center gap-2.5">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand text-white">
            <LifeBuoy size={20} />
          </span>
          <span className="text-lg font-extrabold text-ink">Chumnouy</span>
        </div>
        <Card className="p-6">
          <h1 className="text-xl font-black text-ink">{title}</h1>
          <p className="mt-1 text-sm text-ink-soft">{subtitle}</p>
          <div className="mt-6">{children}</div>
        </Card>
        {footer && <p className="mt-4 text-center text-sm text-ink-soft">{footer}</p>}
      </div>
    </div>
  );
}
