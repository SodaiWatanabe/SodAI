import { ConsoleAuthEmailDelivery } from "./console-delivery";
import { SmtpAuthEmailDelivery } from "./smtp-delivery";
import type { AuthEmail, AuthEmailDelivery } from "./types";

let delivery: AuthEmailDelivery | undefined;

function getDelivery(): AuthEmailDelivery {
  if (delivery) {
    return delivery;
  }

  const mode = process.env.AUTH_EMAIL_DELIVERY ?? "console";

  if (mode === "console") {
    delivery = new ConsoleAuthEmailDelivery();
  } else if (mode === "smtp") {
    delivery = new SmtpAuthEmailDelivery();
  } else {
    throw new Error(`Unsupported AUTH_EMAIL_DELIVERY mode: ${mode}`);
  }

  return delivery;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>'"]/g, (character) => {
    const entities: Record<string, string> = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "'": "&#39;",
      '"': "&quot;",
    };

    return entities[character];
  });
}

function linkEmail(params: {
  actionLabel: string;
  body: string;
  subject: string;
  to: string;
  url: string;
}): AuthEmail {
  const safeUrl = escapeHtml(params.url);

  return {
    to: params.to,
    subject: params.subject,
    text: `${params.body}\n\n${params.actionLabel}: ${params.url}\n\nこの操作に心当たりがない場合は、このメールを破棄してください。`,
    html: `
      <div style="font-family: system-ui, sans-serif; color: #0f172a; line-height: 1.7;">
        <h1 style="font-size: 22px; margin: 0 0 20px;">SodAI</h1>
        <p>${escapeHtml(params.body)}</p>
        <p style="margin: 28px 0;">
          <a href="${safeUrl}" style="background: #0f172a; border-radius: 10px; color: #fff; display: inline-block; padding: 12px 18px; text-decoration: none;">
            ${escapeHtml(params.actionLabel)}
          </a>
        </p>
        <p style="color: #64748b; font-size: 13px;">この操作に心当たりがない場合は、このメールを破棄してください。</p>
      </div>
    `,
  };
}

function sendInBackground(message: AuthEmail): void {
  void getDelivery()
    .send(message)
    .catch((error: unknown) => {
      console.error("Failed to deliver an authentication email.", error);
    });
}

export function sendVerificationEmail(to: string, url: string): void {
  sendInBackground(
    linkEmail({
      actionLabel: "メールアドレスを確認する",
      body: "SodAIへの登録を完了するため、メールアドレスを確認してください。",
      subject: "SodAIのメールアドレス確認",
      to,
      url,
    }),
  );
}

export function sendPasswordResetEmail(to: string, url: string): void {
  sendInBackground(
    linkEmail({
      actionLabel: "パスワードを再設定する",
      body: "SodAIアカウントのパスワード再設定がリクエストされました。",
      subject: "SodAIのパスワード再設定",
      to,
      url,
    }),
  );
}
