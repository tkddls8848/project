import NextAuth from "next-auth"
import GoogleProvider from "next-auth/providers/google"

// Admin emails from environment variable
const getAdminEmails = (): string[] => {
  const adminEmails = process.env.ADMIN_EMAILS || "";
  return adminEmails.split(",").map(email => email.trim()).filter(Boolean);
};

export const authOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID ?? "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? "",
    }),
  ],
  pages: {
    signIn: '/login',
  },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        // Check if user email is in admin list
        const adminEmails = getAdminEmails();
        token.role = adminEmails.includes(user.email ?? "") ? "admin" : "user";
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.role = token.role as string;
      }
      return session;
    },
  },
};

const handler = NextAuth(authOptions);

export { handler as GET, handler as POST }
