import { betterAuth } from "better-auth";

import { authOptions } from "./options.js";

export const auth = betterAuth(authOptions);
