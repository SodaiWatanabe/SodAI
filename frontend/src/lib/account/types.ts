export type Account = {
  id: string;
  status: "active" | "suspended" | "disabled";
  display_name: string | null;
  email: string | null;
  email_verified: boolean;
  created_at: string;
  updated_at: string;
};
