import { DefaultSession } from "next-auth";

declare module "next-auth" {
  /**
   * Extend User type to include role
   */
  interface User {
    role?: string;
  }

  /**
   * Extend Session type to include role
   */
  interface Session {
    user: {
      role?: string;
    } & DefaultSession["user"];
  }
}

declare module "next-auth/jwt" {
  /**
   * Extend JWT type to include role
   */
  interface JWT {
    role?: string;
  }
}
