import nodemailer, { type Transporter } from "nodemailer";

import type { AuthEmail, AuthEmailDelivery } from "./types.js";

function requireSmtpEnvironment(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) {
    throw new Error(`${name} is required when AUTH_EMAIL_DELIVERY=smtp.`);
  }
  return value;
}

function getSmtpPort(): number {
  const configured = process.env.AUTH_SMTP_PORT?.trim() || "587";
  const port = Number(configured);
  if (!Number.isInteger(port) || port < 1 || port > 65_535) {
    throw new Error("AUTH_SMTP_PORT must be an integer between 1 and 65535.");
  }
  return port;
}

export class SmtpAuthEmailDelivery implements AuthEmailDelivery {
  private readonly from = requireSmtpEnvironment("AUTH_EMAIL_FROM");
  private readonly transporter: Transporter;

  constructor() {
    const user = process.env.AUTH_SMTP_USER?.trim();
    const password = process.env.AUTH_SMTP_PASSWORD?.trim();

    if (Boolean(user) !== Boolean(password)) {
      throw new Error(
        "AUTH_SMTP_USER and AUTH_SMTP_PASSWORD must either both be set or both be omitted.",
      );
    }

    this.transporter = nodemailer.createTransport({
      host: requireSmtpEnvironment("AUTH_SMTP_HOST"),
      port: getSmtpPort(),
      secure: process.env.AUTH_SMTP_SECURE === "true",
      auth: user && password ? { user, pass: password } : undefined,
      connectionTimeout: 10_000,
      greetingTimeout: 10_000,
      socketTimeout: 20_000,
    });
  }

  async send(message: AuthEmail): Promise<void> {
    await this.transporter.sendMail({
      from: this.from,
      to: message.to,
      subject: message.subject,
      text: message.text,
      html: message.html,
    });
  }
}
