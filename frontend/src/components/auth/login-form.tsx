"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "@/components/feedback/toast";

import { Button } from "@/components/ui/button";
import { describedBy, FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { isApiError } from "@/lib/api/errors";
import { useAuthActions } from "@/lib/auth";

import { messageFor } from "./messages";
import { logInSchema, type LogInValues } from "./schemas";

// Log in, step 1 (US3.4, WF-U1-3; mockups §2.3).
export function LogInForm() {
  const router = useRouter();
  const { logIn } = useAuthActions();
  const [formError, setFormError] = useState<string | null>(null);
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
          className="rounded-[var(--radius)] border border-danger p-3 text-base text-danger"
          data-testid="login-form-error"
        >
          <span aria-hidden="true">⚠ </span>
          {formError}
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
