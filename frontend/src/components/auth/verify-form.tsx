"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { toast } from "@/components/feedback/toast";
import { Button } from "@/components/ui/button";
import { describedBy, FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { isApiError } from "@/lib/api/errors";
import { useAuth, useAuthActions, type CodePurpose } from "@/lib/auth";
import { useGoToNextStep } from "@/lib/journey";

import { messageFor } from "./messages";
import { ResendCodeButton } from "./resend-code-button";
import { codeSchema, type CodeValues } from "./schemas";

const CODE_ERRORS = ["CODE_INVALID", "CODE_EXPIRED", "CODE_LOCKED", "VALIDATION_FAILED"];

function startPage(purpose: CodePurpose, email: string | null): string {
  if (purpose === "signup") return `/signup?email=${encodeURIComponent(email ?? "")}`;
  return purpose === "login" ? "/login" : "/forgot-password";
}

// Enter your code (US3.2, US3.3, US3.9; WF-U1-2, WF-U2-1, WF-U2-7; mockups §2.2, OtpEntry
// spec). One numeric field so paste and one-time-code autofill work. The same screen serves
// sign-up, login and password reset. "Send a new code" (with its countdown) replaces U1's
// "start again" link.
export function VerifyForm() {
  const router = useRouter();
  const goToNextStep = useGoToNextStep();
  const { pending, pendingEmail } = useAuth();
  const { verifyCode, verifyResetCode, cancelPending } = useAuthActions();
  const [locked, setLocked] = useState(false);
  const {
    register,
    handleSubmit,
    setError,
    setFocus,
    setValue,
    clearErrors,
    formState: { errors, isSubmitting },
  } = useForm<CodeValues>({ resolver: zodResolver(codeSchema), defaultValues: { code: "" } });

  useEffect(() => {
    if (!pending) {
      router.replace("/login");
      return;
    }
    setFocus("code");
  }, [pending, router, setFocus]);

  if (!pending) {
    return <p className="text-base text-muted">Taking you to sign in…</p>;
  }

  const purpose = pending.purpose;
  const restartHref = startPage(purpose, pendingEmail);

  async function onSubmit(values: CodeValues) {
    try {
      if (purpose === "password_reset") {
        await verifyResetCode(values.code.trim());
        toast.success("Code confirmed. Choose a new password.");
        router.push("/reset-password");
        return;
      }
      await verifyCode(values.code.trim());
      toast.success(purpose === "signup" ? "Your account is ready." : "You're signed in.");
      await goToNextStep(); // US11.8: sign-in lands on the next unfinished step
    } catch (error) {
      if (!isApiError(error)) throw error;
      if (error.code === "CODE_LOCKED") setLocked(true);
      if (CODE_ERRORS.includes(error.code)) {
        setError("code", { message: messageFor(error) }, { shouldFocus: true });
        return;
      }
      toast.error(messageFor(error));
    }
  }

  function onResent() {
    setValue("code", "");
    clearErrors("code");
    setLocked(false);
    setFocus("code");
  }

  return (
    <form
      noValidate
      onSubmit={handleSubmit(onSubmit)}
      className="space-y-5"
      data-testid="verify-form"
    >
      <p className="text-base" data-testid="verify-masked-email">
        {purpose === "password_reset"
          ? "If that email has an account, we sent a 6-digit code to "
          : "We sent a 6-digit code to "}
        <strong>{pending.maskedEmail}</strong>.
      </p>
      <FormField id="code" label="6-digit code" error={errors.code?.message}>
        <Input
          id="code"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={6}
          className="text-2xl tracking-[0.3em]"
          disabled={locked}
          readOnly={isSubmitting}
          aria-invalid={errors.code ? "true" : "false"}
          aria-describedby={describedBy("code", { error: Boolean(errors.code) })}
          data-testid="verify-code-input"
          {...register("code")}
        />
      </FormField>
      <Button
        type="submit"
        width="full"
        disabled={isSubmitting || locked}
        data-testid="verify-submit-button"
      >
        {isSubmitting ? "Checking…" : "Verify"}
      </Button>
      {locked ? (
        <p className="text-sm text-muted" data-testid="verify-locked-reason">
          Verify is turned off until the time shown above.
        </p>
      ) : null}
      <ResendCodeButton availableAt={pending.resendAvailableAt} onResent={onResent} />
      <p className="text-base">
        Wrong email?{" "}
        <Link
          href={restartHref}
          onClick={cancelPending}
          className="font-semibold text-accent-strong underline"
          data-testid="verify-go-back-link"
        >
          Go back
        </Link>
      </p>
    </form>
  );
}
