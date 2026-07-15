import { ConsoleAuthEmailDelivery } from "./console-delivery.js";
import { SmtpAuthEmailDelivery } from "./smtp-delivery.js";
import type { AuthEmail, AuthEmailDelivery } from "./types.js";

function createDelivery(): AuthEmailDelivery {
  const mode = process.env.AUTH_EMAIL_DELIVERY ?? "console";
  if (mode === "console") {
    return new ConsoleAuthEmailDelivery();
  }
  if (mode === "smtp") return new SmtpAuthEmailDelivery();
  throw new Error(`Unsupported AUTH_EMAIL_DELIVERY mode: ${mode}`);
}

const delivery = createDelivery();

function escapeHtml(value: string): string {
  return value.replace(/[&<>'"]/g, (character) => {
    const entities: Record<string, string> = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "'": "&#39;",
      '"': "&quot;",
    };
    return entities[character] ?? character;
  });
}

function codeEmail(params: { code: string; subject: string; to: string }): AuthEmail {
  const safeCode = escapeHtml(params.code);
  return {
    to: params.to,
    subject: params.subject,
    text: `SodAIへのログインコードは ${params.code} です。5分以内に入力してください。\n\nこの操作に心当たりがない場合は、このメールを破棄してください。`,
    html: `
      <div style="font-family: system-ui, sans-serif; color: #0f172a; line-height: 1.7;">
        <h1 style="font-size: 22px; margin: 0 0 20px;">SodAI</h1>
        <p>SodAIへのログインコードです。</p>
        <p style="font-size: 30px; font-weight: 650; letter-spacing: 0.24em; margin: 24px 0;">
          ${safeCode}
        </p>
        <p style="color: #64748b; font-size: 13px;">このコードは5分間有効です。</p>
        <p style="color: #64748b; font-size: 13px;">この操作に心当たりがない場合は、このメールを破棄してください。</p>
      </div>
    `,
  };
}

export async function sendSignInOtpEmail(to: string, otp: string): Promise<void> {
  const message = codeEmail({
    code: otp,
    subject: "SodAIへのログインコード",
    to,
  });

  try {
    await delivery.send(message);
  } catch (error) {
    console.error("Failed to deliver an authentication email.", error);
    throw error;
  }
}
