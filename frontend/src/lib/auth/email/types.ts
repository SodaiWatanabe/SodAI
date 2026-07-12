export type AuthEmail = {
  html: string;
  subject: string;
  text: string;
  to: string;
};

export interface AuthEmailDelivery {
  send(message: AuthEmail): Promise<void>;
}
