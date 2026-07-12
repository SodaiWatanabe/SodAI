import Link from "next/link";
import { redirect } from "next/navigation";

import { AuthDivider } from "@/components/auth/auth-divider";
import { AuthShell } from "@/components/auth/auth-shell";
import { GoogleSignInButton } from "@/components/auth/google-sign-in-button";
import { RegisterForm } from "@/components/auth/register-form";
import { isGoogleAuthConfigured } from "@/lib/auth/environment";
import { getCurrentSession } from "@/lib/auth/session";

export const dynamic = "force-dynamic";

export default async function RegisterPage() {
  const session = await getCurrentSession();
  if (session) {
    redirect("/account");
  }

  return (
    <AuthShell
      title="アカウントを作成"
      description="招待は不要です。Googleまたは確認可能なメールアドレスで登録できます。"
      footer={
        <>
          すでにアカウントをお持ちの場合は{" "}
          <Link href="/auth/login" className="font-semibold text-blue-600 hover:text-blue-700">
            ログイン
          </Link>
        </>
      }
    >
      <GoogleSignInButton enabled={isGoogleAuthConfigured()} />
      <AuthDivider />
      <RegisterForm />
    </AuthShell>
  );
}
