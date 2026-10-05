// Client-side form rules mirroring the backend (BR1.1, BR1.2). The server stays the
// authority: the common-password check happens there (PASSWORD_TOO_WEAK).
// `zod/mini` is the tree-shakeable zod build; it keeps the auth routes within the 200 KB
// JavaScript budget (NFR9.5).
import * as z from "zod/mini";

export const PASSWORD_RULES = [
  { id: "length", text: "At least 8 characters", test: (value: string) => value.length >= 8 },
  {
    id: "letter-number",
    text: "A letter and a number",
    test: (value: string) => /\p{L}/u.test(value) && /\d/.test(value),
  },
] as const;

const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s.]{2,}$/;

const email = z
  .string()
  .check(
    z.trim(),
    z.minLength(1, "Enter your email address."),
    z.maxLength(254, "Enter a valid email address."),
    z.regex(EMAIL_PATTERN, "Enter a valid email address."),
  );

export const signUpSchema = z.object({
  fullName: z
    .string()
    .check(
      z.trim(),
      z.minLength(1, "Enter your full name."),
      z.maxLength(120, "Use 120 characters or fewer."),
    ),
  email,
  password: z.string().check(
    z.maxLength(128, "Use 128 characters or fewer."),
    z.refine((value) => PASSWORD_RULES.every((rule) => rule.test(value)), {
      message: "Your password must meet the rules below.",
    }),
  ),
});

export const logInSchema = z.object({
  email,
  password: z.string().check(z.minLength(1, "Enter your password.")),
});

export const codeSchema = z.object({
  code: z.string().check(z.trim(), z.regex(/^\d{6}$/, "Enter the 6-digit code from the email.")),
});

export type SignUpValues = z.infer<typeof signUpSchema>;
export type LogInValues = z.infer<typeof logInSchema>;
export type CodeValues = z.infer<typeof codeSchema>;

// --- U2 -------------------------------------------------------------------------------

const newPassword = z.string().check(
  z.maxLength(128, "Use 128 characters or fewer."),
  z.refine((value) => PASSWORD_RULES.every((rule) => rule.test(value)), {
    message: "Your password must meet the rules below.",
  }),
);

/** The confirm field exists only in the form; it must match before anything is sent (BR5.2). */
function confirmMatches(values: { newPassword: string; confirmPassword: string }): boolean {
  return values.newPassword === values.confirmPassword;
}

const MISMATCH = { message: "The passwords don't match.", path: ["confirmPassword"] };

export const forgotPasswordSchema = z.object({ email });

export const resetPasswordSchema = z
  .object({ newPassword, confirmPassword: z.string() })
  .check(z.refine(confirmMatches, MISMATCH));

export const changePasswordSchema = z
  .object({
    currentPassword: z.string().check(z.minLength(1, "Enter your current password.")),
    newPassword,
    confirmPassword: z.string(),
  })
  .check(z.refine(confirmMatches, MISMATCH));

export type ForgotPasswordValues = z.infer<typeof forgotPasswordSchema>;
export type ResetPasswordValues = z.infer<typeof resetPasswordSchema>;
export type ChangePasswordValues = z.infer<typeof changePasswordSchema>;
