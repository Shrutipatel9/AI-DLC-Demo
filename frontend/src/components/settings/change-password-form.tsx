"use client";

// Settings -> Password (US11.5, WF-U2-8; AC11.5.1-AC11.5.3). The confirm field must match
// before anything is sent (BR5.2). A wrong current password is shown on that field plus an
// error toast; it never counts as an expired session (BR5.1, BR6.4).
import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useForm, useWatch } from "react-hook-form";

import { messageFor } from "@/components/auth/messages";
import { PasswordRules } from "@/components/auth/password-rules";
import { changePasswordSchema, type ChangePasswordValues } from "@/components/auth/schemas";
import { toast } from "@/components/feedback/toast";
import { Button } from "@/components/ui/button";
import { describedBy, FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { isApiError } from "@/lib/api/errors";
import { useAuthActions } from "@/lib/auth";

const EMPTY: ChangePasswordValues = { currentPassword: "", newPassword: "", confirmPassword: "" };
const WRONG_CURRENT = "Your current password is incorrect.";

export function ChangePasswordForm() {
  const router = useRouter();
  const { changePassword } = useAuthActions();
  const {
    register,
    handleSubmit,
    control,
    setError,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ChangePasswordValues>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: EMPTY,
  });
  const newPassword = useWatch({ control, name: "newPassword" });

  async function onSubmit(values: ChangePasswordValues) {
    try {
      await changePassword(values.currentPassword, values.newPassword);
      reset(EMPTY);
      toast.success("Your password was changed. Other devices are signed out.");
    } catch (error) {
      if (!isApiError(error)) throw error;
      if (error.code === "INVALID_CREDENTIALS") {
        setError("currentPassword", { message: WRONG_CURRENT }, { shouldFocus: true });
        toast.error(WRONG_CURRENT);
        return;
      }
      if (error.code === "VALIDATION_FAILED") {
        setError(
          "newPassword",
          { message: "This password is too common or too weak — try another." },
          { shouldFocus: true },
        );
        return;
      }
      if (error.code === "SESSION_INVALID") {
        router.replace("/login");
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
      data-testid="change-password-form"
    >
      <FormField
        id="currentPassword"
        label="Current password"
        error={errors.currentPassword?.message}
      >
        <Input
          id="currentPassword"
          type="password"
          autoComplete="current-password"
          readOnly={isSubmitting}
          aria-invalid={errors.currentPassword ? "true" : "false"}
          aria-describedby={describedBy("currentPassword", {
            error: Boolean(errors.currentPassword),
          })}
          data-testid="change-password-current-input"
          {...register("currentPassword")}
        />
      </FormField>
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
          data-testid="change-password-new-input"
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
          data-testid="change-password-confirm-input"
          {...register("confirmPassword")}
        />
      </FormField>
      <Button
        type="submit"
        width="full"
        disabled={isSubmitting}
        data-testid="change-password-submit-button"
      >
        {isSubmitting ? "Saving…" : "Change password"}
      </Button>
    </form>
  );
}
