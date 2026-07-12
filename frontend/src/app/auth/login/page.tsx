import Link from "next/link";
import { redirect } from "next/navigation";

import { AuthDivider } from "@/components/auth/auth-divider";
import { AuthShell } from "@/components/auth/auth-shell";
import { GoogleSignInButton } from "@/components/auth/google-sign-in-button";
import { LoginForm } from "@/components/auth/login-form";
import { getCurrentSession } from "@/lib/auth/session";
import { isGoogleAuthConfigured } from "@/lib/auth/environment";

export const dynamic = "force-dynamic";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; reset?: string }>;
}) {
  const session = await getCurrentSession();
  if (session) {
    redirect("/account");
  }

  const query = await searchParams;

  return (
    <AuthShell
      title="おかえりなさい"
      description="SodAIとの対話を続けるには、アカウントへログインしてください。"
      footer={
        <>
          アカウントをお持ちでない場合は{" "}
          <Link href="/auth/register" className="font-semibold text-blue-600 hover:text-blue-700">
            新規登録
          </Link>
        </>
      }
    >
      {query.reset === "completed" ? (
        <div className="mb-5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          パスワードを更新しました。新しいパスワードでログインしてください。
        </div>
      ) : null}
      <GoogleSignInButton enabled={isGoogleAuthConfigured()} />
      <AuthDivider />
      <LoginForm initialError={query.error} />
    </AuthShell>
  );
}
