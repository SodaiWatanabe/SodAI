import Link from "next/link";

import { AuthShell } from "@/components/auth/auth-shell";
import { ResetPasswordForm } from "@/components/auth/reset-password-form";

export default async function ResetPasswordPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; token?: string }>;
}) {
  const query = await searchParams;
  const token = query.error ? undefined : query.token;

  return (
    <AuthShell
      title="新しいパスワード"
      description="この操作を完了すると、既存のすべてのセッションが無効になります。"
      footer={
        <Link
          href="/auth/forgot-password"
          className="font-semibold text-blue-600 hover:text-blue-700"
        >
          再設定メールを送り直す
        </Link>
      }
    >
      <ResetPasswordForm token={token} />
    </AuthShell>
  );
}
