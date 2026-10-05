"use client";

// Forgot password, step 1 (US3.9, WF-U2-7; AC3.9.1). The server answers the same for every
// email, and the screen shows no outcome toast (BR4.1): it moves on to the code step with a
// neutral message.
import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";

import { toast } from "@/components/feedback/toast";
import { Button } from "@/components/ui/button";
import { describedBy, FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { isApiError } from "@/lib/api/errors";
import { useAuthActions } from "@/lib/auth";

import { messageFor } from "./messages";
import { forgotPasswordSchema, type ForgotPasswordValues } from "./schemas";

export function ForgotPasswordForm() {
  const router = useRouter();
  const { requestPasswordReset } = useAuthActions();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotPasswordValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: "" },
  });

  async function onSubmit(values: ForgotPasswordValues) {
    try {
      await requestPasswordReset(values.email);
      router.push("/forgot-password/verify");
    } catch (error) {
      if (!isApiError(error)) throw error;
      // Throttling or a network failure; nothing about the account is revealed.
      toast.error(messageFor(error));
    }
  }

  return (
    <form
      noValidate
      onSubmit={handleSubmit(onSubmit)}
      className="space-y-5"
      data-testid="forgot-password-form"
    >
      <p className="text-base">
        Enter the email you signed up with. If it belongs to an account, we&apos;ll email a 6-digit
        code.
      </p>
      <FormField id="email" label="Email" error={errors.email?.message}>
        <Input
          id="email"
          type="email"
          autoComplete="email"
          readOnly={isSubmitting}
          aria-invalid={errors.email ? "true" : "false"}
          aria-describedby={describedBy("email", { error: Boolean(errors.email) })}
          data-testid="forgot-password-email-input"
          {...register("email")}
        />
      </FormField>
      <Button
        type="submit"
        width="full"
        disabled={isSubmitting}
        data-testid="forgot-password-submit-button"
      >
        {isSubmitting ? "Sending…" : "Send code"}
      </Button>
      <p className="text-center text-base">
        <Link
          href="/login"
          className="font-semibold text-accent-strong underline"
          data-testid="forgot-password-login-link"
        >
          Back to log in
        </Link>
      </p>
    </form>
  );
}
