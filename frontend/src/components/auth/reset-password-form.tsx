"use client";

// Forgot password, step 3 (US3.9, WF-U2-7; AC3.9.3-AC3.9.5). The reset token stays inside
// the auth module's memory; this form only knows whether one is present.
import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";

import { toast } from "@/components/feedback/toast";
import { Button } from "@/components/ui/button";
import { describedBy, FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { isApiError } from "@/lib/api/errors";
import { useAuthActions } from "@/lib/auth";

import { fieldMessage, messageFor } from "./messages";
import { PasswordRules } from "./password-rules";
import { resetPasswordSchema, type ResetPasswordValues } from "./schemas";

function StartAgain() {
  return (
    <div className="space-y-4" data-testid="reset-password-start-again">
      <p role="alert" className="text-base">
        This reset link has expired or was already used. Please start again.
      </p>
      <Link
        href="/forgot-password"
        className="font-semibold text-accent-strong underline"
        data-testid="reset-password-start-again-link"
      >
        Request a new code
      </Link>
    </div>
  );
}

export function ResetPasswordForm() {
  const router = useRouter();
  const { hasResetToken, resetPassword } = useAuthActions();
  const [expired, setExpired] = useState(() => !hasResetToken());
  const {
    register,
    handleSubmit,
    control,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { newPassword: "", confirmPassword: "" },
  });
  const newPassword = useWatch({ control, name: "newPassword" });

  if (expired) {
    return <StartAgain />;
  }

  async function onSubmit(values: ResetPasswordValues) {
    try {
      await resetPassword(values.newPassword);
      toast.success("Password changed — please log in.");
      router.replace("/login");
    } catch (error) {
      if (!isApiError(error)) throw error;
      if (error.code === "RESET_TOKEN_INVALID") {
        setExpired(true);
        return;
      }
      if (error.code === "VALIDATION_FAILED") {
        const reason = error.fieldErrors.newPassword ?? "PASSWORD_TOO_WEAK";
        setError(
          "newPassword",
          { message: fieldMessage("password", reason) },
          { shouldFocus: true },
        );
        return;
      }
      toast.error(messageFor(error));
    }
  }

  return (
    <form
      noValidate
      onSubmit={handleSubmit(onSubmit)}
      className="space-y-5"
      data-testid="reset-password-form"
    >
      <FormField
        id="newPassword"
        label="New password"
        error={errors.newPassword?.message}
        hint={<PasswordRules id="newPassword-rules" value={newPassword} />}
      >
        <Input
          id="newPassword"
          type="password"
          autoComplete="new-password"
          readOnly={isSubmitting}
          aria-invalid={errors.newPassword ? "true" : "false"}
          aria-describedby={describedBy("newPassword", {
            hint: true,
            error: Boolean(errors.newPassword),
          })}
          data-testid="reset-password-new-input"
          {...register("newPassword")}
        />
      </FormField>
      <FormField
        id="confirmPassword"
        label="Confirm new password"
        error={errors.confirmPassword?.message}
      >
        <Input
          id="confirmPassword"
          type="password"
          autoComplete="new-password"
          readOnly={isSubmitting}
          aria-invalid={errors.confirmPassword ? "true" : "false"}
          aria-describedby={describedBy("confirmPassword", {
            error: Boolean(errors.confirmPassword),
          })}
          data-testid="reset-password-confirm-input"
          {...register("confirmPassword")}
        />
      </FormField>
      <Button
        type="submit"
        width="full"
        disabled={isSubmitting}
        data-testid="reset-password-submit-button"
      >
        {isSubmitting ? "Saving…" : "Set new password"}
      </Button>
    </form>
  );
}
