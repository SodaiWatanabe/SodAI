import Link from "next/link";

import { AuthShell } from "@/components/auth/auth-shell";
import { ForgotPasswordForm } from "@/components/auth/forgot-password-form";

export default function ForgotPasswordPage() {
  return (
    <AuthShell
      title="パスワードを再設定"
      description="登録済みのメールアドレスへ、安全な再設定リンクを送信します。"
      footer={
        <Link href="/auth/login" className="font-semibold text-blue-600 hover:text-blue-700">
          ログインへ戻る
        </Link>
      }
    >
      <ForgotPasswordForm />
    </AuthShell>
  );
}
