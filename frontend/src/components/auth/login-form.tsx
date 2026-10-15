"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { CircleAlert } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { PageLoader } from "@/components/app/page-loader";
import { toast } from "@/components/feedback/toast";

import { Button } from "@/components/ui/button";
import { describedBy, FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { isApiError } from "@/lib/api/errors";
import { useAuthActions } from "@/lib/auth";

import { messageFor } from "./messages";
import { useSignedInRedirect } from "./use-signed-in-redirect";
import { logInSchema, type LogInValues } from "./schemas";

// Log in, step 1 (US3.4, WF-U1-3; mockups §2.3).
export function LogInForm() {
  const router = useRouter();
  const { logIn } = useAuthActions();
  const [formError, setFormError] = useState<string | null>(null);
  const { redirecting } = useSignedInRedirect();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LogInValues>({
    resolver: zodResolver(logInSchema),
    defaultValues: { email: "", password: "" },
  });

  async function onSubmit(values: LogInValues) {
    setFormError(null);
    try {
      await logIn(values);
      toast.success("We sent you a code. Check your email.");
      router.push("/verify");
    } catch (error) {
      if (!isApiError(error)) throw error;
      const message = messageFor(error);
      if (error.code === "INVALID_CREDENTIALS") {
        setFormError(message);
        return;
      }
      toast.error(message);
    }
  }

  if (redirecting) return <PageLoader message="Taking you to your account…" />;

  return (
    <form
      noValidate
      onSubmit={handleSubmit(onSubmit)}
      className="space-y-5"
      data-testid="login-form"
    >
      {formError ? (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-ui border border-danger/30 bg-danger-soft p-3 text-[15px] text-danger"
          data-testid="login-form-error"
        >
          <CircleAlert className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
          <span>{formError}</span>
        </p>
      ) : null}
      <FormField id="email" label="Email" error={errors.email?.message}>
        <Input
          id="email"
          type="email"
          autoComplete="email"
          readOnly={isSubmitting}
          aria-invalid={errors.email ? "true" : "false"}
          aria-describedby={describedBy("email", { error: Boolean(errors.email) })}
          data-testid="login-email-input"
          {...register("email")}
        />
      </FormField>
      <FormField id="password" label="Password" error={errors.password?.message}>
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          readOnly={isSubmitting}
          aria-invalid={errors.password ? "true" : "false"}
          aria-describedby={describedBy("password", { error: Boolean(errors.password) })}
          data-testid="login-password-input"
          {...register("password")}
        />
      </FormField>
      <p className="text-right text-base">
        <Link
          href="/forgot-password"
          className="font-semibold text-accent-strong underline"
          data-testid="login-forgot-password-link"
        >
          Forgot your password?
        </Link>
      </p>
      <Button type="submit" width="full" disabled={isSubmitting} data-testid="login-submit-button">
        {isSubmitting ? "Checking…" : "Log in"}
      </Button>
      <p className="text-center text-base">
        New here?{" "}
        <Link
          href="/signup"
          className="font-semibold text-accent-strong underline"
          data-testid="login-signup-link"
        >
          Create an account
        </Link>
      </p>
    </form>
  );
}
