import type { AuthEmail, AuthEmailDelivery } from "./types.js";

export class ConsoleAuthEmailDelivery implements AuthEmailDelivery {
  constructor() {
    if (process.env.NODE_ENV === "production") {
      throw new Error(
        "Console email delivery is disabled in production. Configure AUTH_EMAIL_DELIVERY=smtp.",
      );
    }
  }

  async send(message: AuthEmail): Promise<void> {
    console.info(
      [
        "[SodAI auth email]",
        `To: ${message.to}`,
        `Subject: ${message.subject}`,
        "",
        message.text,
      ].join("\n"),
    );
  }
}
